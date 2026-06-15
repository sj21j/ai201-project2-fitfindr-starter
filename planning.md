# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
Searches the mock listings dataset for secondhand items that match the user's keywords, optional size, and optional price ceiling. Returns a ranked list of matches sorted by relevance so the agent can pick the best result.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `description` (str): Keywords describing the item the user wants (e.g., "vintage graphic tee"). Used for keyword scoring against title, description, category, style_tags, colors, and brand fields.
- `size` (str):  Size string to filter by (e.g., "M", "XL"). Case-insensitive substring match so "M" matches "S/M". Pass None to skip size filtering.
- `max_price` (float): Maximum price inclusive (e.g., 30.0). Pass None to skip price filtering.

**What it returns:**
<!-- Describe the return value — what fields does a result contain? -->
A list[dict] sorted by keyword relevance score, highest first. Each dict is a full listing record with these fields:
- id (str): unique listing ID, e.g. "lst_001"
- title (str): item name, e.g. "Vintage Levi's 501 Jeans"
- description (str): free-text description
- category (str): one of tops, bottoms, outerwear, shoes, accessories
- style_tags (list[str]): e.g. ["vintage", "streetwear"]
- size (str): e.g. "S/M", "W30 L30", "XL (oversized)"
- condition (str): excellent, good, or fair
- price (float): e.g. 38.0
- colors (list[str]): e.g. ["blue", "indigo"]
- brand (str | None): brand name or null
- platform (str): depop, thredUp, or poshmark

Returns [] if nothing matches, never raises an exception.
**What happens if it fails or returns nothing:**
<!-- What should the agent do if no listings match? -->
If load_listings() raises an exception (missing file, bad JSON), catch it and return []. If the scored list is empty after filtering, return []. The planning loop checks for [] and sets session["error"] with a helpful message telling the user to try different keywords or remove size/price filters. The agent returns immediately, suggest_outfit is never called with empty input.
---

### Tool 2: suggest_outfit

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
Given the selected thrift listing and the user's wardrobe, calls the Groq LLM to suggest 1–2 complete outfit combinations. If the wardrobe is empty, gives general styling advice for the item instead.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `new_item` (dict): A full listing dict from search_listings (see fields above).
- `wardrobe` (dict): A wardrobe dict with an items key containing a list of wardrobe item dicts. Each wardrobe item has: id (str), name (str), category (str), colors (list[str]), style_tags (list[str]), notes (str | None).

**What it returns:**
<!-- Describe the return value -->
A non-empty str with outfit suggestions. If the wardrobe has items, names specific pieces from the wardrobe and describes the overall look. If the wardrobe is empty, describes what types of pieces pair well with the item and what vibe it suits.

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the wardrobe is empty or no outfit can be suggested? -->
- Empty wardrobe (wardrobe["items"] == []): Switch to a general-styling prompt — never crash, never return "".
- Groq API error: Catch the exception and return a fallback string like "Couldn't load suggestions — try pairing [item title] with simple basics for an easy look." Always returns a string.
---

### Tool 3: create_fit_card

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
Takes the outfit suggestion and the listing dict and calls the Groq LLM to generate a casual 2–4 sentence Instagram/TikTok-style caption for the look.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `outfit` (str): The suggestion string returned by suggest_outfit.
- `new_item` (dict): The full listing dict for the thrifted item (used for title, price, platform, condition).

**What it returns:**
<!-- Describe the return value -->
A str of 2–4 sentences. Casual tone, reads like a real OOTD post. Mentions the item name, price, and platform once each, naturally woven in. No hashtags. Uses temperature 1.0 for variety between calls. If outfit is empty or whitespace-only, returns a descriptive error message string, never raises.

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the outfit data is incomplete? -->
- Empty outfit string: Return "Cannot generate fit card: outfit suggestion is missing." immediately — do not call the LLM.
- Groq API error: Catch and return a fallback string that includes the item name and price inline.
---

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->

---

## Planning Loop

**How does your agent decide which tool to call next?**
<!-- Describe the logic your planning loop uses. What does it look at? What conditions change its behavior? How does it know when it's done? -->
The agent uses a conditional planning loop — it does not call all three tools in a fixed sequence regardless of what was returned. Here is the exact branching logic:
1. Parse the user's query using regex to extract description, size, and max_price. Store in session["parsed"].
2. Call search_listings(description, size, max_price). Store result in session["search_results"].
     - If results == []: set session["error"] to a message describing what failed and what the user can try (e.g., "No listings found for 'designer ballgown' with size XXS under $5. Try removing the size filter or using different keywords."). Return the session immediately. Do NOT proceed.
     - If results found: set session["selected_item"] = results[0]. Continue to step 3.
