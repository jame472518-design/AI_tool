# Two-Stage Auto-Generate Commit Message Design

**Date:** 2026-03-17
**Feature:** Option 4 "LLM auto-generate" quality improvement

## Problem

Current option 4 sends only raw git diff to LLM, lacking project context. The generated commit messages are low quality and don't reflect the actual intent of changes.

## Solution

Two-stage LLM generation that first analyzes the change context, then generates a commit message from that understanding.

### Stage 1: Analyze

**Input to LLM:**
- `git diff --cached --stat` (file change summary with line counts)
- `git log --oneline -5` (recent 5 commits for project context and style)
- Raw diff (actual code changes)

**Output from LLM:**
A structured change summary covering:
- What files were modified and their likely purpose
- What the changes do (functional description)
- Why these changes were likely made (inferred motivation)
- Scope/impact of the changes

### Stage 2: Generate

**Input to LLM:**
- Stage 1 summary (NOT raw diff — the LLM's own understanding)
- Commit template (if configured)

**Output from LLM:**
- Commit message following template format

## File Changes

### git.py
- Add `get_staged_diff_stat() -> str`: runs `git diff --cached --stat`
- Add `get_recent_commits(count: int = 5) -> str`: runs `git log --oneline -<count>`

### prompts.py
- Add `_ANALYZE_DIFF_PROMPT`: Stage 1 prompt with placeholders for {diff_stat}, {recent_commits}, {diff}
- Add `_GENERATE_FROM_SUMMARY_PROMPT_WITH_TEMPLATE`: Stage 2 prompt with {summary}, {template}
- Add `_GENERATE_FROM_SUMMARY_PROMPT_NO_TEMPLATE`: Stage 2 prompt with {summary}
- Add `get_analyze_diff_prompt(diff_stat, recent_commits, diff) -> str`
- Add `get_generate_from_summary_prompt(summary, template=None) -> str`

### llm/base.py
- Add abstract method `analyze_diff(diff_stat: str, recent_commits: str, diff: str) -> str`

### llm/ollama.py, openai.py, enterprise.py
- Implement `analyze_diff()` using `_chat()` with the analyze prompt

### reviewer.py
- Add `analyze_diff(diff_stat, recent_commits, diff) -> str` pass-through

### cli.py (prepare_interactive, option 4)
- Call `get_staged_diff_stat()` and `get_recent_commits()`
- Stage 1: `reviewer.analyze_diff(diff_stat, recent_commits, diff)` → display summary
- Stage 2: `reviewer.generate_commit_message_from_summary(summary, template)` → write message

## UX Flow

```
Choice: 4
⠋ AI analyzing changes... (llama3.2)
[Summary]
  Modified 3 files: refactored camera HAL error handling...
⠋ AI generating commit message... (llama3.2)
Generated:
  [fix] refactor camera HAL error handling to use structured exceptions
```

## Non-Goals
- No user interaction between stages (fully automatic)
- No changes to options 1, 2, 3
- No changes to the standalone `generate-commit-msg` command (hook flow stays as-is for speed)
