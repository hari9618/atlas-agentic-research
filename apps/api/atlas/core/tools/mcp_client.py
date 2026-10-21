"""Atlas MCP client — connect to the Atlas MCP server and call its tools.

This is the *client* side of the Model Context Protocol: it launches the Atlas MCP
server (``mcp_server.py``) over stdio, performs the MCP handshake, discovers the tools
the server advertises, and invokes them by name with typed JSON arguments — exactly
how Claude Desktop, Cursor, or any MCP host talks to a tool server.

    from atlas.core.tools.mcp_client import list_tools, call_tool
    print(list_tools())                       # discovery
    call_tool("web_search", {"query": "..."}) # invocation over MCP
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Launch our own MCP server as a subprocess over stdio (the standard MCP transport).
_SERVER = StdioServerParameters(
    command=sys.executable,  # the current Python interpreter
    args=["-m", "atlas.core.tools.mcp_server"],
)


async def _alist_tools() -> list[dict[str, Any]]:
    async with stdio_client(_SERVER) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            resp = await session.list_tools()
            return [{"name": t.name, "description": (t.description or "").split("\n")[0]}
                    for t in resp.tools]


async def _acall_tool(name: str, arguments: dict[str, Any]) -> Any:
    async with stdio_client(_SERVER) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(name, arguments=arguments)
            # MCP returns content parts; surface the text payload.
            parts = [c.text for c in result.content if getattr(c, "type", "") == "text"]
            return "\n".join(parts) if parts else result.content


def list_tools() -> list[dict[str, Any]]:
    """Discover the tools the Atlas MCP server advertises (sync convenience)."""
    return asyncio.run(_alist_tools())


def call_tool(name: str, arguments: dict[str, Any]) -> Any:
    """Call one Atlas MCP tool by name over the protocol (sync convenience)."""
    return asyncio.run(_acall_tool(name, arguments))


if __name__ == "__main__":
    print("Discovering Atlas MCP tools over the protocol...")
    for t in list_tools():
        print(f"  - {t['name']}: {t['description']}")
