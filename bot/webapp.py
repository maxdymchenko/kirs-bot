"""HTTP API + статика Mini App."""

from __future__ import annotations

import asyncio
import logging
import os
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from bot.accounts import AppStorage
from bot.catalog import CatalogService
from bot.core import DropperConfig, Settings
from bot.novaposhta import NovaPoshtaClient, NovaPoshtaError
from bot.roles import is_owner, is_owner_chat, resolve_session

logger = logging.getLogger(__name__)

MINIAPP_DIR = Path(__file__).resolve().parent.parent / "miniapp"


class DropperRegisterRequest(BaseModel):
    chat_id: str = Field(..., min_length=2, max_length=64)
    company_name: str = Field(..., min_length=2, max_length=120)
    contact_name: str = Field(..., min_length=2, max_length=120)
    phone: str = Field(..., min_length=10, max_length=32)
    comment: str = Field("", max_length=500)
    user_id: str = Field("", max_length=64)
    username: str = Field("", max_length=64)


class StaffCreateRequest(BaseModel):
    telegram_user_id: str = Field(..., min_length=2, max_length=64)
    role: str = Field(..., min_length=3, max_length=32)
    full_name: str = Field("", max_length=120)
    username: str = Field("", max_length=64)
    owner_chat_id: str = Field("", max_length=64)
    owner_user_id: str = Field("", max_length=64)
    created_by_user_id: str = Field("", max_length=64)


class DropperPaymentFlagRequest(BaseModel):
    owner_chat_id: str = Field("", max_length=64)
    owner_user_id: str = Field("", max_length=64)
    require_full_payment: bool


