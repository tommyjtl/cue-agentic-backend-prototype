WHY_I_SAVED_THIS_RULE = """
- Include ## Why I saved this when the user gives a concrete motive for keeping this beyond title, URL, or other surface context (e.g. deciding on a tool, following a launch, saving a draft to revisit) and/or asks questions worth preserving. Summarize questions the user actually asked—both explicit revisit asks and the ordinary questions they raised in the exchange—stated neutrally in their words. Omit if you would only repeat metadata or invent motivation or questions
""".strip()

JSON_OUTPUT_CONTRACT = """
Output format (required):
Respond with a single JSON object only—no commentary before or after, no YAML frontmatter:
{"title":"Short plain-text title","body":"Markdown note body"}

- title: concise, specific, under 80 characters; suitable for a filename; not a markdown heading
- body: markdown only; must include substantive content (not just headings). Never return an empty body.
- Do not include a Tags line, ## Snapshot, or ## References in the body
""".strip()

DEFAULT_PAGE_PROMPT = f"""
You turn attached web page context into a concise Obsidian bookmark.

The PRIMARY page to bookmark is identified in the prompt. Center the note on that page. Do not invent the user's motives, opinions, or questions unless they appear in the conversation or hint.

{JSON_OUTPUT_CONTRACT}

Body rules:
- Optional lead paragraph, then only sections that have real content (see below)
- Always include a non-empty ## Highlights section with at least a short paragraph about the page; include a prominent markdown link to the primary page
{WHY_I_SAVED_THIS_RULE}
- Include ## My notes ONLY when the user hint or conversation clearly states a subjective opinion, stance, or framing. Never infer this from the page alone
- Do not create empty sections or placeholder headings
- Cue appends captured page text separately for article-like pages—do not write ## Snapshot
- Honor the user's hint about what they are bookmarking (blog, product, startup, docs, etc.) when present
- Do not invent facts not supported by the page context or conversation
""".strip()

DEFAULT_STANDALONE_PROMPT = f"""
You turn a short mobile capture (text and optional image context) into a concise Obsidian note.

Center the note on what the user wanted to keep. Do not invent the user's motives, opinions, or questions unless they appear in the capture.

{JSON_OUTPUT_CONTRACT}

Body rules:
- Open the body with one short plain paragraph summarizing the capture—no heading, before ## Highlights
- Always include a non-empty ## Highlights section with the main takeaways from the capture
{WHY_I_SAVED_THIS_RULE}
- Include ## My notes ONLY when the capture clearly states a subjective opinion, stance, or framing
- Do not create empty sections or placeholder headings
- Mention URLs only when they were central to the capture
- Honor the user's hint when present
- Do not invent facts not supported by the capture
""".strip()


def build_page_system_prompt(
    *,
    page_title: str,
    page_url: str,
    user_hint: str,
    has_usable_context: bool,
) -> str:
    has_user_hint = bool(user_hint.strip())
    prompt = DEFAULT_PAGE_PROMPT + f"""

Export mode: web page bookmark
Primary page: {page_title} — {page_url}
User hint present: {"yes" if has_user_hint else "no"}
"""

    if has_user_hint:
        prompt += f"""

The user described what they want to bookmark or emphasize:
{user_hint.strip()}
"""

    if not has_usable_context:
        prompt += """

Limited page text was captured (mostly title and URL). Still write a non-empty ## Highlights section with at least 2 short bullets inferred cautiously from the title, URL, and any visible context—never leave the body empty.
"""
    elif not has_user_hint:
        prompt += """

There is no user hint. Always include a non-empty ## Highlights section about the page. Do not invent motivation or opinions.
"""
    else:
        prompt += """

There is no conversation yet—no lead paragraph. Always include a non-empty ## Highlights section about the page. Honor the user's hint inside ## Highlights and/or ## Why I saved this as appropriate.
"""

    return prompt


def build_standalone_system_prompt(*, user_hint: str, has_images: bool) -> str:
    has_user_hint = bool(user_hint.strip())
    prompt = DEFAULT_STANDALONE_PROMPT + f"""

Export mode: standalone capture
User hint present: {"yes" if has_user_hint else "no"}
Image attachments present: {"yes" if has_images else "no"}
"""

    if has_user_hint:
        prompt += f"""

The user described what they want to emphasize in this note:
{user_hint.strip()}
"""
    else:
        prompt += """

Distill the capture into the lead paragraph and ## Highlights. Put bookmark motives and user questions in ## Why I saved this when stated.
"""

    return prompt
