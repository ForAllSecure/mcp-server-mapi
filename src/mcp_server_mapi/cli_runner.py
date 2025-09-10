from __future__ import annotations
import asyncio
from typing import Sequence, Optional, Mapping
import os


class CLIRuntimeError(Exception):
    def __init__(self, msg: str, exit_code: int | None = None):
        super().__init__(msg)
        self.exit_code = exit_code


async def run_cli(
    base_cmd: Sequence[str],
    *,
    timeout_s: float = 60.0,
    max_bytes: int = 256_000,
    stdin_data: Optional[bytes] = None,
    extra_env: Optional[Mapping[str, str]] = None,
) -> str:
    """
    Run a command asynchronously with timeouts and bounded output.
    Returns stdout as text; if non-zero exit, raises CLIRuntimeError with a short stderr snippet.
    """
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)

    proc = await asyncio.create_subprocess_exec(
        *base_cmd,
        stdin=asyncio.subprocess.PIPE if stdin_data is not None else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(stdin_data), timeout=timeout_s)
    except asyncio.TimeoutError:
        proc.kill()
        raise CLIRuntimeError(f"Command timed out after {timeout_s}s")

    rc = proc.returncode
    if rc != 0:
        snippet = (stderr or b"").decode(errors="replace")[:2000]
        raise CLIRuntimeError(f"Command failed (exit {rc}): {snippet}", exit_code=rc)

    out = (stdout or b"").decode(errors="replace")
    if len(out.encode()) > max_bytes:
        out = out.encode()[:max_bytes].decode(errors="replace") + "\n[truncated]"
    return out
