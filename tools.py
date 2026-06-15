"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    # 1. Load listings, returning [] if anything goes wrong.
    try:
        listings = load_listings()
    except Exception:
        return []

    # Keywords from the description: lowercased, words under 3 chars dropped.
    keywords = [w for w in description.lower().split() if len(w) >= 3]

    scored = []
    for item in listings:
        # Per-item resilience: a malformed record is skipped, not fatal.
        try:
            # 2a. Price filter (inclusive). Skipped when max_price is None.
            if max_price is not None:
                if float(item["price"]) > max_price:
                    continue

            # 2b. Size filter: case-insensitive substring match.
            #     "M" matches "S/M"; "XL (oversized)" matches "XL".
            if size is not None:
                if size.lower() not in item["size"].lower():
                    continue

            # 3. Keyword scoring against a single lowercased text blob.
            brand = item["brand"] or ""
            text = " ".join([
                item["title"],
                item["description"],
                item["category"],
                brand,
                " ".join(item["style_tags"]),
                " ".join(item["colors"]),
            ]).lower()

            score = sum(1 for word in keywords if word in text)
        except (KeyError, TypeError, ValueError):
            continue

        # 4. Drop zero-score items.
        if score > 0:
            scored.append((score, item))

    # 5. Sort by score descending and return the listing dicts.
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in scored]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    items = wardrobe.get("items", [])

    # New-item context shared by both prompt paths.
    item_block = (
        f"Item: {new_item['title']}\n"
        f"Category: {new_item['category']}\n"
        f"Style tags: {', '.join(new_item['style_tags'])}\n"
        f"Colors: {', '.join(new_item['colors'])}"
    )

    if len(items) == 0:
        # Empty wardrobe → general styling advice. Never reveal it's empty.
        prompt = (
            "You are a thoughtful personal stylist. A shopper is considering "
            "this secondhand item:\n\n"
            f"{item_block}\n\n"
            "Give general styling advice: what types of pieces pair well with "
            "it, what overall vibe it suits, and one concrete styling tip. "
            "Keep it warm and practical, a short paragraph."
        )
    else:
        # Format each wardrobe piece as "- name (category, colors)".
        wardrobe_lines = "\n".join(
            f"- {w['name']} ({w['category']}, {', '.join(w['colors'])})"
            for w in items
        )
        prompt = (
            "You are a thoughtful personal stylist. A shopper is considering "
            "this secondhand item:\n\n"
            f"{item_block}\n\n"
            "Here is everything currently in their wardrobe:\n"
            f"{wardrobe_lines}\n\n"
            "Suggest 1-2 specific, complete outfit combinations that pair the "
            "item above with actual pieces from their wardrobe. Name the "
            "wardrobe pieces explicitly by name. Keep it warm and practical."
        )

    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
        )
        suggestion = response.choices[0].message.content
    except Exception:
        return (
            f"Couldn't load suggestions right now — try pairing "
            f"{new_item['title']} with simple basics for an easy look."
        )

    # Guard against an empty/whitespace LLM response — never return "" or None.
    if not suggestion or not suggestion.strip():
        return (
            f"Couldn't load suggestions right now — try pairing "
            f"{new_item['title']} with simple basics for an easy look."
        )
    return suggestion.strip()


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    # First line: guard against a missing/empty outfit — no LLM call.
    if not outfit or not outfit.strip():
        return (
            "Cannot generate fit card: outfit suggestion is missing. Make sure "
            "suggest_outfit ran successfully first."
        )

    title = new_item["title"]
    price = f"${int(float(new_item['price']))}"
    platform = new_item["platform"]
    condition = new_item["condition"]

    prompt = (
        "Write a caption for a secondhand fashion find.\n\n"
        f"Item: {title}\n"
        f"Price: {price}\n"
        f"Platform: {platform}\n"
        f"Condition: {condition}\n\n"
        f"Outfit being worn:\n{outfit}\n\n"
        "Write a 2-4 sentence caption that sounds like a real person's "
        "Instagram OOTD post — casual and authentic, NOT a product listing. "
        f"Mention the item name ({title}), the price ({price}), and the "
        f"platform ({platform}) exactly once each, woven in naturally. "
        "Capture the specific vibe of the outfit described above. "
        "Do not start the caption with the word \"I\". Do not use any hashtags."
    )

    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=1.0,
        )
        caption = response.choices[0].message.content
    except Exception:
        return (
            f"Snagged the {title} for {price} — a secondhand steal worth "
            f"styling your own way."
        )

    # Defend against an empty/whitespace LLM response — never return "".
    if not caption or not caption.strip():
        return (
            f"Snagged the {title} for {price} — a secondhand steal worth "
            f"styling your own way."
        )
    return caption.strip()
