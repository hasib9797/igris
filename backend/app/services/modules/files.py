from __future__ import annotations

import grp
import pwd
import shutil
import stat
from datetime import datetime
from pathlib import Path


SAFE_ROOTS = [Path("/etc"), Path("/var/log"), Path("/home"), Path("/opt"), Path("/srv"), Path("/tmp")]


def _ensure_allowed(path: str) -> Path:
    target = Path(path).expanduser().resolve(strict=False)
    if not any(root in target.parents or target == root for root in SAFE_ROOTS):
        raise PermissionError(f"Path {target} is outside allowed roots")
    return target


def list_path(path: str) -> list[dict]:
    target = _ensure_allowed(path)
    if not target.exists() or not target.is_dir():
        raise FileNotFoundError(f"Directory not found: {target}")
    items = []
    for item in sorted(target.iterdir(), key=lambda entry: entry.name):
        info = item.stat()
        items.append(
            {
                "path": str(item),
                "type": "directory" if item.is_dir() else "file",
                "size": info.st_size,
                "owner": pwd.getpwuid(info.st_uid).pw_name,
                "group": grp.getgrgid(info.st_gid).gr_name,
                "permissions": stat.filemode(info.st_mode),
                "modified_at": datetime.fromtimestamp(info.st_mtime).isoformat(),
            }
        )
    return items


def read_file(path: str) -> dict:
    target = _ensure_allowed(path)
    if not target.exists() or not target.is_file():
        raise FileNotFoundError(f"File not found: {target}")
    info = target.stat()
    return {
        "path": str(target),
        "content": target.read_text(encoding="utf-8"),
        "size": info.st_size,
        "permissions": stat.filemode(info.st_mode),
    }


def write_file(path: str, content: str, create_backup: bool = True) -> None:
    target = _ensure_allowed(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if create_backup and target.exists():
        shutil.copy2(target, target.with_suffix(target.suffix + ".bak"))
    target.write_text(content, encoding="utf-8")


def delete_path(path: str) -> None:
    target = _ensure_allowed(path)
    if target in SAFE_ROOTS:
        raise PermissionError(f"Refusing to delete protected root: {target}")
    if target.is_dir():
        shutil.rmtree(target)
    elif target.exists():
        target.unlink()


def make_directory(path: str) -> None:
    target = _ensure_allowed(path)
    target.mkdir(parents=True, exist_ok=True)