def create_web_app(
    catalog: CatalogService,
    settings: Settings | None = None,
    app_storage: AppStorage | None = None,
) -> FastAPI:
    app = FastAPI(title="Kirs Mini App")
    np_client = NovaPoshtaClient()
    app_settings = settings
    storage = app_storage or AppStorage()

    def _require_settings() -> Settings:
        if not app_settings:
            raise HTTPException(status_code=503, detail="Settings не ініціалізовано")
        return app_settings

    def _require_owner(owner_chat_id: str = "", owner_user_id: str = "") -> Settings:
        cfg = _require_settings()
        if not is_owner(cfg, owner_chat_id, owner_user_id, storage):
            raise HTTPException(status_code=403, detail="Доступ лише для власника")
        return cfg

    def _yaml_dropper(chat_id: str) -> DropperConfig | None:
        key = storage.resolve_chat_id(str(chat_id or "").strip())
        if app_settings and key in app_settings.droppers:
            return app_settings.droppers[key]
        raw = str(chat_id or "").strip()
        if app_settings and raw in app_settings.droppers:
            return app_settings.droppers[raw]
        return None

    async def _notify(chat_id: str, text: str) -> None:
        cfg = _require_settings()

        def _send() -> None:
            import json
            import urllib.error
            import urllib.request

            url = f"https://api.telegram.org/bot{cfg.telegram_token}/sendMessage"
            payload = json.dumps(
                {
                    "chat_id": chat_id,
                    "text": text,
                    "disable_web_page_preview": True,
                },
                ensure_ascii=False,
            ).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                resp.read()

        try:
            await asyncio.to_thread(_send)
        except Exception:
            logger.exception("Не удалось отправить Telegram сообщение в %s", chat_id)

    async def _notify_owners(text: str) -> None:
        cfg = _require_settings()
        targets: list[str] = []
        for chat in cfg.owner_chat_ids:
            resolved = storage.resolve_chat_id(chat) or chat
            if resolved and resolved not in targets:
                targets.append(resolved)
        for user in cfg.owner_user_ids:
            if user and user not in targets:
                targets.append(user)
        for target in targets:
            await _notify(target, text)

    @app.get("/health")
    async def health() -> dict:
        return {"ok": True, "nova_poshta": np_client.configured()}

    @app.get("/api/session")
    async def session(
        chat_id: str = Query("", max_length=64),
        user_id: str = Query("", max_length=64),
    ) -> dict:
        cfg = _require_settings()
        return resolve_session(cfg, storage, chat_id, user_id)

    @app.get("/api/dropper/settings")
    async def dropper_settings(chat_id: str = Query("", max_length=64)) -> dict:
        db_dropper = storage.get_dropper_by_chat(chat_id)
        if db_dropper:
            return {
                "chat_id": db_dropper.chat_id,
                "name": db_dropper.company_name,
                "require_full_payment": db_dropper.require_full_payment,
                "source": "db",
            }
        yaml_dropper = _yaml_dropper(chat_id)
        if yaml_dropper:
            data = yaml_dropper.to_public_dict()
            data["source"] = "yaml"
            return data
        return {
            "chat_id": str(chat_id or "").strip(),
            "name": "",
            "require_full_payment": False,
            "source": "default",
        }

    @app.post("/api/droppers/register")
    async def register_dropper(payload: DropperRegisterRequest) -> dict:
        cfg = _require_settings()
        chat_id = payload.chat_id.strip()
        if not chat_id.startswith("-"):
            raise HTTPException(
                status_code=400,
                detail="Реєстрація дроппера доступна лише з групи Telegram",
            )
        if is_owner_chat(cfg, chat_id, storage):
            raise HTTPException(
                status_code=400,
                detail="Цей чат є кабінетом власника, реєстрація дроппера тут не потрібна",
            )
        existing = storage.get_dropper_by_chat(chat_id)
        if existing:
            return {
                "ok": True,
                "already_registered": True,
                "dropper": existing.to_dict(),
            }

        phone_digits = re.sub(r"\D", "", payload.phone.strip())
        if len(phone_digits) < 10:
            raise HTTPException(status_code=400, detail="Некоректний телефон")
        phone = phone_digits

        try:
            dropper = storage.create_dropper(
                chat_id=chat_id,
                company_name=payload.company_name,
                contact_name=payload.contact_name,
                phone=phone,
                comment=payload.comment,
                registered_by_user_id=payload.user_id,
                registered_by_username=payload.username,
            )
        except Exception as exc:
            logger.exception("register dropper failed")
            if "UNIQUE" in str(exc).upper():
                again = storage.get_dropper_by_chat(chat_id)
                if again:
                    return {"ok": True, "already_registered": True, "dropper": again.to_dict()}
            raise HTTPException(status_code=500, detail="Не вдалося зберегти реєстрацію") from exc

        group_text = (
            "✅ Реєстрацію дроппера успішно завершено!\n\n"
            f"Компанія: {dropper.company_name}\n"
            f"Контакт: {dropper.contact_name}\n"
            f"Телефон: {dropper.phone}\n"
            f"chat_id цієї групи: {dropper.chat_id}\n\n"
            "Тепер можна оформлювати замовлення через /menu."
        )
        owner_text = (
            "🆕 Новий дроппер зареєстрований\n\n"
            f"Компанія: {dropper.company_name}\n"
            f"Контакт: {dropper.contact_name}\n"
            f"Телефон: {dropper.phone}\n"
            f"Коментар: {dropper.comment or '—'}\n"
            f"chat_id групи: `{dropper.chat_id}`\n"
            f"Хто зареєстрував: @{dropper.registered_by_username or '—'} "
            f"(user_id={dropper.registered_by_user_id or '—'})\n\n"
            "Дроппер уже активний у базі (SQLite). "
            "Додавати chat_id на Render не потрібно."
        )

        await _notify(chat_id, group_text)
        await _notify_owners(owner_text)

        return {"ok": True, "already_registered": False, "dropper": dropper.to_dict()}

    @app.get("/api/owner/droppers")
    async def owner_list_droppers(
        owner_chat_id: str = Query("", max_length=64),
        owner_user_id: str = Query("", max_length=64),
    ) -> dict:
        _require_owner(owner_chat_id, owner_user_id)
        items = [d.to_dict() for d in storage.list_droppers()]
        return {"count": len(items), "items": items}

    @app.get("/api/owner/staff")
    async def owner_list_staff(
        owner_chat_id: str = Query("", max_length=64),
        owner_user_id: str = Query("", max_length=64),
    ) -> dict:
        _require_owner(owner_chat_id, owner_user_id)
        items = [s.to_dict() for s in storage.list_staff()]
        return {"count": len(items), "items": items}

    @app.post("/api/owner/staff")
    async def owner_add_staff(payload: StaffCreateRequest) -> dict:
        _require_owner(payload.owner_chat_id, payload.owner_user_id or payload.created_by_user_id)
        try:
            member = storage.upsert_staff(
                telegram_user_id=payload.telegram_user_id,
                role=payload.role,
                full_name=payload.full_name,
                username=payload.username,
                created_by_user_id=payload.created_by_user_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "staff": member.to_dict()}

    @app.post("/api/owner/droppers/{chat_id}/payment-flag")
    async def owner_set_payment_flag(
        chat_id: str,
        payload: DropperPaymentFlagRequest,
    ) -> dict:
        _require_owner(payload.owner_chat_id, payload.owner_user_id)
        dropper = storage.set_dropper_require_full_payment(
            chat_id, payload.require_full_payment
        )
        if not dropper:
            raise HTTPException(status_code=404, detail="Дроппера не знайдено")
        return {"ok": True, "dropper": dropper.to_dict()}

    @app.get("/api/products/search")
    async def search_products(code: str = Query(..., min_length=1, max_length=64)) -> dict:
        try:
            variants = catalog.search_by_code(code)
        except Exception:
            logger.exception("Ошибка поиска по коду %s", code)
            raise HTTPException(status_code=500, detail="Не удалось прочитать каталог") from None

        return {
            "query": code.strip(),
            "count": len(variants),
            "items": [v.to_dict() for v in variants],
        }

    @app.get("/api/np/settlements")
    async def search_settlements(
        q: str = Query(..., min_length=2, max_length=100),
        limit: int = Query(20, ge=1, le=50),
    ) -> dict:
        if not np_client.configured():
            raise HTTPException(status_code=503, detail="NOVA_POSHTA_API_KEY не налаштовано")
        try:
            items = await asyncio.to_thread(np_client.search_settlements, q, limit)
        except NovaPoshtaError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except Exception:
            logger.exception("NP settlements failed")
            raise HTTPException(status_code=502, detail="Помилка пошуку населених пунктів") from None
        return {"query": q.strip(), "count": len(items), "items": [i.to_dict() for i in items]}

    @app.get("/api/np/warehouses")
    async def search_warehouses(
        city_ref: str = Query(..., min_length=10, max_length=64),
        q: str = Query("", max_length=100),
        limit: int = Query(50, ge=1, le=100),
    ) -> dict:
        if not np_client.configured():
            raise HTTPException(status_code=503, detail="NOVA_POSHTA_API_KEY не налаштовано")
        try:
            items = await asyncio.to_thread(np_client.search_warehouses, city_ref, q, limit)
        except NovaPoshtaError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except Exception:
            logger.exception("NP warehouses failed")
            raise HTTPException(status_code=502, detail="Помилка пошуку відділень") from None
        return {
            "city_ref": city_ref.strip(),
            "query": q.strip(),
            "count": len(items),
            "items": [i.to_dict() for i in items],
        }

    @app.get("/api/np/streets")
    async def search_streets(
        q: str = Query(..., min_length=2, max_length=100),
        settlement_ref: str = Query("", max_length=64),
        city_ref: str = Query("", max_length=64),
        limit: int = Query(20, ge=1, le=50),
    ) -> dict:
        if not np_client.configured():
            raise HTTPException(status_code=503, detail="NOVA_POSHTA_API_KEY не налаштовано")
        if not settlement_ref.strip() and not city_ref.strip():
            raise HTTPException(status_code=400, detail="Потрібен settlement_ref або city_ref")
        try:
            items = await asyncio.to_thread(
                np_client.search_streets, settlement_ref, q, city_ref, limit
            )
        except NovaPoshtaError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except Exception:
            logger.exception("NP streets failed")
            raise HTTPException(status_code=502, detail="Помилка пошуку вулиць") from None
        return {
            "query": q.strip(),
            "settlement_ref": settlement_ref.strip(),
            "city_ref": city_ref.strip(),
            "count": len(items),
            "items": [i.to_dict() for i in items],
        }

    @app.get("/")
    async def miniapp_index() -> FileResponse:
        index = MINIAPP_DIR / "index.html"
        if not index.exists():
            raise HTTPException(status_code=404, detail="Mini App не найдена")
        return FileResponse(
            index,
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate",
                "Pragma": "no-cache",
            },
        )

    if MINIAPP_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(MINIAPP_DIR)), name="static")

    return app


def get_public_webapp_url() -> str:
    explicit = os.getenv("WEBAPP_URL", "").strip().rstrip("/")
    if explicit:
        return explicit
    render_url = os.getenv("RENDER_EXTERNAL_URL", "").strip().rstrip("/")
    if render_url:
        return render_url
    return "http://127.0.0.1:8000"
