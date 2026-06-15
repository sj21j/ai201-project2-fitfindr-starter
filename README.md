# FitFindr 🛍️

FitFindr is an AI agent that helps you find secondhand fashion and style it with your existing wardrobe. Describe what you're looking for — including size and price if you want to filter — and the agent searches a mock listings dataset, suggests outfit combinations using your wardrobe, and writes a casual, shareable "fit card" caption for the look.

## What's Included

```
ai201-project2-fitfindr-starter/
├── data/
│   ├── listings.json          # 40 mock secondhand listings
│   └── wardrobe_schema.json   # Wardrobe format + example wardrobe
├── utils/
│   └── data_loader.py         # Helper functions for loading the data
├── tools.py                   # The three agent tools (search / suggest / fit card)
├── agent.py                   # Planning loop, query parsing, and session state
├── app.py                     # Gradio web interface
├── tests/
│   └── test_tools.py          # Pytest suite (search + LLM tools, real Groq calls)
├── planning.md                # Design doc — tools, planning loop, state, architecture
└── requirements.txt           # Python dependencies
```

## Setup

```bash
pip install -r requirements.txt
```

Set your Groq API key in a `.env` file (get a free key at [console.groq.com](https://console.groq.com)):
```
GROQ_API_KEY=your_key_here
```

Launch the web app:
```bash
python app.py
```
Then open the localhost URL shown in your terminal (usually http://localhost:7860 — check the terminal, the port may differ).

Run the agent directly from the command line to see both the happy path and the no-results path:
```bash
python agent.py
```

Run the test suite (the outfit/fit-card tests make real Groq API calls, so a valid `GROQ_API_KEY` must be set):
```bash
pytest tests/
```

## The Mock Listings Dataset

`data/listings.json` contains 40 mock secondhand listings across categories (tops, bottoms, outerwear, shoes, accessories) and styles (vintage, y2k, grunge, cottagecore, streetwear, and more).

Each listing has: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`.

Load it with:
```python
from utils.data_loader import load_listings
listings = load_listings()
```

## The Wardrobe Schema

`data/wardrobe_schema.json` defines the format the agent uses to represent a user's existing wardrobe. It includes:

- `schema`: field definitions for a wardrobe item
- `example_wardrobe`: a sample wardrobe with 10 items used for testing
- `empty_wardrobe`: a starting template for a new user

Load an example wardrobe with:
```python
from utils.data_loader import get_example_wardrobe
wardrobe = get_example_wardrobe()
```

## Tools

All three tools live in `tools.py`. Inputs and return types below match the actual function signatures.

### `search_listings`
- **Inputs:** `description` (str), `size` (str | None = None), `max_price` (float | None = None)
- **Output:** `list[dict]` — matching listing dicts (the full listing schema), ranked by keyword-relevance score, best first. Returns `[]` when nothing matches; never raises.
- **Purpose:** Filter the dataset by `max_price` (inclusive) and `size` (case-insensitive substring match), then score the survivors by how many query keywords (≥ 3 chars) appear in each item's combined text (title + description + category + brand + style_tags + colors). Items scoring 0 are dropped.

### `suggest_outfit`
- **Inputs:** `new_item` (dict — a listing), `wardrobe` (dict with an `items` list)
- **Output:** `str` — a non-empty outfit suggestion. Never returns `""` or `None`.
- **Purpose:** Ask the Groq LLM (`llama-3.3-70b-versatile`) for 1–2 outfit combinations that pair the item with named wardrobe pieces. If the wardrobe is empty, it switches to a general-styling prompt instead.

### `create_fit_card`
- **Inputs:** `outfit` (str), `new_item` (dict — a listing)
- **Output:** `str` — a 2–4 sentence casual, Instagram/TikTok-style caption.
- **Purpose:** Turn the outfit suggestion into a shareable caption that mentions the item name, price, and platform once each. Uses `temperature=1.0` for variety between runs.

## How the Planning Loop Works

The loop lives in `run_agent(query, wardrobe)` in `agent.py` and is **conditional**, not a fixed three-call sequence:

1. **Parse.** `_parse_query()` uses regex (no LLM) to extract `description`, optional `size`, and optional `max_price`. Price matches `under $30`, `$30`, or `under 30`. Size matches `size M`, standalone letter tokens (`XS`–`XXL`, `S/M`, `M/L`), and numeric shoe sizes via `size 8`. The matched price/size phrases are stripped out so they don't pollute the description.
2. **Search.** Call `search_listings(description, size, max_price)`.
   - **If it returns `[]`** → build an error message naming the active filters, store it in `session["error"]`, and **return immediately**. The two LLM tools never run on empty input.
   - **Otherwise** → set `session["selected_item"] = results[0]` (the top-ranked match) and continue.
3. **Suggest.** Call `suggest_outfit(selected_item, wardrobe)`.
   - **If the result is empty/whitespace** → set `session["error"]` and return early.
   - **Otherwise** → store it and continue.
4. **Fit card.** Call `create_fit_card(outfit, selected_item)` and store the result.
5. **Return** the session.

The loop knows it's done when `session["fit_card"]` is populated (happy path) or `session["error"]` is set (early exit).

## State Management

All state lives in a single `session` dict created by `_new_session()` at the start of each run. Tools receive their inputs as plain function arguments — they never read the session directly — and results are written back after each call, making them available to the next step.

| Session key | Type | Set when | Used by |
|---|---|---|---|
| `query` | str | Initialization | Reference / debugging |
| `parsed` | dict | After `_parse_query()` | Supplies args to `search_listings()` |
| `search_results` | list[dict] | After `search_listings()` | Empty-check branch |
| `selected_item` | dict | After a non-empty search | Arg to `suggest_outfit()` and `create_fit_card()` |
| `wardrobe` | dict | Initialization | Arg to `suggest_outfit()` |
| `outfit_suggestion` | str | After `suggest_outfit()` | Arg to `create_fit_card()` |
| `fit_card` | str | After `create_fit_card()` | Returned to the UI |
| `error` | str | On any early exit | Read by `handle_query()` in `app.py` |

The key handoff: `selected_item` found during search flows as an argument into both `suggest_outfit` and `create_fit_card`, so the user never re-enters what they were looking at. `app.py`'s `handle_query()` reads the finished session and maps it to the three UI panels (listing / outfit / fit card), showing `session["error"]` in the first panel when set.

## Error Handling

| Tool | Failure mode | Strategy |
|------|-------------|----------|
| `search_listings` | No listings match | Returns `[]`; the loop sets `session["error"]` and stops before the LLM tools. |
| `search_listings` | `load_listings()` raises (missing file / bad JSON) | Wrapped in `try/except` → returns `[]`. |
| `search_listings` | A single malformed listing record | Per-item `try/except (KeyError, TypeError, ValueError)` skips that record instead of aborting the whole search. |
| `suggest_outfit` | Empty wardrobe | Switches to a general-styling prompt — returns useful advice, never crashes or returns `""`. |
| `suggest_outfit` | Groq API error / empty response | Caught → returns a fallback string referencing the item title. |
| `create_fit_card` | `outfit` empty or whitespace | Guard on the first line returns an error string **without** calling the LLM. |
| `create_fit_card` | Groq API error / empty response | Caught → returns a fallback caption that includes the item title and price. |

**Concrete example from testing.** Running `run_agent("designer ballgown size XXS under $5", get_example_wardrobe())` exercises the no-results path: `search_listings` returns `[]`, and the session comes back with

```
error: No listings found for 'designer ballgown' with filters (size XXS, under $5). Try broader keywords or removing a filter.
outfit_suggestion: None
fit_card: None
```

confirming the loop hard-stops and never calls the styling tools on empty input. Separately, `create_fit_card("", item)` returns `"Cannot generate fit card: outfit suggestion is missing. Make sure suggest_outfit ran successfully first."` without raising — verified by `test_create_fit_card_empty_outfit` in the suite.

## Spec Reflection

**Where the spec helped.** Writing each tool's contract in `planning.md` first — inputs with types, the exact return value, and the failure mode ("returns `[]`, never raises") — made the tools implementable and testable in isolation. The unambiguous "no-results → empty list, agent sets the error and stops" rule is what let the planning loop's branching be written cleanly and verified with a single test, before any LLM tool was involved.

**Where implementation diverged, and why.** The original `_parse_query` spec only anticipated letter sizes (`XS`–`XXL`). During testing, the query `"black combat boots size 8"` returned an *Oversized Flannel*: `"size 8"` wasn't recognized, so `8` was never used as a filter and the leftover word `"size"` leaked into keyword scoring — where, because scoring uses substring matching, it matched `"over`**`size`**`d"`. We diverged from the spec by extending the size regex to parse numeric shoe sizes (`size 8`) and strip the phrase from the description. We deliberately kept the existing loose substring filter rather than rewriting `search_listings`, accepting that `8` also matches `US 8.5`/`W28` — a conscious precision-vs-scope trade-off. (A few smaller additions beyond the spec: per-item resilience in the search loop and `.strip()`/empty-response guards on the LLM tools.)

## AI Usage

This project was built collaboratively with an AI coding assistant (Claude). Specific instances of what was directed and what was revised or overridden:

1. **Tool implementation from spec, then hardened.** Claude was given the Tool 1 spec block and asked to implement the `search_listings` body only. The first draft handled the documented cases; after review it was directed to **add per-item `try/except` resilience** so one malformed listing can't abort the entire search — a deliberate addition beyond the original draft.
2. **Overriding a formatting choice.** Claude's first `create_fit_card` draft formatted the price as `$18.00` (two decimals). This was overridden to render `$18` (no decimals) to match the spec's `$X` convention.
3. **Directed debugging with human-chosen trade-offs.** Given the wrong search result (`"black combat boots size 8"` → Oversized Flannel), Claude was directed to inspect `listings.json` and report the root cause rather than guess-fix. From the fix options it presented, the **loose-substring numeric-size approach** was chosen and the seeded example query was **kept as-is** — overriding the stricter exact-match alternatives.
