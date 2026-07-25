"""External tools the agents call (the MCP tool surface).

Each tool is small, typed, free-tier friendly, and degrades gracefully when its key
is absent. Exposed as plain callables here and over MCP in ``mcp_server.py``.
"""

from .market import company_news, stock_quote
from .sec import sec_filing_excerpt
from .web_search import web_search

__all__ = ["company_news", "sec_filing_excerpt", "stock_quote", "web_search"]
