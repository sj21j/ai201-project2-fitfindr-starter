"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import re

from tools import search_listings, suggest_outfit, create_fit_card


# ── query parsing ─────────────────────────────────────────────────────────────

# Size tokens, ordered longest-first so "S/M" wins over "S", "XXL" over "XL".
_SIZE_RE = re.compile(
    r"\bsize\s+(\d+(?:\.\d+)?)\b"               # "size 8", "size 8.5"
    r"|\b(?:size\s+)?(XXL|XXS|S/M|M/L|XL|XS|S|M|L)\b",
    re.IGNORECASE,
)
# "$30" / "under $30" (optional 'under'), or "under 30" (no dollar sign).
_PRICE_RE = re.compile(
    r"(?:under\s+)?\$\s*(\d+(?:\.\d+)?)\b|\bunder\s+(\d+(?:\.\d+)?)\b",
    re.IGNORECASE,
)


def _parse_query(query: str) -> dict:
    """Extract description, size, and max_price from a query using regex."""
    price_match = _PRICE_RE.search(query)
    size_match = _SIZE_RE.search(query)

    max_price = None
    if price_match:
        value = price_match.group(1) or price_match.group(2)
        max_price = float(value)

    size = None
    if size_match:
        size = (size_match.group(1) or size_match.group(2)).upper()

    # Build the description by cutting the price and size spans out of the
    # original query, then cleaning up leftover commas and whitespace.
    description = query
    spans = []
    if price_match:
        spans.append(price_match.span())
    if size_match:
        spans.append(size_match.span())
    for start, end in sorted(spans, reverse=True):
        description = description[:start] + " " + description[end:]

    description = re.sub(r"\s*,\s*", " ", description)   # drop stray commas
    description = re.sub(r"\s+", " ", description).strip()

    return {"description": description, "size": size, "max_price": max_price}


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.

    You may add fields to this dict as needed for your implementation.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "error": None,               # set if the interaction ended early
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.

    TODO — implement this function using the planning loop you designed in planning.md:

        Step 1: Initialize the session with _new_session().

        Step 2: Parse the user's query to extract a description, size, and
                max_price. You can use regex, string splitting, or ask the LLM
                to parse it — document your choice in planning.md.
                Store the result in session["parsed"].

        Step 3: Call search_listings() with the parsed parameters.
                Store results in session["search_results"].
                If no results: set session["error"] to a helpful message and
                return the session early. Do NOT proceed to suggest_outfit
                with empty input.

        Step 4: Select the item to use (e.g., the top result).
                Store it in session["selected_item"].

        Step 5: Call suggest_outfit() with the selected item and wardrobe.
                Store the result in session["outfit_suggestion"].

        Step 6: Call create_fit_card() with the outfit suggestion and selected item.
                Store the result in session["fit_card"].

        Step 7: Return the session.

    Before writing code, complete the Planning Loop and State Management sections
    of planning.md — your implementation should match what you described there.
    """
    # Step 1: fresh session.
    session = _new_session(query, wardrobe)

    # Step 2: parse the query (regex, no LLM).
    parsed = _parse_query(query)
    session["parsed"] = parsed
    description = parsed["description"]
    size = parsed["size"]
    max_price = parsed["max_price"]

    # Step 3: search. Hard stop if nothing matches.
    results = search_listings(description, size, max_price)
    session["search_results"] = results
    if results == []:
        filters = []
        if size:
            filters.append(f"size {size}")
        if max_price is not None:
            filters.append(f"under ${max_price:g}")
        filter_text = f" with filters ({', '.join(filters)})" if filters else ""
        session["error"] = (
            f"No listings found for '{description}'{filter_text}. "
            "Try broader keywords or removing a filter."
        )
        return session

    # Step 4: select the top-ranked item.
    session["selected_item"] = results[0]

    # Step 5: outfit suggestion. Stop early if it comes back empty.
    outfit = suggest_outfit(session["selected_item"], session["wardrobe"])
    session["outfit_suggestion"] = outfit
    if not outfit or not outfit.strip():
        session["error"] = "Outfit suggestion returned empty."
        return session

    # Step 6: fit card.
    session["fit_card"] = create_fit_card(outfit, session["selected_item"])

    # Step 7: done.
    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
