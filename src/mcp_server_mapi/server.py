import logging
import subprocess
import shlex
import os
from pydantic import BaseModel, Field
from enum import Enum
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from pathlib import Path


class Rule(str, Enum):
    AUTH_BYPASS = "auth-bypass"
    DEFAULT_CREDENTIALS = "default-credentials"
    COMMAND_INJECTION = "command-injection"
    INTERNAL_SERVER_ERROR = "internal-server-error"
    INVALID_REQUEST_SPEC = "invalid-request-spec"
    INVALID_RESPONSE_SPEC = "invalid-response-spec"
    PATH_TRAVERSAL = "path-traversal"
    SERVER_CRASH = "server-crash"
    SQL_INJECTION = "sql-injection"
    SSRF = "ssrf"
    TIMEOUT = "timeout"
    VERB_TAMPERING = "verb-tampering"
    XSS = "xss"


class MapiRunOptions(BaseModel):
    url: str = Field(description="""The target URL to analyze""")

    include_rules: list[Rule] | None = Field(
        description="""
Include only specific rules. By default, we will include the following rules:
- auth-bypass: An API endpoint marked as secure in the API specification returns a successful response given invalid or missing credentials.
- default-credentials: An API endpoint marked as secure in the API specification returns a successful response using well-known default credentials.
- command-injection: Command Injection detection.
- internal-server-error: The API returned an Internal Server Error (status code >= 500) indicating an unhandled exception.
- invalid-request-spec:  The server accepted a payload which wasn't valid according to the provide spec.            
- invalid-response-spec: The response from the API was not described in the provided spec.
- path-traversal: Accessing paths influenced by users can allow an attacker to access unexpected resources.
- server-crash: A server that can be forced to crash may be vulnerable to denial-of-service attacks.
- sql-injection: Error-based SQL Injection detection.
- ssrf: Server-side request forgery - service is vulnerable to unauthorized access of private services.
- timeout: No response was received from the API before the timeout elapsed.            
- verb-tampering: The API responds to methods that are invalid and/or not in the API specification.
- xss: The API emits unsanitized user input in HTML responses.
"""
    )

    ignore_rules: list[Rule] | None = Field(
        description="""Ignore specific rules. By default, we will apply all rules."""
    )

    zap: bool = Field(
        description="""[Requires Docker] Run ZAP - API Scan in addition to Mayhem for API."""
    )

    har: str | None = Field(
        description="""HTTP Archive (HAR) file to record details of the run"""
    )

    header_auth: list[str] | None = Field(
        description="""Authorization headers to use with mapi. Use this when dealing with an API that requires authentication.
        Must be in the following format <header_key>:<header_value>.
        """
    )

    replay_issues: bool = Field(
        description="Replay previous mapi issues. Default is false. Usually you should provide true if the user asks to."
    )

    def command_line(self) -> str:
        options = [f"--url={self.url}"]

        if self.include_rules:
            options.extend([f"--include-rule={rule.value}" for rule in self.include_rules])

        if self.ignore_rules:
            options.extend([f"--ignore-rule={rule.value}" for rule in self.ignore_rules])

        if self.har:
            options.append(f"--har={self.har}")

        if self.zap:
            options.append("--zap")

        if not self.replay_issues:
            options.append("--no-replay")

        if self.header_auth:
            for auth in self.header_auth:
                options.append(shlex.quote(f"--header-auth={auth}"))

        return " ".join(options)


class MapiRun(BaseModel):
    duration: str = Field(
        description="""
How long to run. Longer runs will discover more edge cases in your API.
    Examples:
        - Automatic                          [auto]
        - Run for 30 seconds                 [30s or 30sec]
        - Run for 90 minutes                 [90m or 90min]
        - Run for 1 hour                     [1h  or 1hr]
        - Run for 2 hours and 20 minutes     [2h20m]
"""
    )
    specification: str = Field(
        description="""
Filesystem path or url to an OpenAPI 3 specification in either YAML or JSON format.
We will attempt to convert Swagger 2.0 specifications, Postman 2.x collections or HTTP Archive (.har file) to OpenAPI 3 if those are provided.
"""
    )

    options: MapiRunOptions

    def command_line(self, workspace: str, project: str, target: str) -> str:
        return f"mapi run {workspace}/{project}/{target} {self.duration} {self.specification} {self.options.command_line()}"


