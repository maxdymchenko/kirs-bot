"""HTTP API + статика Mini App."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from bot.catalog import CatalogService
from bot.novaposhta import NovaPoshtaClient, NovaPoshtaError

logger = logging.getLogger(__name__)

MINIAPP_DIR = Path(__file__).resolve().parent.parent / "miniapp"


def create_web_app(catalog: CatalogService) -> FastAPI:
    app = FastAPI(title="Kirs Mini App")
    np_client = NovaPoshtaClient()

    @app.get("/health")
    async def health() -> dict:
        return {"ok": True, "nova_poshta": np_client.configured()}

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
            raise HTTPException(
                status_code=503,
                detail="NOVA_POSHTA_API_KEY не налаштовано",
            )
        try:
            items = await asyncio.to_thread(np_client.search_settlements, q, limit)
        except NovaPoshtaError as exc:
            logger.warning("NP settlements error: %s", exc)
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
            raise HTTPException(
                status_code=503,
                detail="NOVA_POSHTA_API_KEY не налаштовано",
            )
        try:
            items = await asyncio.to_thread(
                np_client.search_warehouses, city_ref, q, limit
            )
        except NovaPoshtaError as exc:
            logger.warning("NP warehouses error: %s", exc)
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
            raise HTTPException(
                status_code=503,
                detail="NOVA_POSHTA_API_KEY не налаштовано",
            )
        if not settlement_ref.strip() and not city_ref.strip():
            raise HTTPException(
                status_code=400,
                detail="Потрібен settlement_ref або city_ref",
            )
        try:
            items = await asyncio.to_thread(
                np_client.search_streets,
                settlement_ref,
                q,
                city_ref,
                limit,
            )
        except NovaPoshtaError as exc:
            logger.warning("NP streets error: %s", exc)
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
    """Публичный HTTPS URL Mini App (Render или WEBAPP_URL)."""
    explicit = os.getenv("WEBAPP_URL", "").strip().rstrip("/")
    if explicit:
        return explicit
    render_url = os.getenv("RENDER_EXTERNAL_URL", "").strip().rstrip("/")
    if render_url:
        return render_url
    return "http://127.0.0.1:8000"
