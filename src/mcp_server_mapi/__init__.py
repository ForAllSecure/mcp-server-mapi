import click
import sys
import asyncio
import logging
from .server import serve

@click.command()
@click.option("-w", "--workspace", required=True, type=str, help="The user's Mayhem workspace")
@click.option("-p", "--project", default="mcp-mapi-project", type=str, help="The user's Mayhem project")
@click.option("-t", "--target", default="mcp-mapi-target", type=str, help="The user's Mayhem target")
@click.option("-v", "--verbose", count=True)
def main(workspace: str, project: str, target: str, verbose: int) -> None:
    """MCP Mapi Server - mapi functionality for MCP"""
    logging_level = logging.WARN

    if verbose == 1:
        logging_level = logging.INFO
    elif verbose >= 2:
        logging_level = logging.DEBUG

    logging.basicConfig(level=logging_level, stream=sys.stderr)
    asyncio.run(serve(workspace, project, target))

if __name__ == "__main__":
    main()
