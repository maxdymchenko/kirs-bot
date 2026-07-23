"""HTTP API + статика Mini App."""

from __future__ import annotations

import asyncio
import logging
import os
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from bot.accounts import AppStorage
from bot.catalog import CatalogService, InsufficientStockError
from bot.core import DropperConfig, Settings
from bot.novaposhta import NovaPoshtaClient, NovaPoshtaError
from bot.roles import is_owner, is_owner_chat, resolve_session

logger = logging.getLogger(__name__)

MINIAPP_DIR = Path(__file__).resolve().parent.parent / "miniapp"
_USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{5,32}$")


def _norm_tg_username(raw: str) -> str:
    value = str(raw or "").strip()
    if value.startswith("@"):
        value = value[1:]
    return value.strip()


async def _resolve_telegram_staff_identity(
    settings: Settings, raw: str
) -> tuple[str, str]:
    """
    Повертає (telegram_user_id, username).
    Приймає числовий id або @username / username.
    """
    text = str(raw or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Вкажіть Telegram @username")

    if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
        return text.lstrip("+"), ""

    username = _norm_tg_username(text)
    if not _USERNAME_RE.match(username):
        raise HTTPException(
            status_code=400,
            detail="Нікнейм має бути у форматі @nickname (5–32 символи: літери, цифри, _)",
        )

    import json
    import urllib.error
    import urllib.parse
    import urllib.request

    def _get_chat() -> dict:
        url = (
            f"https://api.telegram.org/bot{settings.telegram_token}/getChat?"
            + urllib.parse.urlencode({"chat_id": f"@{username}"})
        )
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))

    try:
        data = await asyncio.to_thread(_get_chat)
    except urllib.error.HTTPError as exc:
        logger.warning("getChat(@%s) HTTP %s", username, exc.code)
        raise HTTPException(
            status_code=400,
            detail=(
                f"Не знайдено @{username}. Перевірте нік або попросіть людину "
                "спочатку написати боту /menu."
            ),
        ) from exc
    except Exception as exc:
        logger.exception("getChat(@%s) failed", username)
        raise HTTPException(
            status_code=502, detail="Не вдалося перевірити username у Telegram"
        ) from exc

    if not data.get("ok"):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Не знайдено @{username}. Перевірте нік або попросіть людину "
                "спочатку написати боту /menu."
            ),
        )
    chat = data.get("result") or {}
    user_id = str(chat.get("id") or "").strip()
    resolved_username = str(chat.get("username") or username).strip()
    if not user_id:
        raise HTTPException(status_code=400, detail="Telegram не повернув user_id")
    return user_id, resolved_username


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
    telegram: str = Field("", max_length=64)  # @username або числовий user_id
    telegram_user_id: str = Field("", max_length=64)  # legacy
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
    allow_cod: bool | None = None
    allow_balance_payment: bool | None = None
    allow_negative_balance: bool | None = None
    negative_balance_limit: float | None = None
    extra_discount_percent: float | None = None
    orders_disabled: bool | None = None
    referral_percent: float | None = None
    referral_program_enabled: bool | None = None
    referral_months: int | None = None
    owner_comment: str | None = None
    credit_holidays_days: int | None = None


class DropperSelfSettingsUpdateRequest(BaseModel):
    chat_id: str = Field(..., min_length=2, max_length=64)
    user_id: str = Field("", max_length=64)
    notify_shipping_events: bool | None = None


class OrderCreateRequest(BaseModel):
    chat_id: str = Field(..., min_length=2, max_length=64)
    user_id: str = Field("", max_length=64)
    first_name: str = Field("", max_length=80)
    patronymic: str = Field("", max_length=80)
    last_name: str = Field("", max_length=80)
    phone: str = Field(..., min_length=10, max_length=32)
    delivery_method: str = Field("", max_length=32)
    city: str = Field("", max_length=200)
    city_ref: str = Field("", max_length=64)
    settlement_ref: str = Field("", max_length=64)
    warehouse: str = Field("", max_length=300)
    warehouse_ref: str = Field("", max_length=64)
    street: str = Field("", max_length=200)
    street_ref: str = Field("", max_length=64)
    house: str = Field("", max_length=32)
    apartment: str = Field("", max_length=32)
    own_ttn: bool = False
    own_ttn_carrier: str = Field("", max_length=32)
    ttn_number: str = Field("", max_length=64)
    payment_method: str = Field(..., min_length=2, max_length=32)
    prepay: float = Field(0, ge=0)
    cod_amount: float = Field(0, ge=0)
    comment: str = Field("", max_length=1000)
    receipt_name: str = Field("", max_length=260)
    ttn_pdf_name: str = Field("", max_length=260)
    cart: list[dict] = Field(default_factory=list)
    total: float = Field(0, ge=0)
    np_city: dict | None = None
    np_warehouse: dict | None = None
    np_street: dict | None = None


