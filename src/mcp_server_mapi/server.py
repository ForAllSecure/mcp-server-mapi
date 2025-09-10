from __future__ import annotations
import os
import sys
import logging
from typing import Literal, List, Optional

from pydantic import BaseModel, Field, model_validator, field_validator
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


# -----------------------------
# Pydantic schema for `mapi discover`
# -----------------------------
class DiscoverArgs(BaseModel):
    # FLAGS
    verify_tls: bool = Field(False, description="--verify-tls")
    disable_oauth2: bool = Field(False, description="--disable-oauth2")
    disable_auth_mutations: bool = Field(False, description="--disable-auth-mutations")
    no_builtin_endpoints: bool = Field(False, description="--no-builtin-endpoints")

    # OPTIONS (single)
    url: Optional[str] = Field(None, description="--url <parsed-url>")
    cacert: Optional[str] = Field(None, description="--cacert <ca-cert>")
    cert: Optional[str] = Field(None, description="--cert <cert>")
    key: Optional[str] = Field(None, description="--key <key>")
    p12cert: Optional[str] = Field(None, description="--p12cert <p12cert>")
    p12password: Optional[str] = Field(None, description="--p12password <p12password>")

    basic_auth: Optional[str] = Field(None, description='--basic-auth "username:password"')
    endpoints_file: Optional[str] = Field(None, description="--endpoints-file <file>")
    output_dir: str = Field("api-specs", description="--output <output-dir> (default api-specs)")
    request_timeout: str = Field("5 seconds", description='--request-timeout (e.g., "1m42s", "5s") - only required for very slow hosts')
    rate_limit: int = Field(1000, ge=1, description="--rate-limit <int> (default 1000)")

    # OPTIONS (repeatable)
    header: List[str] = Field(default_factory=list, description='-H/--header "k:v" (repeatable)')
    cookie_auth: List[str] = Field(default_factory=list, description='--cookie-auth "k=v"...')
    header_auth: List[str] = Field(default_factory=list, description='--header-auth "k:v"...')
    query_auth: List[str] = Field(default_factory=list, description='--query-auth "k:v"...')
    redact_header: List[str] = Field(default_factory=list, description='--redact-header "name"...')

    # Target selection (mutually exclusive)
    hosts: Optional[List[str]] = Field(None, description='-h/--hosts "host1,host2" (best option to start with, just make sure to *not* include schemes/ports/paths when specifying the option)')
    cidrs: Optional[List[str]] = Field(None, description='--cidrs "10.0.0.0/24,10.0.1.0/24"')
    domains: Optional[List[str]] = Field(None, description='--domains "example.com,foo.com"')

    # Network tuning (comma-separated in CLI; model as lists)
    ports: List[int] = Field(default_factory=lambda: [80, 443], description="--ports 80,443")
    schemes: List[Literal["http", "https"]] = Field(default_factory=lambda: ["http", "https"],
                                                    description="--schemes http,https")

    # OAuth2 (optional; many fields)
    oauth2_client_data: Optional[str] = Field(None, description='--oauth2-client-data "id:secret"')
    oauth2_credentials: Optional[str] = Field(None, description='--oauth2-credentials "user:pass"')

    oauth2_auth_code_auth_url: Optional[str] = None
    oauth2_auth_code_token_url: Optional[str] = None
    oauth2_auth_code_refresh_url: Optional[str] = None
    oauth2_auth_code_scopes: List[str] = Field(default_factory=list)

    oauth2_implicit_auth_url: Optional[str] = None
    oauth2_implicit_refresh_url: Optional[str] = None
    oauth2_implicit_scopes: List[str] = Field(default_factory=list)

    oauth2_cc_token_url: Optional[str] = None
    oauth2_cc_refresh_url: Optional[str] = None
    oauth2_cc_scopes: List[str] = Field(default_factory=list)

    oauth2_password_token_url: Optional[str] = None
    oauth2_password_refresh_url: Optional[str] = None
    oauth2_password_scopes: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_targets(self):
        # hosts vs cidrs vs domains are mutually exclusive (but all optional)
        groups = [bool(self.hosts), bool(self.cidrs), bool(self.domains)]
        if sum(groups) > 1:
            raise ValueError("Choose at most one of: hosts, cidrs, domains")
        return self


