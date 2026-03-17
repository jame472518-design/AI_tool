from __future__ import annotations

_REVIEW_PROMPT = """\
You are a senior software engineer. Review the following git diff and report only REAL, SERIOUS issues.

First, identify the programming language(s) from the diff, then apply language-appropriate checks:

For C/C++:
- Memory leaks (malloc without free, unreleased resources)
- Null pointer dereference
- Race conditions, missing lock/mutex protection
- Buffer overflow

For Python:
- Unhandled exceptions that could crash the program
- Security issues (SQL injection, command injection, unsafe eval/exec)
- Resource leaks (files/connections opened but never closed, missing context managers)
- Obvious logic errors (wrong variable, unreachable code, infinite loops)

For Java:
- Null pointer dereference
- Resource leaks (unclosed streams, connections)
- Concurrency issues in multi-threaded code

For all languages:
- Hardcoded secrets (keys, passwords, tokens, API keys)
- Obvious logic errors

IMPORTANT — Do NOT report:
- Code style, naming, or formatting suggestions
- Performance optimization suggestions
- Refactoring suggestions
- Issues that require multi-threading when the code is clearly single-threaded
- JSON data files as "incomplete" or "unreleased resources" — JSON is data, not code
- Android XML android:key attributes — these are preference identifiers, NOT secrets
- Android resource references in XML (@string/, @drawable/, @color/)
- Theoretical issues that cannot actually occur in the code's execution context

If you are unsure whether something is a real issue, do NOT report it. Only report issues you are confident about.

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
- Output MUST follow the template structure exactly
- On the first line, brackets containing quoted text like ["Status ex:NEW,UPDATE"] are PLACEHOLDERS — replace with actual values (e.g. [NEW])
- Brackets WITHOUT quotes like [DESCRIPTION], [test] are SECTION TITLES — keep as-is
- "short description" → replace with a concise summary theme
- [DESCRIPTION] and [test] sections → provide DETAILED content, be thorough
- Do NOT include lines starting with # (those are comments)
- Do NOT output placeholder lines like "1." "2." "..." — replace with actual content
- Respond with only the commit message. No explanation, no quotes, no markdown fences.

Diff:
{diff}"""


def get_generate_commit_prompt(diff: str, template: str | None = None) -> str:
    if template:
        return _GENERATE_COMMIT_PROMPT_WITH_TEMPLATE.format(diff=diff, template=template)
    return _GENERATE_COMMIT_PROMPT_NO_TEMPLATE.format(diff=diff)


_INTERVIEW_QUESTIONS_PROMPT = """\
You are a commit message assistant. Given the following git diff, generate 3-5 short questions \
to ask the developer so you can write a good commit message.

Questions should help you understand:
- What was the purpose/motivation of this change
- What was modified and why
- How was it tested

Each question MUST be bilingual: English first, then Chinese translation in parentheses.
Example format:
1. What problem does this change solve? (這個修改解決了什麼問題？)
2. How was this tested? (如何測試的？)

Respond with ONLY the questions, one per line, numbered (1. 2. 3. ...). No other text.

Diff:
{diff}"""

_INTERVIEW_GENERATE_PROMPT = """\
You are a commit message assistant. Given the developer's answers and the git diff, \
generate a commit message following the template format below.

Template format:
{template}

Developer's answers:
{answers}

Rules:
- Output MUST follow the template structure exactly
- Fill in each field based on the answers and diff context
- Do NOT include lines starting with # (those are comments)
- Respond with only the commit message. No explanation, no quotes.

Diff:
{diff}"""

_INTERVIEW_GENERATE_PROMPT_NO_TEMPLATE = """\
You are a commit message assistant. Given the developer's answers and the git diff, \
generate a concise commit message.

Developer's answers:
{answers}

Rules:
- Use format: [tag] description
- Accurately reflect the changes
- Keep first line under 72 characters
- Respond with only the commit message. No explanation, no quotes.

Diff:
{diff}"""


_ANALYZE_DIFF_PROMPT = """\
You are a senior software engineer. Analyze the following code changes and provide a structured summary.

Context — recent commits in this project:
{recent_commits}

Files changed (stats):
{diff_stat}

Full diff:
{diff}

Provide a concise analysis covering:
1. **Files modified**: What each changed file likely does (infer from filename and content)
2. **What changed**: Functional description of the modifications
3. **Why**: Inferred motivation or purpose behind these changes
4. **Scope**: Impact and scope of the changes (small bugfix, new feature, refactor, etc.)

Keep your analysis concise and factual. Do NOT generate a commit message — just analyze."""

_GENERATE_FROM_SUMMARY_PROMPT_WITH_TEMPLATE = """\
You are a technical writing assistant. Given the change analysis below, \
generate a commit message that follows the template format.

Change analysis:
{summary}

Template format:
{template}

Here is an example of a CORRECT output:

[NEW][BSP][Sensor][JIRA-0002][NAL] fix camera crash on boot

[IMPACT PROJECTS]
camera_hal, sensor_service

[DESCRIPTION]
1. Fixed null pointer dereference in camera HAL initialization when sensor module returns empty config
2. Added retry logic for sensor connection timeout during boot sequence
3. Updated error handling to log detailed diagnostic info before failing

[test]
1. Verified camera boot sequence completes without crash on all supported devices
2. Tested sensor reconnection after timeout with 10 retry cycles
3. Confirmed no regression in camera capture performance

Rules:
- First line: replace ["..."] placeholders with actual values, all on ONE line
- Section titles like [DESCRIPTION], [test], [IMPACT PROJECTS] must stay exactly as-is
- [DESCRIPTION] and [test]: be detailed, list every change/test as numbered items
- Remove [none] brackets entirely
- Output ONLY the commit message, nothing else"""

_GENERATE_FROM_SUMMARY_PROMPT_NO_TEMPLATE = """\
You are a technical writing assistant. Given the following change analysis, \
generate a concise commit message description.

Change analysis:
{summary}

Rules:
- Use present tense imperative form (e.g., "fix crash in camera HAL", "add null check for buffer pointer")
- Start with a lowercase verb
- Accurately describe what the code changes do based on the analysis
- Keep it under 72 characters
- Respond with only the description, no prefix, no quotes, no explanation"""


def get_analyze_diff_prompt(diff_stat: str, recent_commits: str, diff: str) -> str:
    return _ANALYZE_DIFF_PROMPT.format(diff_stat=diff_stat, recent_commits=recent_commits, diff=diff)


def get_generate_from_summary_prompt(summary: str, template: str | None = None,
                                     custom_prompt: str | None = None) -> str:
    if custom_prompt:
        # Strip comment lines from custom prompt
        lines = [l for l in custom_prompt.splitlines() if not l.startswith("#")]
        prompt_text = "\n".join(lines).strip()
        return prompt_text.format(summary=summary, template=template or "")
    if template:
        return _GENERATE_FROM_SUMMARY_PROMPT_WITH_TEMPLATE.format(summary=summary, template=template)
    return _GENERATE_FROM_SUMMARY_PROMPT_NO_TEMPLATE.format(summary=summary)


def get_interview_questions_prompt(diff: str) -> str:
    return _INTERVIEW_QUESTIONS_PROMPT.format(diff=diff)


def get_interview_generate_prompt(answers: str, diff: str, template: str | None = None) -> str:
    if template:
        return _INTERVIEW_GENERATE_PROMPT.format(answers=answers, diff=diff, template=template)
    return _INTERVIEW_GENERATE_PROMPT_NO_TEMPLATE.format(answers=answers, diff=diff)
