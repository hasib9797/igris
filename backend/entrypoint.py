from __future__ import annotations

import uvicorn

from backend.app.config import get_config


def main() -> None:
    config = get_config()
    uvicorn.run("backend.app.main:app", host=config.server.host, port=config.server.port, reload=False, workers=1)


if __name__ == "__main__":
    main()