def _add_flag(argv: list[str], cond: bool, flag: str):
    if cond:
        argv.append(flag)


def _add_opt(argv: list[str], flag: str, val: Optional[str | int]):
    if val is None:
        return
    argv += [flag, str(val)]


def _add_repeat(argv: list[str], flag: str, values: List[str | int]):
    for v in values:
        argv += [flag, str(v)]


def _comma_join(values: List[str | int]) -> str:
    return ",".join(str(v) for v in values)


# -----------------------------
# MCP tool for `mapi discover`
# -----------------------------
@mcp.tool(description="Run `mapi discover` with the provided options.")
async def mapi_discover(ctx: Context, args: DiscoverArgs) -> str:
    cmd: list[str] = [MAPI_BIN, "discover"]

    # FLAGS
    _add_flag(cmd, args.verify_tls, "--verify-tls")
    _add_flag(cmd, args.disable_oauth2, "--disable-oauth2")
    _add_flag(cmd, args.disable_auth_mutations, "--disable-auth-mutations")
    _add_flag(cmd, args.no_builtin_endpoints, "--no-builtin-endpoints")

    # SIMPLE OPTIONS
    _add_opt(cmd, "--url", args.url)
    _add_opt(cmd, "--cacert", args.cacert)
    _add_opt(cmd, "--cert", args.cert)
    _add_opt(cmd, "--key", args.key)
    _add_opt(cmd, "--p12cert", args.p12cert)
    _add_opt(cmd, "--p12password", args.p12password)
    _add_opt(cmd, "--basic-auth", args.basic_auth)
    _add_opt(cmd, "--endpoints-file", args.endpoints_file)
    _add_opt(cmd, "--output", args.output_dir)
    _add_opt(cmd, "--request-timeout", args.request_timeout)
    _add_opt(cmd, "--rate-limit", args.rate_limit)

    # REPEATABLES
    _add_repeat(cmd, "--header", args.header)
    _add_repeat(cmd, "--cookie-auth", args.cookie_auth)
    _add_repeat(cmd, "--header-auth", args.header_auth)
    _add_repeat(cmd, "--query-auth", args.query_auth)
    _add_repeat(cmd, "--redact-header", args.redact_header)

    # TARGET SELECTION (mutually exclusive)
    if args.hosts:
        _add_opt(cmd, "--hosts", _comma_join(args.hosts))
    if args.cidrs:
        _add_opt(cmd, "--cidrs", _comma_join(args.cidrs))
    if args.domains:
        _add_opt(cmd, "--domains", _comma_join(args.domains))

    # NETWORK
    if args.ports:
        _add_opt(cmd, "--ports", _comma_join(args.ports))
    if args.schemes:
        _add_opt(cmd, "--schemes", _comma_join(args.schemes))

    # OAUTH2 (Authorization Code)
    _add_opt(cmd, "--oauth2-client-data", args.oauth2_client_data)
    _add_opt(cmd, "--oauth2-credentials", args.oauth2_credentials)

    _add_opt(cmd, "--oauth2-authorization-code-auth-url", args.oauth2_auth_code_auth_url)
    _add_opt(cmd, "--oauth2-authorization-code-token-url", args.oauth2_auth_code_token_url)
    _add_opt(cmd, "--oauth2-authorization-code-refresh-url", args.oauth2_auth_code_refresh_url)
    _add_repeat(cmd, "--oauth2-authorization-code-scopes", args.oauth2_auth_code_scopes)

    # OAUTH2 (Implicit)
    _add_opt(cmd, "--oauth2-implicit-auth-url", args.oauth2_implicit_auth_url)
    _add_opt(cmd, "--oauth2-implicit-refresh-url", args.oauth2_implicit_refresh_url)
    _add_repeat(cmd, "--oauth2-implicit-scopes", args.oauth2_implicit_scopes)

    # OAUTH2 (Client Credentials)
    _add_opt(cmd, "--oauth2-client-credentials-token-url", args.oauth2_cc_token_url)
    _add_opt(cmd, "--oauth2-client-credentials-refresh-url", args.oauth2_cc_refresh_url)
    _add_repeat(cmd, "--oauth2-client-credentials-scopes", args.oauth2_cc_scopes)

    # OAUTH2 (Password)
    _add_opt(cmd, "--oauth2-password-token-url", args.oauth2_password_token_url)
    _add_opt(cmd, "--oauth2-password-refresh-url", args.oauth2_password_refresh_url)
    _add_repeat(cmd, "--oauth2-password-scopes", args.oauth2_password_scopes)

    # Run it
    log.info("Running: %s", " ".join(cmd))
    try:
        return await run_cli(cmd, timeout_s=600.0)
    except CLIRuntimeError as e:
        raise RuntimeError(str(e)) from None


