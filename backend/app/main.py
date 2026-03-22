from __future__ import annotations

import asyncio
from http.cookies import SimpleCookie
import os
import pty
import subprocess
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from backend.app.api.routes import router
from backend.app.auth.session import COOKIE_NAME, decode_session
from backend.app.config import get_config
from backend.app.db.session import Base, get_engine, get_session_factory, init_database
from backend.app.models import AdminUser
from backend.app.utils.audit import log_audit


def create_app() -> FastAPI:
    config = get_config()
    init_database()
    Base.metadata.create_all(bind=get_engine())
    with get_session_factory()() as session:
        admin = session.scalar(select(AdminUser).where(AdminUser.username == config.auth.admin_username))
        if config.auth.password_hash:
            if not admin:
                session.add(AdminUser(username=config.auth.admin_username, password_hash=config.auth.password_hash))
                session.commit()
            elif admin.password_hash != config.auth.password_hash:
                admin.password_hash = config.auth.password_hash
                session.commit()

    app = FastAPI(title="Igris", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    @app.exception_handler(RuntimeError)
    async def handle_runtime_error(_, exc: RuntimeError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(PermissionError)
    async def handle_permission_error(_, exc: PermissionError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @app.exception_handler(FileNotFoundError)
    async def handle_not_found(_, exc: FileNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ValueError)
    async def handle_value_error(_, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": exc.errors()})

    frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if frontend_dist.exists():
        assets_dir = frontend_dist / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        @app.get("/{path:path}")
        def serve_spa(path: str) -> FileResponse | JSONResponse:
            if path.startswith("api/"):
                return JSONResponse({"detail": "Not found"}, status_code=404)
            target = frontend_dist / path
            if target.exists() and target.is_file():
                return FileResponse(target)
            return FileResponse(frontend_dist / "index.html")

    @app.websocket("/api/terminal/ws")
    async def terminal_socket(websocket: WebSocket) -> None:
        if not get_config().system.allow_terminal:
            await websocket.accept()
            await websocket.send_text("Terminal module is disabled")
            await websocket.close(code=4403)
            return

        cookie = SimpleCookie()
        cookie.load(websocket.headers.get("cookie", ""))
        session_token = cookie[COOKIE_NAME].value if COOKIE_NAME in cookie else None
        username = decode_session(session_token)
        if not username:
            await websocket.accept()
            await websocket.send_text("Authentication required")
            await websocket.close(code=4401)
            return

        with get_session_factory()() as session:
            user = session.scalar(select(AdminUser).where(AdminUser.username == username))
            if not user:
                await websocket.accept()
                await websocket.send_text("Authentication required")
                await websocket.close(code=4401)
                return
            log_audit(session, actor=username, action="terminal.session_open")

        await websocket.accept()

        master, slave = pty.openpty()
        process = subprocess.Popen(
            ["/bin/bash"],
            stdin=slave,
            stdout=slave,
            stderr=slave,
            text=False,
            close_fds=True,
        )

        async def reader() -> None:
            while True:
                data = os.read(master, 1024)
                if not data:
                    break
                await websocket.send_text(data.decode(errors="ignore"))

        async def writer() -> None:
            while True:
                message = await websocket.receive_text()
                os.write(master, message.encode())

        try:
            await asyncio.gather(reader(), writer())
        except WebSocketDisconnect:
            pass
        finally:
            with get_session_factory()() as session:
                log_audit(session, actor=username, action="terminal.session_close")
            process.terminate()
            os.close(master)
            os.close(slave)

    return app


app = create_app()

