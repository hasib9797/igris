#!/usr/bin/env python3
from __future__ import annotations

import sys

import httpx


def main() -> int:
    try:
        response = httpx.get("http://127.0.0.1:2511/api/system/health", timeout=3.0)
        return 0 if response.status_code in {200, 401} else 1
    except Exception:
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