# -----------------------------
# Pydantic schema for `mapi run`
# -----------------------------
class RunArgs(BaseModel):
    # --- required positional args ---
    api_target: str = Field(..., description="<api-target> (project/target name to push results to, e.g., 'projectname/targetname')")
    duration: str = Field(..., description="<duration> e.g., 'auto', '30s', '2h20m' - strongly recommend 'auto'")
    specification: str = Field(..., description="<specification> path to OpenAPI/Swagger/Postman/HAR file on disk")

    # --- flags ---
    verify_tls: bool = False
    skip_sanity_check_abort: bool = False
    no_replay: bool = False
    disable_oauth2: bool = False
    disable_auth_mutations: bool = False
    experimental_rules: bool = False
    no_auto_ignore_rules: bool = False
    warn_as_error: bool = Field(False, description="--warnaserror")
    interactive: bool = False
    disable_github_report_comment: bool = False
    skip_scm_detection: bool = False
    mutable_postman_variables: bool = False
    zap: bool = False
    local: bool = Field(False, description="--local (for local scans, requires enterprise plan)")

    # --- simple options ---
    url: Optional[str] = None
    min_request_count: Optional[int] = Field(None, ge=1)
    concurrency: Optional[int] = Field(None, ge=1)
    rate_limit: Optional[int] = Field(None, ge=1)
    max_memory_usage: str = Field("80%", description='e.g., "60%" or "6GB"')
    max_response_size: str = Field("100KB", description='e.g., "100B", "500KB"')
    cacert: Optional[str] = None
    cert: Optional[str] = None
    key: Optional[str] = None
    previous_job: Optional[str] = None

    junit: Optional[str] = None
    html: Optional[str] = None
    sarif: Optional[str] = None

    config: Optional[str] = None
    har: Optional[str] = None
    github_api_url: str = Field("https://api.github.com", description="--github-api-url <url> (typically not required to be set)")
    scm_remote: Optional[str] = None
    scm_branch: Optional[str] = None
    scm_parent_sha: Optional[str] = None
    scm_commit_sha: Optional[str] = None
    scm_tag: Optional[str] = None

    rewrite_plugin: Optional[str] = None
    classify_plugin: Optional[str] = None

    postman_api_key: Optional[str] = None
    postman_environment_id: Optional[str] = None
    postman_global_variables: Optional[str] = None

    zap_min_risk_code: int = Field(1, ge=0, le=3)
    zap_import_json_results: Optional[str] = None
    zap_docker_tag: str = Field("zaproxy/zap-stable:2.14.0")

    upload_sample_requests_per_endpoint: int = Field(5, ge=0)

    request_timeout: str = Field("5 seconds")

    basic_auth: Optional[str] = None

    # --- repeatables ---
    header: List[str] = Field(default_factory=list)                # -H/--header
    cookie_auth: List[str] = Field(default_factory=list)           # --cookie-auth
    header_auth: List[str] = Field(default_factory=list)           # --header-auth
    query_auth: List[str] = Field(default_factory=list)            # --query-auth
    resource_hint: List[str] = Field(default_factory=list)         # --resource-hint
    include_endpoint: List[str] = Field(default_factory=list)      # --include-endpoint
    ignore_endpoint: List[str] = Field(default_factory=list)       # --ignore-endpoint
    include_endpoints_by_tag: List[str] = Field(default_factory=list)
    ignore_endpoints_by_tag: List[str] = Field(default_factory=list)
    include_rule: List[str] = Field(default_factory=list)          # --include-rule
    ignore_rule: List[str] = Field(default_factory=list)           # --ignore-rule
    redact_header: List[str] = Field(default_factory=list)         # --redact-header

    # --- OAuth2 family (mirrors discover) ---
    oauth2_client_data: Optional[str] = None
    oauth2_credentials: Optional[str] = None

    oauth2_auth_code_auth_url: Optional[str] = None
    oauth2_auth_code_token_url: Optional[str] = None
    oauth2_auth_code_refresh_url: Optional[str] = None
    oauth2_auth_code_scopes: List[str] = Field(default_factory=list)

    oauth2_implicit_auth_url: Optional[str] = None
    oauth2_implicit_refresh_url: Optional[str] = None
    oauth2_implicit_scopes: List[str] = Field(default_factory=list)

    oauth2_cc_token_url: Optional[str] = None
    oauth2_cc_refresh_url: Optional[str] = None
    oauth2_cc_scopes: List[str] = Field(default_factory=list)

    oauth2_password_token_url: Optional[str] = None
    oauth2_password_refresh_url: Optional[str] = None
    oauth2_password_scopes: List[str] = Field(default_factory=list)

    p12cert: Optional[str] = None
    p12password: Optional[str] = None

    @field_validator("duration")
    @classmethod
    def _duration_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("duration must be non-empty (e.g., 'auto', '30s', '2h20m')")
        return v

