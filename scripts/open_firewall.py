#!/usr/bin/env python3
from __future__ import annotations

import subprocess


def allow_port(port: int) -> None:
    subprocess.run(["ufw", "allow", f"{port}/tcp"], check=True)


def deny_port(port: int) -> None:
    subprocess.run(["ufw", "--force", "delete", "allow", f"{port}/tcp"], check=True)


if __name__ == "__main__":
    allow_port(2511)
