from __future__ import annotations

import pwd
import re

from backend.app.services.command import run_command


USERNAME_RE = re.compile(r"^[a-z_][a-z0-9_-]*[$]?$", re.IGNORECASE)


def _validate_username(username: str) -> str:
    if not USERNAME_RE.fullmatch(username):
        raise ValueError("Invalid username")
    return username


def list_users() -> list[dict]:
    users = []
    for entry in pwd.getpwall():
        if entry.pw_uid >= 1000 or entry.pw_name == "root":
            users.append(
                {
                    "username": entry.pw_name,
                    "uid": entry.pw_uid,
                    "gid": entry.pw_gid,
                    "home": entry.pw_dir,
                    "shell": entry.pw_shell,
                }
            )
    return users


def create_user(username: str, shell: str, home: str | None = None) -> None:
    username = _validate_username(username)
    command = ["useradd", "-m", "-s", shell]
    if home:
        command.extend(["-d", home])
    command.append(username)
    run_command(command, timeout=30).ensure_success("Unable to create user")


def delete_user(username: str) -> None:
    username = _validate_username(username)
    if username == "root":
        raise ValueError("Refusing to delete root")
    run_command(["userdel", "-r", username], timeout=60).ensure_success("Unable to delete user")


def lock_user(username: str) -> None:
    username = _validate_username(username)
    if username == "root":
        raise ValueError("Refusing to lock root")
    run_command(["usermod", "-L", username], timeout=20).ensure_success("Unable to lock user")


def unlock_user(username: str) -> None:
    username = _validate_username(username)
    run_command(["usermod", "-U", username], timeout=20).ensure_success("Unable to unlock user")


def set_password(username: str, password: str) -> None:
    username = _validate_username(username)
    run_command(["chpasswd"], timeout=20, input_text=f"{username}:{password}\n").ensure_success("Unable to reset password")


def set_sudo(username: str, enabled: bool) -> None:
    username = _validate_username(username)
    if enabled:
        run_command(["usermod", "-aG", "sudo", username], timeout=20).ensure_success("Unable to grant sudo")
    else:
        run_command(["gpasswd", "-d", username, "sudo"], timeout=20).ensure_success("Unable to revoke sudo")
