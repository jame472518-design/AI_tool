from __future__ import annotations

_REVIEW_PROMPT = """\
You are a senior Android BSP engineer. Review the following git diff and report only serious issues.

Focus on:
- Memory leaks (malloc without free, unreleased resources)
- Null pointer dereference
- Race conditions, missing lock/mutex protection
- Hardcoded secrets (keys, passwords, tokens)
- Obvious logic errors
- Buffer overflow

Do not report:
- Code style or naming suggestions
- Performance optimization suggestions
- Refactoring suggestions
- Android XML android:key attributes (e.g. android:key="pref_camera2_xxx") — these are preference identifiers, NOT hardcoded secrets
- Android resource references in XML (e.g. @string/, @drawable/, @color/) are normal usage, not issues

Respond with a JSON array only. Each element:
{"severity": "critical|error|warning|info", "file": "path", "line": number, "message": "description"}
If no issues found, respond with []. No other text."""

REVIEW_RESPONSE_SCHEMA = """Respond with a JSON array only. Each element:
{"severity": "critical|error|warning|info", "file": "path", "line": number, "message": "description"}
If no issues found, respond with []. No other text."""

_COMMIT_IMPROVE_PROMPT_NO_TEMPLATE = """\
You are a technical writing assistant. Given the original commit message and the git diff:
1. Fix English grammar errors
2. Make the description accurately reflect the code changes
3. Keep it under 72 characters total
4. Preserve the [PROJECT-NUMBER] prefix exactly as-is

Respond with only the improved commit message. No explanation, no quotes.

Original: {message}

Diff:
{diff}"""

_COMMIT_IMPROVE_PROMPT_WITH_TEMPLATE = """\
You are a technical writing assistant. Given the original commit message and the git diff, improve the message to follow the template format below.

Template format:
{template}

Rules:
1. Output MUST follow the template structure exactly — fill in each line of the template
2. Make the description accurately reflect the code changes
3. Preserve the [PROJECT-NUMBER] prefix exactly as-is if present
4. Do NOT include lines starting with # (those are comments)

Respond with only the improved commit message. No explanation, no quotes.

Original: {message}

Diff:
{diff}"""


def get_review_prompt(custom_rules: str | None = None) -> str:
    if not custom_rules:
        return _REVIEW_PROMPT
    return _REVIEW_PROMPT.replace(
        "\nDo not report:",
        f"\nAdditional rules:\n- {custom_rules}\n\nDo not report:",
    )


def get_commit_improve_prompt(message: str, diff: str, template: str | None = None) -> str:
    if template:
        return _COMMIT_IMPROVE_PROMPT_WITH_TEMPLATE.format(message=message, diff=diff, template=template)
    return _COMMIT_IMPROVE_PROMPT_NO_TEMPLATE.format(message=message, diff=diff)


_GENERATE_COMMIT_PROMPT_NO_TEMPLATE = """\
You are a technical writing assistant. Given the following git diff, generate a concise commit message description.

Rules:
- Use present tense imperative form (e.g., "fix crash in camera HAL", "add null check for buffer pointer")
- Start with a lowercase verb
- Accurately describe what the code changes do
- Keep it under 72 characters
- Respond with only the description, no prefix, no quotes, no explanation

Diff:
{diff}"""

_GENERATE_COMMIT_PROMPT_WITH_TEMPLATE = """\
You are a technical writing assistant. Given the following git diff, generate a commit message that follows the template format below.

Template format:
{template}

Rules:
- Output MUST follow the template structure exactly — fill in each line of the template
- Accurately describe what the code changes do
- Do NOT include lines starting with # (those are comments)
- Respond with only the commit message following the template. No explanation, no quotes.

Diff:
{diff}"""


def get_generate_commit_prompt(diff: str, template: str | None = None) -> str:
    if template:
        return _GENERATE_COMMIT_PROMPT_WITH_TEMPLATE.format(diff=diff, template=template)
    return _GENERATE_COMMIT_PROMPT_NO_TEMPLATE.format(diff=diff)
