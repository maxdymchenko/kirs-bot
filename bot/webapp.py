"""HTTP API + статика Mini App."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from bot.catalog import CatalogService

logger = logging.getLogger(__name__)

MINIAPP_DIR = Path(__file__).resolve().parent.parent / "miniapp"


def create_web_app(catalog: CatalogService) -> FastAPI:
    app = FastAPI(title="Kirs Mini App")

    @app.get("/health")
    async def health() -> dict:
        return {"ok": True}

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

    @app.get("/")
    async def miniapp_index() -> FileResponse:
        index = MINIAPP_DIR / "index.html"
        if not index.exists():
            raise HTTPException(status_code=404, detail="Mini App не найдена")
        return FileResponse(index)

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