3. Call suggest_outfit(session["selected_item"], session["wardrobe"]). Store result in session["outfit_suggestion"].
     - If result is an empty string: set session["error"], return session early.
     - Otherwise continue to step 4.
4. Call create_fit_card(session["outfit_suggestion"], session["selected_item"]). Store result in session["fit_card"].
5. Return the completed session.

The agent knows it's done when session["fit_card"] is populated (happy path) or session["error"] is set (error path).
---

## State Management

**How does information from one tool get passed to the next?**
<!-- Describe how your agent stores and accesses state within a session. What data is tracked? How is it passed between tool calls? -->
All state lives in a single session dict initialized at the start of run_agent(). Tools receive their inputs as plain function arguments, they never read from the session dict directly. Results are written back into the session after each tool call, making them available to the next step.

| Session key | Type | Set when | Used by |
|---|---|---|---|
| `query` | str | Initialization | Reference / debugging |
| `parsed` | dict | After `_parse_query()` | Feeds args into `search_listings()` |
| `search_results` | list[dict] | After `search_listings()` | Empty-check branch |
| `selected_item` | dict | After non-empty search | Arg to `suggest_outfit()` and `create_fit_card()` |
| `wardrobe` | dict | Initialization | Arg to `suggest_outfit()` |
| `outfit_suggestion` | str | After `suggest_outfit()` | Arg to `create_fit_card()` |
| `fit_card` | str | After `create_fit_card()` | Returned to UI |
| `error` | str | On any early exit | Read by `handle_query()` in app.py |

The key handoff: `selected_item` found in step 2 flows as an argument into both `suggest_outfit` and `create_fit_card` — the user never has to re-enter what they were looking at.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| `search_listings` | No results match the query | Set `session["error"]` = "No listings found for '[description]' with filters ([size], under $[price]). Try broader keywords or remove a filter." Return session immediately — do not call `suggest_outfit`. |
| `search_listings` | `load_listings()` raises exception | Caught inside tool; returns `[]`. Agent treats this as no-results case above. |
| `suggest_outfit` | Wardrobe is empty | Tool switches to a general-styling prompt path. Returns a useful string — never crashes or returns "". |
| `suggest_outfit` | Groq API error | Caught inside tool; returns fallback string. Agent continues with fallback as the outfit suggestion. |
| `create_fit_card` | `outfit` is empty or whitespace | Tool returns error message string immediately without calling LLM. |
| `create_fit_card` | Groq API error | Caught inside tool; returns fallback string with item name and price. |

---

## Architecture

<!-- Draw a diagram of your agent showing how the components connect:
     User input → Planning Loop → Tools (search_listings, suggest_outfit, create_fit_card)
                                                                          ↕
                                                                   State / Session
     Show what triggers each tool, how state flows between them, and where error paths branch off.
     ASCII art, a Mermaid diagram (https://mermaid.js.org/syntax/flowchart.html), or an embedded
     sketch are all fine. You'll share this diagram with an AI tool when asking it to implement
     the planning loop and each individual tool. -->
```
User query (natural language)
    │
    ▼
_parse_query(query)
    │  → {description (str), size (str|None), max_price (float|None)}
    │
    ▼
Planning Loop ─────────────────────────────────────────────────────────┐
    │                                                                   │
    ├─► search_listings(description, size, max_price)                  │
    │        │                                                          │
    │        ├── results == [] ──► session["error"] = "No listings..." │
    │        │                     return session  ◄────────────────────┘
    │        │                     (early exit — tools 2 & 3 never called)
    │        │
    │        └── results found
    │              session["search_results"] = results
    │              session["selected_item"]  = results[0]
    │
    ├─► suggest_outfit(selected_item, wardrobe)
    │        │
    │        ├── wardrobe["items"] == [] → general styling prompt path
    │        │
    │        └── wardrobe has items → specific outfit prompt path
    │              session["outfit_suggestion"] = LLM response string
    │
    └─► create_fit_card(outfit_suggestion, selected_item)
             │
             ├── outfit == "" → return error string (no LLM call)
             │
             └── session["fit_card"] = LLM caption string
                     │
                     ▼
               Return session to handle_query() in app.py
                     │
                     ▼
         ┌───────────────────────────┐
         │  Panel 1: listing_text    │  ← formatted from selected_item
         │  Panel 2: outfit_suggestion│  ← session["outfit_suggestion"]
         │  Panel 3: fit_card        │  ← session["fit_card"]
         └───────────────────────────┘
```
---

## AI Tool Plan

<!-- For each part of the implementation below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, your agent diagram)
     - What you expect it to produce
     - How you'll verify the output matches your spec before moving on

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Tool 1 spec (inputs, return value, failure mode) and ask it to implement
     search_listings() using load_listings() from the data loader — then test it against 3 queries
     before trusting it" is a plan. -->

