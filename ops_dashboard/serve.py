"""Local live server: one page, one polling endpoint, and a background refresh loop.

Read-only. It only ever queries Azure and serves the result from memory.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from contextlib import asynccontextmanager
from typing import Optional

from ops_dashboard.render import page

_WAITING = (
    "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\">"
    "<meta http-equiv=\"refresh\" content=\"5\"><title>Ops dashboard</title></head>"
    "<body><p>Ops dashboard is running its first Azure query. This page reloads every 5 seconds.</p>"
    "{detail}</body></html>"
)


def create_app(engine, refresh_seconds: int = 60):
    """Build the FastAPI app. `engine` needs `refresh()`, `current()`, and `status()`."""
    from fastapi import FastAPI, Query
    from fastapi.responses import HTMLResponse, JSONResponse

    @asynccontextmanager
    async def lifespan(_app):
        task = asyncio.create_task(_loop(engine, refresh_seconds))
        try:
            yield
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    app = FastAPI(title="Ops dashboard", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/", response_class=HTMLResponse)
    async def index():
        current = engine.current()
        if current is None:
            status = engine.status()
            detail = ""
            if status.get("error"):
                from html import escape

                detail = f"<p>Last attempt failed: {escape(str(status['error']))}</p>"
            return HTMLResponse(_WAITING.format(detail=detail), status_code=503, headers=_NO_STORE)
        html = page(current.parts, live=True, version=current.version)
        return HTMLResponse(html, headers=_NO_STORE)

    @app.get("/api/report")
    async def report(version: Optional[str] = Query(default=None, max_length=32)):
        current = engine.current()
        if current is None:
            return JSONResponse({"ready": False, "status": engine.status()}, status_code=503, headers=_NO_STORE)
        if version == current.version:
            return JSONResponse(
                {"changed": False, "version": current.version, "status": current.status},
                headers=_NO_STORE,
            )
        return JSONResponse(
            {
                "changed": True,
                "version": current.version,
                "status": current.status,
                "title": current.parts.title,
                "body": current.parts.body,
                "payload": current.parts.payload,
            },
            headers=_NO_STORE,
        )

    @app.get("/api/health")
    async def health():
        status = engine.status()
        return JSONResponse(status, status_code=200 if status.get("ready") else 503, headers=_NO_STORE)

    return app


_NO_STORE = {"Cache-Control": "no-store"}


async def _loop(engine, refresh_seconds: int) -> None:
    while True:
        started = time.monotonic()
        await asyncio.to_thread(engine.refresh)
        await asyncio.sleep(max(1.0, refresh_seconds - (time.monotonic() - started)))


def run(engine, host: str, port: int, refresh_seconds: int) -> None:
    import uvicorn

    uvicorn.run(create_app(engine, refresh_seconds), host=host, port=port, log_level="warning")