# -----------------------------
# MCP tool for `mapi run`
# -----------------------------
@mcp.tool(description="Run `mapi run` with the provided options.")
async def mapi_run(ctx: Context, args: RunArgs) -> str:
    cmd: list[str] = [MAPI_BIN, "run"]

    # first, the required positionals:
    cmd += [args.api_target, args.duration, args.specification]

    # flags
    _add_flag(cmd, args.verify_tls, "--verify-tls")
    _add_flag(cmd, args.skip_sanity_check_abort, "--skip-sanity-check-abort")
    _add_flag(cmd, args.no_replay, "--no-replay")
    _add_flag(cmd, args.disable_oauth2, "--disable-oauth2")
    _add_flag(cmd, args.disable_auth_mutations, "--disable-auth-mutations")
    _add_flag(cmd, args.experimental_rules, "--experimental-rules")
    _add_flag(cmd, args.no_auto_ignore_rules, "--no-auto-ignore-rules")
    _add_flag(cmd, args.warn_as_error, "--warnaserror")
    _add_flag(cmd, args.interactive, "--interactive")
    _add_flag(cmd, args.disable_github_report_comment, "--disable-github-report-comment")
    _add_flag(cmd, args.skip_scm_detection, "--skip-scm-detection")
    _add_flag(cmd, args.mutable_postman_variables, "--mutable-postman-variables")
    _add_flag(cmd, args.zap, "--zap")
    _add_flag(cmd, args.local, "--local")

    # options
    _add_opt(cmd, "--url", args.url)
    _add_opt(cmd, "--min-request-count", args.min_request_count)
    _add_opt(cmd, "--concurrency", args.concurrency)
    _add_opt(cmd, "--rate-limit", args.rate_limit)
    _add_opt(cmd, "--max-memory-usage", args.max_memory_usage)
    _add_opt(cmd, "--max-response-size", args.max_response_size)
    _add_opt(cmd, "--cacert", args.cacert)
    _add_opt(cmd, "--cert", args.cert)
    _add_opt(cmd, "--key", args.key)
    _add_opt(cmd, "--previous-job", args.previous_job)

    _add_opt(cmd, "--junit", args.junit)
    _add_opt(cmd, "--html", args.html)
    _add_opt(cmd, "--sarif", args.sarif)

    _add_opt(cmd, "--config", args.config)
    _add_opt(cmd, "--har", args.har)
    _add_opt(cmd, "--github-api-url", args.github_api_url)

    _add_opt(cmd, "--scm-remote", args.scm_remote)
    _add_opt(cmd, "--scm-branch", args.scm_branch)
    _add_opt(cmd, "--scm-parent-sha", args.scm_parent_sha)
    _add_opt(cmd, "--scm-commit-sha", args.scm_commit_sha)
    _add_opt(cmd, "--scm-tag", args.scm_tag)

    _add_opt(cmd, "--rewrite-plugin", args.rewrite_plugin)
    _add_opt(cmd, "--classify-plugin", args.classify_plugin)

    _add_opt(cmd, "--postman-api-key", args.postman_api_key)
    _add_opt(cmd, "--postman-environment-id", args.postman_environment_id)
    _add_opt(cmd, "--postman-global-variables", args.postman_global_variables)

    _add_opt(cmd, "--zap-min-risk-code", args.zap_min_risk_code)
    _add_opt(cmd, "--zap-import-json-results", args.zap_import_json_results)
    _add_opt(cmd, "--zap-docker-tag", args.zap_docker_tag)

    _add_opt(cmd, "--upload-sample-requests-per-endpoint", args.upload_sample_requests_per_endpoint)

    _add_opt(cmd, "--request-timeout", args.request_timeout)

    _add_opt(cmd, "--basic-auth", args.basic_auth)

    # repeatables
    _add_repeat(cmd, "--header", args.header)
    _add_repeat(cmd, "--cookie-auth", args.cookie_auth)
    _add_repeat(cmd, "--header-auth", args.header_auth)
    _add_repeat(cmd, "--query-auth", args.query_auth)
    _add_repeat(cmd, "--resource-hint", args.resource_hint)

    _add_repeat(cmd, "--include-endpoint", args.include_endpoint)
    _add_repeat(cmd, "--ignore-endpoint", args.ignore_endpoint)
    _add_repeat(cmd, "--include-endpoints-by-tag", args.include_endpoints_by_tag)
    _add_repeat(cmd, "--ignore-endpoints-by-tag", args.ignore_endpoints_by_tag)

    _add_repeat(cmd, "--include-rule", args.include_rule)
    _add_repeat(cmd, "--ignore-rule", args.ignore_rule)
    _add_repeat(cmd, "--redact-header", args.redact_header)

    # OAuth2
    _add_opt(cmd, "--oauth2-client-data", args.oauth2_client_data)
    _add_opt(cmd, "--oauth2-credentials", args.oauth2_credentials)

    _add_opt(cmd, "--oauth2-authorization-code-auth-url", args.oauth2_auth_code_auth_url)
    _add_opt(cmd, "--oauth2-authorization-code-token-url", args.oauth2_auth_code_token_url)
    _add_opt(cmd, "--oauth2-authorization-code-refresh-url", args.oauth2_auth_code_refresh_url)
    _add_repeat(cmd, "--oauth2-authorization-code-scopes", args.oauth2_auth_code_scopes)

    _add_opt(cmd, "--oauth2-implicit-auth-url", args.oauth2_implicit_auth_url)
    _add_opt(cmd, "--oauth2-implicit-refresh-url", args.oauth2_implicit_refresh_url)
    _add_repeat(cmd, "--oauth2-implicit-scopes", args.oauth2_implicit_scopes)

    _add_opt(cmd, "--oauth2-client-credentials-token-url", args.oauth2_cc_token_url)
    _add_opt(cmd, "--oauth2-client-credentials-refresh-url", args.oauth2_cc_refresh_url)
    _add_repeat(cmd, "--oauth2-client-credentials-scopes", args.oauth2_cc_scopes)

    _add_opt(cmd, "--oauth2-password-token-url", args.oauth2_password_token_url)
    _add_opt(cmd, "--oauth2-password-refresh-url", args.oauth2_password_refresh_url)
    _add_repeat(cmd, "--oauth2-password-scopes", args.oauth2_password_scopes)

    _add_opt(cmd, "--p12cert", args.p12cert)
    _add_opt(cmd, "--p12password", args.p12password)

    log.info("Running: %s", " ".join(cmd))
    try:
        # mapi runs can be long; give them room
        return await run_cli(cmd, timeout_s=3600)  # 1 hour cap; adjust as needed
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
