# Matpriskollen MCP

Bring local grocery offers into your AI assistant. Search by product or category, inspect advertised prices and conditions, and use the results when planning meals or a shopping trip.

> **Status:** Experimental personal project. Unofficial; not affiliated with Matpriskollen or the retailers. Store-page changes may require parser updates.

## What is Matpriskollen?

[Matpriskollen](https://matpriskollen.se) is a Swedish service for finding weekly grocery prices and offers near you. It brings store offers together so you can browse what is advertised locally.

This project connects a small part of that information to an AI assistant through the **Model Context Protocol (MCP)**. The assistant can call two read-only tools to discover the configured stores and retrieve their offers. This is an independent public-page integration, not an official Matpriskollen API.

The current scope is deliberately small:

| Store ID | Store |
|---|---|
| `hemkop_bredang` | Hemköp Skärholmen Bredäng |
| `ica_liljeholmen` | ICA Kvantum Liljeholmen |

It is not a nationwide store search or a complete grocery-price database.

## What can you use it for?

These are example requests for an MCP-enabled assistant, not recorded results or built-in meal-planning features:

- **Plan around local offers:** “What chicken and vegetable offers are listed at my two stores? Suggest a few dinners using those ingredients.”
- **Prepare a shopping list:** “Find coffee, fruit and household essentials in the advertised offers. Keep package sizes and purchase conditions beside each item.”
- **Compare advertised options:** “Show the coffee offers from both stores side by side, including pack size, multibuy terms and any stated membership conditions.”
- **Check the fine print:** “Which matching offers are within their listed date window, and what conditions or missing information should I check before shopping?”

The server supplies offer data. The assistant does the planning and explanation. It does not place orders, maintain a shopping list, calculate nutrition, guarantee availability, or prove which store has the cheapest complete basket. Similar product names do not establish equivalent products or quantities.

## How it works

```text
Your question
    |
MCP-enabled assistant
    |
list_stores / get_offers
    |
Allowlisted public store page -> parser -> validated offer snapshot
```

The parser reads structured data embedded in the page without executing JavaScript. The service checks record counts and returns source information, preserved price text and explicit unknowns. A parser failure is an error, not a successful empty list.

### Tools

**`list_stores()`** returns the two configured store IDs, names and source URLs. No network request.

**`get_offers(store_id, query=None, category=None, limit=20, offset=0)`** retrieves an offer snapshot and supports product-text search, category filtering and pagination. Query and category filters combine with AND.

Example tool arguments, not live output:

```json
{"store_id":"hemkop_bredang","query":"kyckling","limit":20,"offset":0}
```

```json
{"store_id":"ica_liljeholmen","category":"Frukt","limit":10,"offset":0}
```

Results distinguish source-declared, parsed, deduplicated, filtered and returned counts. Pagination uses the verified result set, rather than estimating how many records remain.

### Prices, conditions and uncertainty

- Price labels remain source text, including multibuys and unit prices. The server does not invent a normalized per-item price.
- Package sizes, conditions, categories, origin and validity information are retained when present.
- Missing optional fields remain unknown. An absent membership flag does **not** mean an offer is available without membership.
- Date-window status is recomputed on every call, including cached calls. Being within the broad date window does not override narrower conditions in the offer text.
- Source URLs and fetch times accompany the data. A recent fetch does not prove the retailer recently updated the offer.
- Detail pages are not fetched. Stock, full eligibility and any missing conditions still need checking with the retailer.

## Install and connect

Requires Python 3.12 or newer and [uv](https://docs.astral.sh/uv/). From a checkout of this repository:

```sh
uv sync --frozen
uv run python -m matpriskollen_mcp.server
```

The server uses MCP over standard input and output. It is not an interactive shell command or a web server. Configure your MCP client to launch the command above with this repository as its working directory. If the client does not support a working-directory setting, use the absolute path to the installed `matpriskollen-mcp` executable in the project's virtual environment.

Starting the server and calling `list_stores` make no page request. `get_offers` makes an on-demand request when it needs a fresh snapshot.

## Bounded by design

- Only the two configured store IDs are accepted; callers cannot supply arbitrary URLs.
- One page fetch per store on a cache miss, with a one-hour in-memory cache and serialized fetches.
- Redirects are refused. Response-size, content-type and encoding checks bound what the parser accepts.
- Conflicting duplicates, inconsistent counts and malformed required values produce explicit errors.
- Failed fetches or parses trigger a cooldown. Expired snapshots are discarded rather than served as a stale fallback.
- No scheduled scraping, background refresh, authentication, cookies, access-control bypass, purchases or database writes.
- Source text is untrusted data, never instructions for the assistant.

## Tests

The offline suite uses synthetic fixtures. It does not fetch grocery offers:

```sh
uv run python -m unittest discover -s tests -v
```

Captured store pages and live offer results are not included in this repository.

## Responsible use

This project is independent of Matpriskollen, Hemköp and ICA. Publishing this code does not grant rights to their content or establish permission to fetch or redistribute offer data. Check the current source-site terms and obtain any required permission before using the live integration. Do not use it for bulk collection, republishing a retailer's catalogue or bypassing restrictions.

Check advertised conditions with the retailer before shopping. This tool reports what its source provides; it does not guarantee price eligibility or stock.

See [ROADMAP.md](ROADMAP.md) for the project's scope and possible next steps.
