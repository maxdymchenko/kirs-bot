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
    referral_code: str = Field("", max_length=32)


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


class DropperSettingsUpdateRequest(BaseModel):
    owner_chat_id: str = Field("", max_length=64)
    owner_user_id: str = Field("", max_length=64)
    require_full_payment: bool | None = None
    allow_balance_payment: bool | None = None
    allow_negative_balance: bool | None = None
    negative_balance_limit: float | None = None
    extra_discount_percent: float | None = None
    orders_disabled: bool | None = None
    referral_percent: float | None = None


def _apply_dropper_discount(price_raw: str, percent: float) -> tuple[str, str | None]:
    """Повертає (ціна_для_показу, оригінал_або_None)."""
    if not percent or percent <= 0:
        return price_raw, None
    try:
        price = float(str(price_raw).replace(",", ".").strip())
    except (TypeError, ValueError):
        return price_raw, None
    discounted = price * (1.0 - float(percent) / 100.0)
    if discounted < 0:
        discounted = 0.0
    if abs(discounted - round(discounted)) < 1e-9:
        shown = str(int(round(discounted)))
    else:
        shown = f"{discounted:.2f}".rstrip("0").rstrip(".")
    return shown, str(price_raw)

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
            data = db_dropper.to_dict()
            data["name"] = db_dropper.company_name
            data["source"] = "db"
            if db_dropper.referred_by_dropper_id:
                referrer = storage.get_dropper_by_id(db_dropper.referred_by_dropper_id)
                data["referred_by"] = (
                    {
                        "id": referrer.id,
                        "company_name": referrer.company_name,
                        "referral_code": referrer.referral_code,
                    }
                    if referrer
                    else None
                )
            else:
                data["referred_by"] = None
            data["referrals"] = [
                {
                    "id": r.id,
                    "company_name": r.company_name,
                    "chat_id": r.chat_id,
                }
                for r in storage.list_referrals(db_dropper.id)
            ]
            return data
        yaml_dropper = _yaml_dropper(chat_id)
        if yaml_dropper:
            data = yaml_dropper.to_public_dict()
            data["source"] = "yaml"
            return data
        return {
            "chat_id": str(chat_id or "").strip(),
            "name": "",
            "require_full_payment": False,
            "allow_balance_payment": False,
            "allow_negative_balance": False,
            "negative_balance_limit": 0,
            "extra_discount_percent": 0,
            "orders_disabled": False,
            "referral_percent": 0,
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

        if payload.referral_code.strip():
            if not storage.get_dropper_by_referral_code(payload.referral_code):
                raise HTTPException(
                    status_code=400,
                    detail="Реферальний код не знайдено. Перевірте або залиште поле порожнім.",
                )

        try:
            dropper = storage.create_dropper(
                chat_id=chat_id,
                company_name=payload.company_name,
                contact_name=payload.contact_name,
                phone=phone,
                comment=payload.comment,
                registered_by_user_id=payload.user_id,
                registered_by_username=payload.username,
                referral_code_used=payload.referral_code,
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
            f"chat_id цієї групи: {dropper.chat_id}\n"
            f"Ваш реферальний код: {dropper.referral_code}\n\n"
            "Тепер можна оформлювати замовлення через /menu."
        )
        owner_text = (
            "🆕 Новий дроппер зареєстрований\n\n"
            f"Компанія: {dropper.company_name}\n"
            f"Контакт: {dropper.contact_name}\n"
            f"Телефон: {dropper.phone}\n"
            f"Коментар: {dropper.comment or '—'}\n"
            f"chat_id групи: `{dropper.chat_id}`\n"
            f"Реферальний код: `{dropper.referral_code}`\n"
            f"Хто зареєстрував: @{dropper.registered_by_username or '—'} "
            f"(user_id={dropper.registered_by_user_id or '—'})\n\n"
            "Дроппер уже активний у базі (SQLite)."
        )
        if dropper.referred_by_dropper_id:
            referrer = storage.get_dropper_by_id(dropper.referred_by_dropper_id)
            if referrer:
                owner_text += f"\nЗапросив: {referrer.company_name} ({referrer.referral_code})"

        await _notify(chat_id, group_text)
        await _notify_owners(owner_text)

        return {"ok": True, "already_registered": False, "dropper": dropper.to_dict()}

    @app.get("/api/owner/droppers")
    async def owner_list_droppers(
        owner_chat_id: str = Query("", max_length=64),
        owner_user_id: str = Query("", max_length=64),
    ) -> dict:
        _require_owner(owner_chat_id, owner_user_id)
        items = []
        for d in storage.list_droppers():
            data = d.to_dict()
            data["referrals_count"] = len(storage.list_referrals(d.id))
            if d.referred_by_dropper_id:
                ref = storage.get_dropper_by_id(d.referred_by_dropper_id)
                data["referred_by_name"] = ref.company_name if ref else ""
            else:
                data["referred_by_name"] = ""
            items.append(data)
        return {"count": len(items), "items": items}

    @app.get("/api/dropper/balance")
    async def dropper_balance(chat_id: str = Query(..., max_length=64)) -> dict:
        dropper = storage.get_dropper_by_chat(chat_id)
        if not dropper:
            raise HTTPException(status_code=404, detail="Дроппера не знайдено")
        ledger = storage.list_ledger(dropper.id, limit=100)
        referrals = [x for x in ledger if x["entry_type"] == "referral_credit"]
        return {
            "dropper": dropper.to_dict(),
            "balance": storage.get_balance(dropper.id),
            "referral_earned_total": round(sum(x["amount"] for x in referrals), 2),
            "ledger": ledger,
            "referrals": referrals,
            "note": (
                "Реферальні нарахування = % від дроп-ціни замовлень "
                "приведених дропперів (після підтвердження замовлення)."
            ),
        }

    @app.get("/api/owner/balances")
    async def owner_balances(
        owner_chat_id: str = Query("", max_length=64),
        owner_user_id: str = Query("", max_length=64),
    ) -> dict:
        _require_owner(owner_chat_id, owner_user_id)
        items = storage.list_dropper_balances()
        referral_history = storage.list_ledger(entry_type="referral_credit", limit=100)
        # збагачуємо іменами
        enriched = []
        for row in referral_history:
            beneficiary = storage.get_dropper_by_id(row["dropper_id"])
            source = (
                storage.get_dropper_by_id(row["related_dropper_id"])
                if row.get("related_dropper_id")
                else None
            )
            enriched.append(
                {
                    **row,
                    "beneficiary_name": beneficiary.company_name if beneficiary else "",
                    "source_name": source.company_name if source else "",
                }
            )
        return {
            "count": len(items),
            "items": items,
            "referral_history": enriched,
            "rule": "Реф.% рахується від дроп-ціни замовлення приведеного дроппера.",
        }

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

    @app.post("/api/owner/droppers/{chat_id}/settings")
    async def owner_update_dropper_settings(
        chat_id: str,
        payload: DropperSettingsUpdateRequest,
    ) -> dict:
        _require_owner(payload.owner_chat_id, payload.owner_user_id)
        dropper = storage.update_dropper_settings(
            chat_id,
            require_full_payment=payload.require_full_payment,
            allow_balance_payment=payload.allow_balance_payment,
            allow_negative_balance=payload.allow_negative_balance,
            negative_balance_limit=payload.negative_balance_limit,
            extra_discount_percent=payload.extra_discount_percent,
            orders_disabled=payload.orders_disabled,
            referral_percent=payload.referral_percent,
        )
        if not dropper:
            raise HTTPException(status_code=404, detail="Дроппера не знайдено")
        return {"ok": True, "dropper": dropper.to_dict()}

    @app.get("/api/products/colors")
    async def product_colors(
        q: str = Query("", max_length=64),
        limit: int = Query(40, ge=1, le=200),
    ) -> dict:
        try:
            colors = catalog.list_colors(query=q, limit=limit)
        except Exception:
            logger.exception("Ошибка чтения цветов каталога")
            raise HTTPException(status_code=500, detail="Не удалось прочитать каталог") from None
        return {"query": q.strip(), "count": len(colors), "items": colors}

    @app.get("/api/products/search")
    async def search_products(
        q: str = Query("", max_length=120),
        code: str = Query("", max_length=64),
        color: str = Query("", max_length=64),
        chat_id: str = Query("", max_length=64),
        limit: int = Query(80, ge=1, le=200),
    ) -> dict:
        query = (q or code or "").strip()
        color_q = color.strip()
        if not query and not color_q:
            raise HTTPException(status_code=400, detail="Вкажіть пошуковий запит або колір")
        try:
            variants = catalog.search(query=query, color=color_q, limit=limit)
        except Exception:
            logger.exception("Ошибка поиска query=%s color=%s", query, color_q)
            raise HTTPException(status_code=500, detail="Не удалось прочитать каталог") from None

        dropper = storage.get_dropper_by_chat(chat_id) if chat_id else None
        discount = float(dropper.extra_discount_percent) if dropper else 0.0
        items = []
        for v in variants:
            data = v.to_dict()
            shown, original = _apply_dropper_discount(data.get("drop_price") or "", discount)
            data["drop_price"] = shown
            if original is not None:
                data["drop_price_original"] = original
                data["extra_discount_percent"] = discount
            items.append(data)

        return {
            "query": query,
            "color": color_q,
            "count": len(items),
            "items": items,
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
        limit: int = Query(200, ge=1, le=500),
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
