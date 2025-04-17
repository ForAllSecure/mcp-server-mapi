# mcp-server-mapi

This repository contains the implementation of Model Context Protocol server for mapi cli.

## Setup
Right now, this is very early stage and we don't actually provide a _proper_ python package.

Just clone this repository and from your mcp client project where you want to use this server run:

```bash
uv add "mcp-server-mapi @ <path_to_cloned_folder>"
```

## Usage

Add the following to your `mcp_agent.config.yaml` under `servers` section:

```yaml
mapi:
    command: "uv"
    args: ["run", "mcp-server-mapi", "-w", "<your_mayhem_workspace>"]
```

You can also control the project and target name with `-p=<project_name>` and `-t=<target_name>` respectively.
Finally, you can configure the logging level by passing `-v` for logging level `INFO` (default) or `-vv` for more verbose output.

## Tools

### mapi_run
Performs a mapi run

### mapi_defects_list
Fetches the defects observed for a run