from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass
class CommandResult:
    command: Sequence[str]
    returncode: int
    stdout: str
    stderr: str

    def ensure_success(self, context: str = "Command failed") -> "CommandResult":
        if self.returncode != 0:
            raise RuntimeError(f"{context}: {self.stderr.strip() or self.stdout.strip() or 'unknown error'}")
        return self


def run_command(
    command: Sequence[str],
    timeout: int = 30,
    *,
    input_text: str | None = None,
    env: Mapping[str, str] | None = None,
) -> CommandResult:
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        input=input_text,
        env=dict(env) if env is not None else None,
    )
    return CommandResult(command=command, returncode=completed.returncode, stdout=completed.stdout, stderr=completed.stderr)


def run_shell(command: str, timeout: int = 30) -> CommandResult:
    completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout, shell=True, check=False)
    return CommandResult(command=[command], returncode=completed.returncode, stdout=completed.stdout, stderr=completed.stderr)


def parse_json_command(command: Sequence[str], timeout: int = 30) -> dict | list:
    result = run_command(command, timeout=timeout).ensure_success()
    return json.loads(result.stdout or "[]")