class GeneralSettingsUpdateRequest(BaseModel):
    owner_chat_id: str = Field("", max_length=64)
    owner_user_id: str = Field("", max_length=64)
    np_api_keys: list[dict] = Field(default_factory=list)
    sender_city: dict = Field(default_factory=dict)
    sender_warehouse: dict = Field(default_factory=dict)
    parcel_defaults: dict = Field(default_factory=dict)
    orders_spreadsheet_url: str = Field("", max_length=500)
    orders_spreadsheet_id: str = Field("", max_length=128)
    orders_sheet_title: str = Field("Заказы", max_length=80)


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

    def _np_any_configured() -> bool:
        from bot.np_fulfillment import list_np_clients

        return bool(list_np_clients(storage)) or np_client.configured()

    def _np_call(operation: str, fn):
        from bot.np_fulfillment import call_with_np_key_rotation

        return call_with_np_key_rotation(storage, operation, fn)

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
        from bot.paths import data_dir, notifications_db_path
        from bot.storage import NotificationStorage

        data_path = data_dir()
        notif_path = notifications_db_path()
        notif_count = 0
        notif_max_id = 0
        unprocessed = 0
        try:
            ns = NotificationStorage(notif_path)
            with ns._connect() as conn:
                row = conn.execute(
                    "SELECT COUNT(*) AS c, COALESCE(MAX(id), 0) AS m FROM notifications"
                ).fetchone()
                notif_count = int(row["c"] or 0)
                notif_max_id = int(row["m"] or 0)
                row2 = conn.execute(
                    "SELECT COUNT(*) AS c FROM notifications WHERE processed = 0"
                ).fetchone()
                unprocessed = int(row2["c"] or 0)
        except Exception:
            logger.exception("health notifications check failed")

        return {
            "ok": True,
            "nova_poshta": _np_any_configured(),
            "app_data_dir_env": (os.getenv("APP_DATA_DIR") or "").strip() or None,
            "data_dir": str(data_path),
            "notifications_db": str(notif_path),
            "notifications_db_exists": notif_path.exists(),
            "notifications_count": notif_count,
            "notifications_max_id": notif_max_id,
            "notifications_unprocessed": unprocessed,
        }

    @app.get("/api/session")
    async def session(
        chat_id: str = Query("", max_length=64),
        user_id: str = Query("", max_length=64),
        username: str = Query("", max_length=64),
    ) -> dict:
        cfg = _require_settings()
        return resolve_session(cfg, storage, chat_id, user_id, username)

    @app.get("/api/dropper/settings")
    async def dropper_settings(chat_id: str = Query("", max_length=64)) -> dict:
        db_dropper = storage.get_dropper_by_chat(chat_id)
        if db_dropper:
            data = db_dropper.to_public_dict()
            data["name"] = db_dropper.company_name
            data["source"] = "db"
            # Реферальні деталі — лише якщо програма увімкнена у цього дроппера.
            data["referred_by"] = None
            data["referrals"] = []
            if db_dropper.referral_program_enabled:
                data["referrals"] = [
                    {
                        "id": r.id,
                        "company_name": r.company_name,
                        "chat_id": r.chat_id,
                    }
                    for r in storage.list_referrals(db_dropper.id)
                ]
            data["balance"] = storage.get_balance(db_dropper.id)
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
            "allow_cod": True,
            "allow_balance_payment": False,
            "allow_negative_balance": False,
            "negative_balance_limit": 0,
            "extra_discount_percent": 0,
            "orders_disabled": False,
            "referral_percent": 0,
            "notify_shipping_events": False,
            "source": "default",
        }

    @app.post("/api/dropper/settings")
    async def dropper_update_own_settings(
        payload: DropperSelfSettingsUpdateRequest,
    ) -> dict:
        dropper = storage.get_dropper_by_chat(payload.chat_id)
        if not dropper:
            raise HTTPException(status_code=404, detail="Дроппера не знайдено")
        updated = storage.update_dropper_settings(
            dropper.chat_id,
            notify_shipping_events=payload.notify_shipping_events,
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Дроппера не знайдено")
        data = updated.to_public_dict()
        data["name"] = updated.company_name
        data["balance"] = storage.get_balance(updated.id)
        return {"ok": True, "dropper": data}

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

        skip_referral = False
        referral_block_reason = ""
        if payload.referral_code.strip():
            if not storage.get_dropper_by_referral_code(payload.referral_code):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Реферальний код не знайдено або програма вимкнена. "
                        "Перевірте код або залиште поле порожнім."
                    ),
                )
            taken = storage.referral_fingerprint_taken(
                user_id=payload.user_id,
                username=payload.username,
                phone=phone,
            )
            if taken:
                skip_referral = True
                referral_block_reason = (
                    f"тип={taken.get('type')} значення={taken.get('value')}"
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
                skip_referral_link=skip_referral,
            )
        except Exception as exc:
            logger.exception("register dropper failed")
            if "UNIQUE" in str(exc).upper():
                again = storage.get_dropper_by_chat(chat_id)
                if again:
                    return {"ok": True, "already_registered": True, "dropper": again.to_dict()}
            raise HTTPException(status_code=500, detail="Не вдалося зберегти реєстрацію") from exc

        storage.remember_referral_fingerprints(
            dropper_id=dropper.id,
            user_id=payload.user_id,
            username=payload.username,
            phone=phone,
        )

        code_line = ""
        if dropper.referral_program_enabled and dropper.referral_code:
            code_line = f"Ваш реферальний код: {dropper.referral_code}\n\n"
        group_text = (
            "✅ Реєстрацію дроппера успішно завершено!\n\n"
            f"Компанія: {dropper.company_name}\n"
            f"Контакт: {dropper.contact_name}\n"
            f"Телефон: {dropper.phone}\n"
            f"chat_id цієї групи: {dropper.chat_id}\n"
            f"{code_line}"
            "Тепер можна оформлювати замовлення через /menu."
        )
        owner_text = (
            "🆕 Новий дроппер зареєстрований\n\n"
            f"Компанія: {dropper.company_name}\n"
            f"Контакт: {dropper.contact_name}\n"
            f"Телефон: {dropper.phone}\n"
            f"Коментар: {dropper.comment or '—'}\n"
            f"chat_id групи: `{dropper.chat_id}`\n"
            f"Реферальний код: `{dropper.referral_code or '—'}`\n"
            f"Хто зареєстрував: @{dropper.registered_by_username or '—'} "
            f"(user_id={dropper.registered_by_user_id or '—'})\n\n"
            "Дроппер уже активний у базі (SQLite)."
        )
        if dropper.referred_by_dropper_id:
            referrer = storage.get_dropper_by_id(dropper.referred_by_dropper_id)
            if referrer:
                owner_text += (
                    f"\nЗапросив: {referrer.company_name} ({referrer.referral_code})"
                    f" · до {dropper.referral_expires_at or '—'}"
                )
        elif skip_referral and payload.referral_code.strip():
            owner_text += (
                "\n⚠️ Реферальний код вказано, але привʼязку заблоковано "
                f"(повторна реєстрація: {referral_block_reason})."
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
        items = []
        for d in storage.list_droppers():
            if d.status != "active":
                continue
            data = d.to_dict()
            data["referrals_count"] = len(storage.list_referrals(d.id))
            data["turnover"] = round(storage.dropper_turnover(d.id), 2)
            data["balance"] = storage.get_balance(d.id)
            if d.referred_by_dropper_id:
                ref = storage.get_dropper_by_id(d.referred_by_dropper_id)
                data["referred_by_name"] = ref.company_name if ref else ""
            else:
                data["referred_by_name"] = ""
            items.append(data)
        items.sort(key=lambda x: (-float(x.get("turnover") or 0), str(x.get("company_name") or "").casefold()))
        return {"count": len(items), "items": items}

    @app.get("/api/dropper/balance")
    async def dropper_balance(chat_id: str = Query(..., max_length=64)) -> dict:
        dropper = storage.get_dropper_by_chat(chat_id)
        if not dropper:
            raise HTTPException(status_code=404, detail="Дроппера не знайдено")
        ledger_all = storage.list_ledger(dropper.id, limit=5000)
        ledger = ledger_all[:200]
        referral_rows = [x for x in ledger_all if x["entry_type"] == "referral_credit"]
        credited_total = round(sum(x["amount"] for x in ledger_all if x["amount"] > 0), 2)
        debited_total = round(
            abs(sum(x["amount"] for x in ledger_all if x["amount"] < 0)), 2
        )
        program_on = bool(dropper.referral_program_enabled)
        referral_earned_total = (
            round(sum(x["amount"] for x in referral_rows), 2) if program_on else 0.0
        )

        enriched = []
        for row in ledger:
            item = dict(row)
            related_id = row.get("related_dropper_id")
            if program_on and related_id:
                source = storage.get_dropper_by_id(related_id)
                item["related_dropper_name"] = (
                    source.company_name if source else ""
                )
            else:
                item["related_dropper_name"] = ""
            # Без увімкненої програми — без реферальних підписів у історії.
            if not program_on and item.get("entry_type") == "referral_credit":
                item["entry_type"] = "manual_credit"
                item["title"] = "Нарахування"
                item["note"] = ""
                item["related_dropper_id"] = None
            enriched.append(item)

        balance = storage.get_balance(dropper.id)
        floor = (
            -max(0.0, float(dropper.negative_balance_limit or 0))
            if dropper.allow_negative_balance
            else 0.0
        )
        spend_room = (
            max(0.0, balance - floor) if dropper.allow_balance_payment else 0.0
        )
        note = (
            "Тут усі операції по балансу: прибуток з наложки після отримання посилки, "
            "списання за замовлення, передплата понад «Дроп ціна», реферали тощо. "
            "Самі замовлення — у вкладці «Історія»."
            if program_on
            else (
                "Тут усі операції по балансу: прибуток з наложки після отримання посилки, "
                "списання за замовлення, передплата понад «Дроп ціна» тощо. "
                "Самі замовлення — у вкладці «Історія»."
            )
        )
        return {
            "dropper": dropper.to_public_dict(),
            "balance": balance,
            "spend_room": round(spend_room, 2),
            "referral_earned_total": referral_earned_total,
            "credited_total": credited_total,
            "debited_total": debited_total,
            "ledger": enriched,
            "referrals": (
                [x for x in enriched if x["entry_type"] == "referral_credit"]
                if program_on
                else []
            ),
            "note": note,
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
        cfg = _require_owner(
            payload.owner_chat_id, payload.owner_user_id or payload.created_by_user_id
        )
        identity = (payload.telegram or payload.telegram_user_id or "").strip()
        if not identity:
            raise HTTPException(status_code=400, detail="Вкажіть Telegram @username")
        user_id, resolved_username = await _resolve_telegram_staff_identity(cfg, identity)
        username = resolved_username or _norm_tg_username(payload.username or identity)
        try:
            member = storage.upsert_staff(
                telegram_user_id=user_id,
                role=payload.role,
                full_name=payload.full_name,
                username=username,
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
            allow_cod=payload.allow_cod,
            allow_balance_payment=payload.allow_balance_payment,
            allow_negative_balance=payload.allow_negative_balance,
            negative_balance_limit=payload.negative_balance_limit,
            extra_discount_percent=payload.extra_discount_percent,
            orders_disabled=payload.orders_disabled,
            referral_percent=payload.referral_percent,
            referral_program_enabled=payload.referral_program_enabled,
            referral_months=payload.referral_months,
            owner_comment=payload.owner_comment,
            credit_holidays_days=payload.credit_holidays_days,
        )
        if not dropper:
            raise HTTPException(status_code=404, detail="Дроппера не знайдено")
        # Після зміни ліміту/канікул — перерахувати стан боргу
        from bot.credit_holidays import evaluate_credit_holidays

        evaluate_credit_holidays(storage, dropper)
        dropper = storage.get_dropper_by_chat(chat_id) or dropper
        return {"ok": True, "dropper": dropper.to_dict()}

    @app.delete("/api/owner/droppers/{chat_id}")
    async def owner_delete_dropper(
        chat_id: str,
        owner_chat_id: str = Query("", max_length=64),
        owner_user_id: str = Query("", max_length=64),
    ) -> dict:
        _require_owner(owner_chat_id, owner_user_id)
        dropper = storage.get_dropper_by_chat(chat_id)
        if not dropper:
            raise HTTPException(status_code=404, detail="Дроппера не знайдено")
        name = dropper.company_name
        ok = storage.delete_dropper(chat_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Дроппера не знайдено")
        return {"ok": True, "deleted": name, "chat_id": chat_id}

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
        if not _np_any_configured():
            raise HTTPException(status_code=503, detail="Немає API-ключа Нової Пошти")
        try:
            items = await asyncio.to_thread(
                _np_call, "settlements", lambda c: c.search_settlements(q, limit)
            )
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
        limit: int = Query(30, ge=1, le=500),
    ) -> dict:
        if not _np_any_configured():
            raise HTTPException(status_code=503, detail="Немає API-ключа Нової Пошти")
        try:
            items = await asyncio.to_thread(
                _np_call,
                "warehouses",
                lambda c: c.search_warehouses(city_ref, q, limit),
            )
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
        if not _np_any_configured():
            raise HTTPException(status_code=503, detail="Немає API-ключа Нової Пошти")
        if not settlement_ref.strip() and not city_ref.strip():
            raise HTTPException(status_code=400, detail="Потрібен settlement_ref або city_ref")
        try:
            items = await asyncio.to_thread(
                _np_call,
                "streets",
                lambda c: c.search_streets(settlement_ref, q, city_ref, limit),
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

    @app.post("/api/np/webhook")
    async def np_tracking_webhook(
        request: Request,
        token: str = Query("", max_length=128),
    ) -> dict:
        """
        Основний канал статусів — опитування раз на ~30 хв.
        Webhook (якщо НП підключений) — додатковий push на цей URL.
        Захист: якщо задано NP_WEBHOOK_TOKEN — обовʼязковий ?token=...
        """
        expected = os.getenv("NP_WEBHOOK_TOKEN", "").strip()
        if expected and token.strip() != expected:
            raise HTTPException(status_code=403, detail="Невірний webhook token")
        try:
            body = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Очікується JSON") from exc
        from bot.np_fulfillment import apply_webhook_payload

        stats = await apply_webhook_payload(storage, body, notify=_notify)
        logger.info("NP webhook: %s", stats)
        return {"ok": True, **stats}

    def _balance_spend_room(dropper) -> float:
        if not dropper.allow_balance_payment:
            return 0.0
        balance = storage.get_balance(dropper.id)
        floor = (
            -max(0.0, float(dropper.negative_balance_limit or 0))
            if dropper.allow_negative_balance
            else 0.0
        )
        return max(0.0, balance - floor)

    def _validate_order_payload(
        payload: OrderCreateRequest, dropper
    ) -> tuple[float, float, float, float]:
        if dropper.orders_disabled:
            raise HTTPException(status_code=403, detail="Передачу замовлень заблоковано")
        if dropper.credit_holidays_blocked:
            raise HTTPException(
                status_code=403,
                detail="Передачу заблоковано: вичерпано кредитні канікули. Погасіть борг повністю.",
            )
        if not payload.cart:
            raise HTTPException(status_code=400, detail="Кошик порожній")
        total = max(0.0, float(payload.total or 0))
        cart_sum = 0.0
        for item in payload.cart:
            try:
                price = float(str(item.get("drop_price") or "0").replace(",", "."))
            except (TypeError, ValueError):
                price = 0.0
            qty = max(1, int(item.get("qty") or 1))
            cart_sum += price * qty
        if abs(cart_sum - total) > 1.0 and total <= 0:
            total = round(cart_sum, 2)
        prepay = max(0.0, float(payload.prepay or 0))
        cod_amount = max(0.0, float(payload.cod_amount or 0))
        debit = 0.0
        if not str(payload.phone or "").strip():
            raise HTTPException(status_code=400, detail="Вкажіть номер телефону клієнта")

        if payload.own_ttn:
            if payload.payment_method not in ("requisites", "balance"):
                raise HTTPException(
                    status_code=400,
                    detail="При власній ТТН доступна оплата на реквізити або з балансу",
                )
            carrier = (payload.own_ttn_carrier or "nova_poshta").strip().lower()
            raw_ttn = str(payload.ttn_number or "").strip()
            if carrier == "rozetka":
                rmp = re.sub(r"\s+", "", raw_ttn).upper()
                if not re.fullmatch(r"RMP-\d{6,20}", rmp):
                    raise HTTPException(
                        status_code=400,
                        detail="Вкажіть номер RMP у форматі RMP-XXXXXXXXX",
                    )
            else:
                ttn = re.sub(r"\D", "", raw_ttn)
                if len(ttn) < 10:
                    raise HTTPException(status_code=400, detail="Вкажіть повний номер ТТН")
            if not str(payload.ttn_pdf_name or "").strip():
                raise HTTPException(
                    status_code=400,
                    detail="Прикріпіть файл PDF 100×100",
                )
            pdf_name = str(payload.ttn_pdf_name or "").strip().lower()
            if not pdf_name.endswith(".pdf"):
                raise HTTPException(
                    status_code=400,
                    detail="Файл 100×100 має бути у форматі PDF",
                )

        if payload.payment_method == "balance":
            if not dropper.allow_balance_payment:
                raise HTTPException(
                    status_code=403,
                    detail="Оплата з балансу для вас вимкнена",
                )
            room = _balance_spend_room(dropper)
            if total > room + 0.01:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Недостатньо доступного балансу "
                        f"(потрібно {round(total)} грн, доступно {round(room)} грн)"
                    ),
                )
            debit = round(total, 2)
            prepay = 0.0
            cod_amount = 0.0
        elif payload.own_ttn:
            cod_amount = 0.0
            prepay = 0.0
        elif payload.payment_method == "cod":
            if not getattr(dropper, "allow_cod", True):
                raise HTTPException(
                    status_code=403,
                    detail="Передачу замовлень наложкою для вас вимкнено",
                )
            if cod_amount < 0:
                raise HTTPException(status_code=400, detail="Вкажіть суму накладного платежу")
            if prepay > cod_amount + 0.01:
                raise HTTPException(
                    status_code=400,
                    detail="Передплата не може перевищувати суму накладного платежу",
                )
            room = _balance_spend_room(dropper)
            max_prepay = total + room
            if prepay > max_prepay + 0.01:
                raise HTTPException(
                    status_code=400,
                    detail=f"Передплата не може перевищувати {round(max_prepay)} грн",
                )
            debit = max(0.0, round(prepay - total, 2))
        else:
            cod_amount = 0.0

        if payload.own_ttn:
            # Доставка й ПІБ вже в етикетці ТТН — перевіряємо лише телефон вище.
            pass
        else:
            if not payload.first_name.strip() or not payload.last_name.strip():
                raise HTTPException(status_code=400, detail="Вкажіть ім'я та прізвище отримувача")
            if not payload.city_ref.strip():
                raise HTTPException(status_code=400, detail="Оберіть населений пункт")
            if payload.delivery_method == "np_warehouse" and not payload.warehouse_ref:
                raise HTTPException(status_code=400, detail="Оберіть відділення/поштомат")
            if payload.delivery_method == "np_courier":
                if not payload.patronymic.strip():
                    raise HTTPException(status_code=400, detail="Для курʼєра вкажіть по батькові")
                if not payload.street_ref or not payload.house.strip():
                    raise HTTPException(status_code=400, detail="Вкажіть адресу для курʼєра")

        if (
            payload.payment_method == "requisites"
            and dropper.require_full_payment
            and not payload.receipt_name.strip()
        ):
            raise HTTPException(status_code=400, detail="Потрібна квитанція про оплату")
        return total, prepay, debit, cod_amount

    def _format_dropper_accept_message(order: dict, dropper) -> str:
        payload = order.get("payload") or {}
        cart = payload.get("cart") or []
        lines = [
            "✅ Замовлення прийнято",
            "",
            f"Номер: {order.get('order_number')}",
            f"Сума: {round(float(order.get('total') or 0))} ₴",
        ]
        if order.get("cod_amount"):
            lines.append(f"Накладений платіж: {round(float(order.get('cod_amount') or 0))} ₴")
        if order.get("prepay"):
            lines.append(f"Передплата: {round(float(order.get('prepay') or 0))} ₴")
        if order.get("prepay_balance_debit"):
            lines.append(
                f"Списано з балансу: {round(float(order.get('prepay_balance_debit') or 0))} ₴"
            )
        method = (order.get("payment_method") or "").strip()
        if method == "balance":
            lines.append("Оплата: з балансу")
        elif method == "requisites":
            lines.append("Оплата: на реквізити")
        elif method == "cod":
            lines.append("Оплата: при отриманні")
        if order.get("own_ttn") and order.get("ttn_number"):
            carrier = ((order.get("payload") or {}).get("own_ttn_carrier") or "").strip()
            if carrier == "rozetka":
                lines.append(f"Ваш RMP: {order.get('ttn_number')}")
            else:
                lines.append(f"Ваша ТТН: {order.get('ttn_number')}")
        elif order.get("ttn_number"):
            lines.append(f"ТТН: {order.get('ttn_number')}")
        else:
            lines.append("ТТН: створюється через API Нової Пошти…")
        lines.append("")
        lines.append("Товари:")
        for item in cart[:20]:
            code = item.get("code") or ""
            name = item.get("name") or ""
            qty = item.get("qty") or 1
            lines.append(f"• {code} — {name} × {qty}")
        if len(cart) > 20:
            lines.append(f"… ще {len(cart) - 20}")
        lines.append("")
        lines.append("Деталі — у вкладці «Історія замовлень» Mini App.")
        return "\n".join(lines)

    @app.post("/api/orders")
    async def create_order(payload: OrderCreateRequest) -> dict:
        dropper = storage.get_dropper_by_chat(payload.chat_id)
        if not dropper:
            raise HTTPException(status_code=404, detail="Дроппера не знайдено")
        total, prepay, debit, cod_amount = _validate_order_payload(payload, dropper)

        own_ttn = bool(payload.own_ttn)
        carrier = (payload.own_ttn_carrier or "nova_poshta").strip().lower() if own_ttn else ""
        if own_ttn and carrier == "rozetka":
            ttn_number = re.sub(r"\s+", "", payload.ttn_number or "").upper()
        elif own_ttn:
            ttn_number = re.sub(r"\D", "", payload.ttn_number or "")
        else:
            ttn_number = ""
        if own_ttn:
            ttn_status = "provided"
        elif payload.payment_method == "cod":
            # Створення ТТН через API НП — окремий етап (потрібні реквізити відправника)
            ttn_status = "pending_create"
        else:
            ttn_status = "pending_create"

        safe_cart = []
        for item in payload.cart:
            safe_cart.append(
                {
                    "product_id": item.get("product_id") or "",
                    "code": item.get("code") or "",
                    "name": item.get("name") or "",
                    "color": item.get("color") or "",
                    "qty": max(1, int(item.get("qty") or 1)),
                    "drop_price": item.get("drop_price") or "",
                    "drop_price_original": item.get("drop_price_original") or "",
                    "extra_discount_percent": item.get("extra_discount_percent") or 0,
                    "stock": item.get("stock"),
                    "photo_url": item.get("photo_url") or "",
                }
            )

        # Списання наявності до створення замовлення (комплект → складові)
        try:
            catalog.consume_cart_stock(safe_cart)
        except InsufficientStockError as exc:
            raise HTTPException(status_code=400, detail=str(exc) or "Немає в наявності") from exc
        except Exception:
            logger.exception("Stock consume failed before order create")
            raise HTTPException(
                status_code=503,
                detail="Не вдалося оновити наявність у таблиці. Спробуйте ще раз.",
            )

        order_payload = {
            "recipient": {
                "first_name": payload.first_name.strip(),
                "patronymic": payload.patronymic.strip(),
                "last_name": payload.last_name.strip(),
                "phone": payload.phone.strip(),
            },
            "delivery": {
                "method": "own_ttn" if own_ttn else payload.delivery_method,
                "city": payload.city,
                "city_ref": payload.city_ref,
                "settlement_ref": payload.settlement_ref,
                "warehouse": payload.warehouse,
                "warehouse_ref": payload.warehouse_ref,
                "street": payload.street,
                "street_ref": payload.street_ref,
                "house": payload.house,
                "apartment": payload.apartment,
                "np_city": payload.np_city,
                "np_warehouse": payload.np_warehouse,
                "np_street": payload.np_street,
            },
            "payment": {
                "method": payload.payment_method,
                "prepay": prepay,
                "cod_amount": cod_amount,
                "prepay_balance_debit": debit,
                "receipt_name": payload.receipt_name,
            },
            "own_ttn": own_ttn,
            "own_ttn_carrier": carrier,
            "ttn_number": ttn_number,
            "ttn_pdf_name": payload.ttn_pdf_name,
            "comment": payload.comment.strip(),
            "cart": safe_cart,
            "created_by_user_id": payload.user_id.strip(),
        }

        if own_ttn:
            delivery_method = "own_ttn"
        else:
            delivery_method = payload.delivery_method

        order = storage.create_order(
            dropper_id=dropper.id,
            chat_id=dropper.chat_id,
            payment_method=payload.payment_method,
            delivery_method=delivery_method,
            own_ttn=own_ttn,
            total=total,
            prepay=prepay,
            prepay_balance_debit=debit,
            cod_amount=cod_amount,
            ttn_number=ttn_number,
            ttn_status=ttn_status,
            payload=order_payload,
        )

        if debit > 0:
            if payload.payment_method == "balance":
                storage.add_ledger_entry(
                    dropper_id=dropper.id,
                    amount=-debit,
                    entry_type="balance_payment",
                    title=f"Оплата з балансу · {order['order_number']}",
                    note="Списання суми «Дроп ціна» з балансу дроппера",
                    related_order_id=order["order_number"],
                )
            else:
                storage.add_ledger_entry(
                    dropper_id=dropper.id,
                    amount=-debit,
                    entry_type="prepay_overage_debit",
                    title=f"Передплата понад «Дроп ціна» · {order['order_number']}",
                    note="Різниця передплати і суми замовлення",
                    related_order_id=order["order_number"],
                )
            from bot.credit_holidays import evaluate_credit_holidays

            evaluate_credit_holidays(storage, dropper)

        storage.accrue_referral_from_drop_total(
            source_dropper_id=dropper.id,
            drop_total=total,
            order_id=order["order_number"],
        )

        try:
            await _notify(
                dropper.chat_id,
                _format_dropper_accept_message(order, dropper),
            )
            storage.update_order_flags(order["id"], notify_dropper_status="sent")
            order = storage.get_order(order["id"]) or order
        except Exception:
            logger.exception("Не вдалося повідомити дроппера про заказ %s", order["order_number"])
            storage.update_order_flags(order["id"], notify_dropper_status="error")

        if not own_ttn:
            from bot.np_fulfillment import fulfill_new_order

            try:
                order = await fulfill_new_order(
                    storage, order, notify=_notify, owner_notify=_notify_owners
                )
            except Exception:
                logger.exception(
                    "NP fulfill after order %s failed", order.get("order_number")
                )

        return {"ok": True, "order": order}

    @app.get("/api/dropper/orders")
    async def dropper_orders(
        chat_id: str = Query(..., max_length=64),
        limit: int = Query(50, ge=1, le=200),
    ) -> dict:
        dropper = storage.get_dropper_by_chat(chat_id)
        if not dropper:
            raise HTTPException(status_code=404, detail="Дроппера не знайдено")
        items = storage.list_orders_for_dropper(dropper.id, limit=limit)
        return {"count": len(items), "items": items}

    @app.get("/api/owner/droppers/{chat_id}/orders")
    async def owner_dropper_orders(
        chat_id: str,
        owner_chat_id: str = Query("", max_length=64),
        owner_user_id: str = Query("", max_length=64),
        limit: int = Query(50, ge=1, le=200),
    ) -> dict:
        _require_owner(owner_chat_id, owner_user_id)
        dropper = storage.get_dropper_by_chat(chat_id)
        if not dropper:
            raise HTTPException(status_code=404, detail="Дроппера не знайдено")
        items = storage.list_orders_for_dropper(dropper.id, limit=limit)
        return {
            "dropper": dropper.to_dict(),
            "count": len(items),
            "items": items,
        }

    @app.get("/api/owner/settings")
    async def get_owner_settings(
        owner_chat_id: str = Query("", max_length=64),
        owner_user_id: str = Query("", max_length=64),
    ) -> dict:
        _require_owner(owner_chat_id, owner_user_id)
        settings = storage.get_general_settings()
        enabled = storage.get_enabled_np_api_keys()
        base = (os.getenv("WEBAPP_URL") or "").rstrip("/")
        webhook_token = (os.getenv("NP_WEBHOOK_TOKEN") or "").strip()
        webhook_url = ""
        if base:
            webhook_url = f"{base}/api/np/webhook"
            if webhook_token:
                webhook_url = f"{webhook_url}?token={webhook_token}"
        return {
            "settings": settings,
            "enabled_np_keys_count": len(enabled),
            "np_webhook_url": webhook_url,
            "np_webhook_token_set": bool(webhook_token),
            "sheet_columns": [
                "Дата",
                "№ Заказа",
                "Оплата",
                "Служба доставки",
                "Название товара",
                "Код",
                "Цвет/модель",
                "Кол-во",
                "Цена продажи, грн",
                "Дроп цена, грн",
                "Источник заказа",
                "Данные клиента",
                "ТТН",
                "Статус",
                "Примечание",
                "Чек",
                "Рассчет с дроппером",
                "Расположение товара на складе",
            ],
            "note": (
                "Галочка = основний кабінет НП. Ключі без галочки — резерв при помилці основного. "
                "Статуси ТТН перевіряються автоматично раз на ~30 хв."
            ),
        }

    @app.post("/api/owner/settings")
    async def save_owner_settings(payload: GeneralSettingsUpdateRequest) -> dict:
        _require_owner(payload.owner_chat_id, payload.owner_user_id)
        saved = storage.save_general_settings(
            {
                "np_api_keys": payload.np_api_keys,
                "sender_city": payload.sender_city,
                "sender_warehouse": payload.sender_warehouse,
                "parcel_defaults": payload.parcel_defaults,
                "orders_spreadsheet_url": payload.orders_spreadsheet_url,
                "orders_spreadsheet_id": payload.orders_spreadsheet_id,
                "orders_sheet_title": payload.orders_sheet_title,
            }
        )
        return {
            "ok": True,
            "settings": saved,
            "enabled_np_keys_count": len(
                [k for k in saved.get("np_api_keys", []) if k.get("enabled") and k.get("api_key")]
            ),
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