**Milestone 3 — Individual tool implementations:**
For `search_listings`: Give Claude the Tool 1 spec block from this planning.md (inputs with types, return value field list, failure mode) plus the `load_listings()` signature from `utils/data_loader.py`. Ask it to implement the function body only. Verify the output by checking: does it filter by all three params? Does it return `[]` (not `None`) on no match? Does it keyword-score against all text fields including style_tags and colors? Then run the pytest tests before using it.

For `suggest_outfit`: Give Claude the Tool 2 spec block and the wardrobe schema field list. Ask it to implement the function body only, handling the empty-wardrobe path with a separate prompt. Verify by calling it with `get_empty_wardrobe()` and confirming the return is a non-empty string.

For `create_fit_card`: Give Claude the Tool 3 spec block. Ask for temperature=1.0 and an empty-outfit guard as the very first line. Verify by calling with `""` and confirming no exception is raised.

**Milestone 4 — Planning loop and state management:**
Give Claude the Planning Loop section, State Management table, and the ASCII architecture diagram from this file. Ask it to implement `run_agent()` only, not `_new_session()`. Verify by running `python agent.py` and checking: (1) happy path populates all three session fields, (2) no-results path sets `session["error"]` and leaves `outfit_suggestion` and `fit_card` as None.
---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
<!-- What does the agent do first? Which tool is called? With what input? -->
`_parse_query()` extracts:
- `description = "vintage graphic tee"`
- `size = None` (no size mentioned)
- `max_price = 30.0`

**Step 2:**
<!-- What happens next? What was returned from step 1? What tool is called now? -->
`search_listings("vintage graphic tee", size=None, max_price=30.0)` loads all 40 listings, drops any with `price > 30.0`, then scores the remainder by counting how many of ["vintage", "graphic", "tee"] appear in each item's combined text fields. Items with score 0 are dropped. Returns e.g.:
```
[
  {"id": "lst_002", "title": "Y2K Baby Tee — Butterfly Print", "price": 18.0, "platform": "depop", "size": "S/M", ...},
  {"id": "lst_007", "title": "Faded Band Tee — Black", "price": 24.0, ...},
  ...
]
```
`session["selected_item"]` = first result (e.g., the Y2K Baby Tee at $18).

**Step 3:**
<!-- Continue until the full interaction is complete -->
`suggest_outfit(selected_item, wardrobe)` formats the 10 wardrobe items (baggy straight-leg jeans, chunky white sneakers, black combat boots, etc.) into the prompt and asks the LLM for specific combinations. LLM returns something like:
`"Tuck this baby tee into your baggy straight-leg jeans and throw on your chunky white sneakers for a 90s-inspired look. Or layer it under your vintage black denim jacket with the combat boots for an edgier vibe."`

`session["outfit_suggestion"]` = that string.

**Step 4 — Fit card:**
`create_fit_card(outfit_suggestion, selected_item)` sends the outfit string plus item details (title, $18, depop) to the LLM at temperature=1.0. Returns something like:
`"found this y2k baby tee on depop for $18 and it was made for my baggy jeans era 🤍 denim jacket over the top and you're done"`

`session["fit_card"]` = that string.

**Final output to user:**
<!-- What does the user actually see at the end? -->
- Panel 1 (Top listing found): Formatted card showing "Y2K Baby Tee — Butterfly Print / $18.00 · excellent / depop / Size: S/M / Colors: white, pink, purple / ..."
- Panel 2 (Outfit idea): The full outfit suggestion paragraph from the LLM
- Panel 3 (Your fit card): The Instagram-style caption