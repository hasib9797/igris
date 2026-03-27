from __future__ import annotations

import asyncio
from http.cookies import SimpleCookie
import os
import signal
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


def resolve_frontend_dist() -> Path:
    configured = os.environ.get("IGRIS_FRONTEND_DIST")
    if configured:
        return Path(configured).resolve()
    return (Path(__file__).resolve().parents[2] / "frontend" / "dist").resolve()


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
    app.state.shutdown_event = asyncio.Event()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    @app.on_event("shutdown")
    async def mark_shutdown() -> None:
        app.state.shutdown_event.set()

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

    frontend_dist = resolve_frontend_dist()
    index_file = frontend_dist / "index.html"
    if frontend_dist.exists() and index_file.exists():
        assets_dir = frontend_dist / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        @app.get("/{path:path}", response_model=None, include_in_schema=False)
        def serve_spa(path: str):
            if path == "api" or path.startswith("api/"):
                return JSONResponse({"detail": "Not found"}, status_code=404)
            if path:
                target = (frontend_dist / path).resolve()
                try:
                    target.relative_to(frontend_dist)
                except ValueError:
                    return JSONResponse({"detail": "Not found"}, status_code=404)
                if target.exists() and target.is_file():
                    return FileResponse(target)
            return FileResponse(index_file)

    @app.websocket("/api/terminal/ws")
    async def terminal_socket(websocket: WebSocket) -> None:
        process: subprocess.Popen[bytes] | None = None
        master: int | None = None
        slave: int | None = None
        username: str | None = None

        async def safe_close(code: int, message: str) -> None:
            try:
                await websocket.accept()
            except RuntimeError:
                pass
            try:
                await websocket.send_text(message)
            except Exception:
                pass
            try:
                await websocket.close(code=code)
            except Exception:
                pass

        try:
            if not get_config().system.allow_terminal:
                await safe_close(4403, "Terminal module is disabled")
                return

            cookie = SimpleCookie()
            cookie.load(websocket.headers.get("cookie", ""))
            session_token = cookie[COOKIE_NAME].value if COOKIE_NAME in cookie else None
            username = decode_session(session_token)
            if not username:
                await safe_close(4401, "Authentication required")
                return

            with get_session_factory()() as session:
                user = session.scalar(select(AdminUser).where(AdminUser.username == username))
                if not user:
                    await safe_close(4401, "Authentication required")
                    return
                log_audit(session, actor=username, action="terminal.session_open")

            await websocket.accept()

            try:
                import pty
            except ImportError:
                await websocket.send_text("Terminal module is unavailable on this platform")
                await websocket.close(code=4403)
                return

            master, slave = pty.openpty()
            process = subprocess.Popen(
                ["/bin/bash"],
                stdin=slave,
                stdout=slave,
                stderr=slave,
                text=False,
                close_fds=True,
                start_new_session=True,
            )

            async def reader() -> None:
                assert master is not None
                while True:
                    try:
                        data = os.read(master, 1024)
                    except OSError:
                        break
                    if not data:
                        break
                    try:
                        await websocket.send_text(data.decode(errors="ignore"))
                    except Exception:
                        break

            async def writer() -> None:
                assert master is not None
                while True:
                    try:
                        message = await websocket.receive_text()
                    except WebSocketDisconnect:
                        break
                    except RuntimeError:
                        break
                    try:
                        os.write(master, message.encode())
                    except OSError:
                        break

            reader_task = asyncio.create_task(reader())
            writer_task = asyncio.create_task(writer())
            shutdown_task = asyncio.create_task(app.state.shutdown_event.wait())
            done, pending = await asyncio.wait({reader_task, writer_task, shutdown_task}, return_when=asyncio.FIRST_COMPLETED)
            if shutdown_task in done:
                try:
                    await websocket.close(code=1001)
                except Exception:
                    pass
            for task in pending:
                task.cancel()
            for task in done:
                try:
                    await task
                except Exception:
                    pass
        except Exception:
            try:
                await websocket.close(code=1011)
            except Exception:
                pass
        finally:
            if username:
                with get_session_factory()() as session:
                    log_audit(session, actor=username, action="terminal.session_close")
            if process is not None:
                if process.poll() is None:
                    try:
                        os.killpg(process.pid, signal.SIGTERM)
                    except Exception:
                        process.terminate()
                    try:
                        process.wait(timeout=2)
                    except Exception:
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except Exception:
                            process.kill()
            for fd in (master, slave):
                if fd is not None:
                    try:
                        os.close(fd)
                    except OSError:
                        pass

    return app


app = create_app()
