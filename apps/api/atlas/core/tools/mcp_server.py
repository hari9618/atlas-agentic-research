"""Atlas MCP server — exposes the research tools over the Model Context Protocol.

The same four tools the agents use in-process are published here as real MCP tools
via the official SDK's ``FastMCP``. Any MCP client (Claude Desktop, Cursor, the MCP
Inspector, or Atlas's own ``mcp_client``) can connect over stdio, discover the tools,
and call them by name with typed JSON arguments.

Run it standalone (stdio transport):

    python -m atlas.core.tools.mcp_server

Each tool is a thin, typed wrapper over the plain callables in this package, so the
business logic lives in one place and MCP is purely the transport/exposure layer.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .market import company_news as _company_news
from .market import stock_quote as _stock_quote
from .sec import sec_filing_excerpt as _sec_filing_excerpt
from .web_search import web_search as _web_search

# The MCP server. The name is what clients see when they connect.
mcp = FastMCP("atlas-tools")


@mcp.tool()
def web_search(query: str, max_results: int = 5) -> list[dict]:
    """Search the live web for recent, general information.

    Returns a list of {title, url, content} hits. Use when the local corpus can't
    answer a question (e.g. a company that wasn't ingested).
    """
    return _web_search(query, max_results=max_results)


@mcp.tool()
def sec_filing_excerpt(ticker: str, form: str = "10-K", max_chars: int = 2000) -> dict:
    """Pull a short excerpt from a public company's latest SEC filing by ticker.

    Returns {ticker, title, url, excerpt} or {} if nothing is found. Use for
    authoritative financials and official disclosures.
    """
    return _sec_filing_excerpt(ticker, form=form, max_chars=max_chars)


@mcp.tool()
def stock_quote(ticker: str) -> dict:
    """Get the latest daily quote (close, volume, date) for a US stock ticker.

    Free, no API key (via Stooq). Returns {} on failure. Use for market/price signals.
    """
    return _stock_quote(ticker)


@mcp.tool()
def company_news(company: str, max_results: int = 5) -> list[dict]:
    """Get recent news headlines about a company.

    Returns a list of {title, url, content}. Use for current events and sentiment.
    """
    return _company_news(company, max_results=max_results)


def main() -> None:
    """Entrypoint: serve the tools over MCP's stdio transport."""
    mcp.run()


if __name__ == "__main__":
    main()
