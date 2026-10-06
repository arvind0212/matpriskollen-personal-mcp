# Roadmap

Keep this integration small and understandable: two read-only tools, explicit stores, traceable results and visible failures.

## Implemented

- Python MCP server over standard input and output.
- Offline `list_stores` and on-demand `get_offers` tools.
- Allowlisted destinations, redirect refusal, response-size and content-type checks, and parsing without executing page JavaScript.
- Product and category filters, bounded pagination, exact count checks and duplicate handling.
- Preserved price and condition text, explicit unknowns, source timestamps and timezone-aware date-window status.
- One-hour in-memory caching, serialized fetches, failure cooldowns and no stale fallback.
- Synthetic offline regression tests and a locked dependency set.

The live integration depends on the source page format. A changed page can require a parser update; an unreadable page must not become an apparently successful empty result.

## Possible next steps

1. Clarify the permitted scope of live access and data use. Code publication, live fetching and redistribution of results are separate questions.
2. Document compatibility checks against a dated page format, when permitted. Keep captured pages and real offer data out of the repository.
3. Add content-safe diagnostics and more synthetic regression cases for parser changes.
4. Add short setup examples for commonly used MCP clients, verified against their current configuration formats.
5. Consider additional stores only through explicit allowlist entries and the same validation and failure contracts.
6. Decide on a distribution licence and packaging beyond a source checkout.

These are possible directions for an experimental personal project, not promised delivery dates or a maintenance commitment.

## Out of scope

Nationwide store discovery, scheduled bulk collection, price-history storage, automatic purchases, nutrition analysis and guaranteed cheapest-basket recommendations. The assistant can use returned data to help plan, but this server does not implement those planning features.

Missing conditions, uncertain membership eligibility and unknown stock remain visible limitations rather than values to guess.