class MapiDiscover(BaseModel):
    host: str = Field(description="The host to scan", examples=["localhost"])
    port: int = Field(description="The port to scan", examples=["80"])

    @classmethod
    def output_dir() -> str:
        return f"{os.getcwd()}/mapi_discover"

    def command_line(self) -> str:
        return f"mapi discover --hosts={self.host} --ports={self.port} --output={MapiDiscover.output_dir()}"


class MapiDefectList(BaseModel):
    run_id: int = Field(
        description="""
The Run ID to fetch defects from. The Run ID is the number of the URL provided when performing a run via mapi run
"""
    )

    def command_line(self, workspace: str, project: str, target: str) -> str:
        return f"mapi defect list {workspace}/{project}/{target}/{self.run_id}"


class MapiTools(str, Enum):
    RUN = "run"
    DEFECT_LIST = "defect_list"
    DISCOVER = "discover"


def run_command(logger: logging.Logger, command: str) -> tuple[bool, str]:
    logger.info(f"Running command: {command}")
    process = subprocess.Popen(
        shlex.split(command),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    captured = []
    for line in process.stdout:
        logger.info(line[:-1])
        captured.append(line)

    return_code = process.wait()

    if len(captured) > 50:
        captured = captured[-50:]

    output = "".join(captured)
    return return_code == 0, output


def mapi_run(
    logger: logging.Logger, workspace: str, project: str, target: str, run: MapiRun
) -> str:
    command = run.command_line(workspace, project, target)
    success, output = run_command(logger, command)
    prefix = "mapi run output" if success else "mapi run failed"
    return f"{prefix}:{output}"


def mapi_list_defects(
    logger: logging.Logger,
    workspace: str,
    project: str,
    target: str,
    list: MapiDefectList,
) -> str:
    command = list.command_line(workspace, project, target)
    success, output = run_command(logger, command)
    prefix = "mapi defects list output" if success else "mapi defects list failed"
    return f"{prefix}:{output}"


def mapi_discover(logger: logging.Logger, discover: MapiDiscover) -> str:
    command = discover.command_line()
    success, output = run_command(logger, command)

    if success:
        api_spec_paths = [str(f) for f in Path(MapiDiscover.output_dir()).iterdir()]
        return f"Api specification paths: {api_spec_paths} (can be analyzed as is without further prioritization/processing)"
    else:
        return f"mapi discover failed:\n{output}"


async def serve(workspace: str, project: str, target: str) -> None:
    logger = logging.getLogger(__name__)
    server = Server("mcp-mapi")

    logger.info(
        f"mcp-mapi used with options:\nWorkspace: {workspace}\nProject: {project}\nTarget: {target}"
    )

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name=MapiTools.RUN,
                description="Analyzes an API for vulnerabilities. This tool requires an API specification in order to perform it's analysis.",
                inputSchema=MapiRun.model_json_schema(),
            ),
            Tool(
                name=MapiTools.DEFECT_LIST,
                description="Fetches the defects that were recorded for a specific run",
                inputSchema=MapiDefectList.model_json_schema(),
            ),
            Tool(
                name=MapiTools.DISCOVER,
                description="""A discovery tool that searches for API specifications.
                If crawling with a crawler fails, the target might be a web API, in which case this
                tool can be used to discover API specifications.""",
                inputSchema=MapiDiscover.model_json_schema()
            )
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        match name:
            case MapiTools.RUN:
                mapi_run_args = MapiRun(**arguments)
                result = mapi_run(logger, workspace, project, target, mapi_run_args)
                return [TextContent(type="text", text=result)]
            case MapiTools.DEFECT_LIST:
                mapi_defect_list_args = MapiDefectList(**arguments)
                result = mapi_list_defects(
                    logger, workspace, project, target, mapi_defect_list_args
                )
                return [TextContent(type="text", text=result)]
            case MapiTools.DISCOVER:
                mapi_discover_args = MapiDiscover(**arguments)
                result = mapi_discover(logger, mapi_discover_args)
                return [TextContent(type="text", text=result)]
            case _:
                raise ValueError(f"Unknown tool: {name}")

    options = server.create_initialization_options()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, options, raise_exceptions=True)
