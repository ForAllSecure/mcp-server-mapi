from __future__ import annotations
import os
import sys
import logging
from typing import Literal, List, Optional

from pydantic import BaseModel, Field, model_validator
from mcp.server.fastmcp import FastMCP, Context

# --- Logging: IMPORTANT ---
# Never write to stdout on stdio servers (keeps JSON-RPC clean).
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("mcp_server_mapi")

from .cli_runner import run_cli, CLIRuntimeError

MAPI_BIN = os.environ.get("MAPI_BIN", "/usr/local/bin/mapi")  # override in env if needed
mcp = FastMCP("MAPI Server")

# --------- Tool input models ---------

class FooArgs(BaseModel):
    query: str = Field(..., description="Query string for the 'foo' subcommand.")
    limit: int = Field(10, ge=1, le=1000, description="Maximum items.")
    verbose: int = Field(0, ge=0, le=3, description="Verbosity level; renders as -v repeated.")
    tags: List[str] = Field(default_factory=list, description="--tag <value> (repeatable)")
    exact: bool = Field(False, description="Use --exact flag")
    fmt: Literal["json", "text"] = Field("json", description="--format")
    extra: List[str] = Field(default_factory=list, description="Advanced pass-through args")

@mcp.tool(description="Run the CLI 'foo' subcommand to search/list things.")
async def run_foo(ctx: Context, args: FooArgs) -> str:
    cmd = [MAPI_BIN, "foo", "--limit", str(args.limit), "--format", args.fmt]
    if args.exact:
        cmd.append("--exact")
    cmd += ["-v"] * args.verbose
    for t in args.tags:
        cmd += ["--tag", t]
    cmd += ["--query", args.query]
    cmd += args.extra
    log.info("Running: %s", " ".join(cmd))
    try:
        return await run_cli(cmd, timeout_s=60.0)
    except CLIRuntimeError as e:
        raise RuntimeError(str(e)) from None


class BarArgs(BaseModel):
    id: Optional[str] = None
    file: Optional[str] = None
    dry_run: bool = False
    timeout_s: int = Field(30, ge=1, le=300)

    @model_validator(mode="after")
    def _one_of_id_or_file(self):
        if bool(self.id) == bool(self.file):
            raise ValueError("Provide exactly one of: id OR file")
        return self

@mcp.tool(description="Run the CLI 'bar' subcommand to fetch a record.")
async def run_bar(ctx: Context, args: BarArgs) -> str:
    cmd = [MAPI_BIN, "bar"]
    if args.id:
        cmd += ["--id", args.id]
    if args.file:
        cmd += ["--file", args.file]
    if args.dry_run:
        cmd.append("--dry-run")
    log.info("Running: %s", " ".join(cmd))
    try:
        return await run_cli(cmd, timeout_s=float(args.timeout_s))
    except CLIRuntimeError as e:
        raise RuntimeError(str(e)) from None


async def version() -> str:
    try:
        out = await run_cli([MAPI_BIN, "--version"], timeout_s=10.0, max_bytes=32_000)
    except Exception as e:
        out = f"(error retrieving version) {e}"
    return f"server=MAPI Server; mapi_bin={MAPI_BIN}; mapi_version={out.strip()}"


def main():
    if os.environ.get("MAYHEM_TOKEN") is None:
        log.error("MAYHEM_TOKEN not set; cannot start MAPI server")
        sys.exit(1)
    log.info("Starting MAPI Server on stdio...")
    mcp.run(transport="stdio")
