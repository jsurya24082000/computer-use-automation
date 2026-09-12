from typing import Any, Dict, List


def _input_label(el) -> str:
    """Try to find the nearest label text for an input."""
    try:
        # Look for the closest previous sibling or parent table cell that contains text.
        return el.evaluate("""e => {
            let cell = e.closest('td');
            if (cell) {
                let row = cell.parentElement;
                if (row) {
                    let prev = cell.previousElementSibling;
                    if (prev) return prev.innerText.trim();
                    for (let c of row.children) {
                        if (c !== cell && c.innerText.trim()) return c.innerText.trim();
                    }
                }
            }
            return '';
        }""")
    except Exception:
        return ""


def extract_controls(page) -> List[Dict[str, Any]]:
    """Return a flat list of interactive controls the model can reason about."""
    controls = []

    # Inputs (text, password, submit, etc.)
    for el in page.locator("input, select, textarea").all():
        try:
            controls.append({
                "tag": el.evaluate("e => e.tagName.toLowerCase()"),
                "type": el.get_attribute("type") or el.evaluate("e => e.type"),
                "name": el.get_attribute("name"),
                "aria_label": el.get_attribute("aria-label"),
                "id": el.get_attribute("id"),
                "label": _input_label(el),
                "value": (el.input_value() or el.get_attribute("value")) if el.is_visible() else None,
            })
        except Exception:
            continue

    # Buttons / submit inputs / clickable table cells
    for el in page.locator("button, input[type='submit'], td[onclick]").all():
        try:
            text = el.inner_text().strip() if el.is_visible() else ""
            if not text:
                text = el.get_attribute("value") or el.get_attribute("aria-label") or ""
            controls.append({
                "tag": el.evaluate("e => e.tagName.toLowerCase()"),
                "type": el.get_attribute("type"),
                "name": el.get_attribute("name"),
                "aria_label": el.get_attribute("aria-label"),
                "id": el.get_attribute("id"),
                "text": text,
            })
        except Exception:
            continue

    # Links
    for el in page.locator("a").all():
        try:
            if el.is_visible():
                controls.append({
                    "tag": "a",
                    "href": el.get_attribute("href"),
                    "text": el.inner_text().strip(),
                })
        except Exception:
            continue

    # Deduplicate by (tag, name, text)
    seen = set()
    unique = []
    for c in controls:
        key = (c.get("tag"), c.get("name"), c.get("text"))
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique


def build_prompt(goal: str, url: str, title: str, controls: List[Dict[str, Any]], body_text: str = "", previous_actions: str = "") -> str:
    control_text = "\n".join(
        f"- tag={c.get('tag')} type={c.get('type')} name={c.get('name')} aria_label={c.get('aria_label')} label={c.get('label')} text={c.get('text')} current_value={c.get('value')}"
        for c in controls
    )

    snippet = body_text.replace("\n", " ").strip()[:800]

    return f"""You are driving a browser to complete the following goal. You must take only one action at a time and then stop and wait for the next state.

GOAL: {goal}

Previous actions already performed:
{previous_actions}

Current page:
- URL: {url}
- Title: {title}
- Visible page text: {snippet}

Interactive controls available:
{control_text}

Allowed actions: click, fill, submit, navigate, wait, done, escalate.

Rules:
- Use the previous actions to understand what has already been done. Do NOT repeat a login if the page is already past the login screen.
- Do NOT fill a field that already has the correct value. If the `current_value` already matches what you want, choose a different action (fill another field or click/submit).
- Use `fill` to type text into an empty/wrong field. Set `target` by `name` or `text` and `value` to the text.
- Use `click` to press a button, link, or clickable cell. Set `target` by `name` or `text`. NEVER click the "Logout" link — it ends the session and the goal will not be reached.
- Use `submit` to submit a form by clicking its submit button/cell. Set `target` by `name` or `text`.
- Use `navigate` to go to a URL. Set `value` to the URL.
- Use `wait` if the page is loading or you need to see an outcome. Set `value` to the milliseconds.
- Use `done` immediately when the goal is accomplished (the page shows the answer you need, such as the savings balance or a confirmation number).
- Use `escalate` only if you are truly stuck and have no safe action.
- If the page already shows the information requested by the goal, use `done` with no target.

Respond with a single JSON object of this exact form and no other text:

{{
  "action": "...",
  "target": {{"name": "..." or "text": "..."}},
  "value": "...",
  "reason": "..."
}}

`target` is only needed for click, fill, and submit. `value` is only needed for fill, navigate, and wait.
"""
