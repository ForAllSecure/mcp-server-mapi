# MCP Server for mapi

A Model Context Protocol (MCP) server for the mapi cli.

## Build

We recommend building and running the server as a docker container. To build:

```sh
docker build -t mcp-server-mapi .
```

## Run

Invoke the MCP server as follows:

```sh
docker run -i mcp-server-mapi uv run mcp-server-mapi mcp
```

If you're running in local dev mode, you can skip the docker part and just invoke uv.

## Connect to Claude

If you're using Claude Desktop you can hook the MCP server to it using the claude_desktop_config.json file - just make sure you include your API token in it.

## Current Tools

### mapi_discover

### mapi_run
