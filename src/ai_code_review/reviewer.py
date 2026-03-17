from __future__ import annotations

from .llm.base import LLMProvider, ReviewResult
from .prompts import get_review_prompt


class Reviewer:
    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    def review_diff(self, diff: str, custom_rules: str | None = None) -> ReviewResult:
        prompt = get_review_prompt(custom_rules)
        return self._provider.review_code(diff, prompt)

    def improve_commit_message(self, message: str, diff: str, template: str | None = None) -> str:
        return self._provider.improve_commit_msg(message, diff, template=template)

    def generate_commit_message(self, diff: str, template: str | None = None) -> str:
        return self._provider.generate_commit_msg(diff, template=template)

    def analyze_diff(self, diff_stat: str, recent_commits: str, diff: str) -> str:
        return self._provider.analyze_diff(diff_stat, recent_commits, diff)

    def generate_commit_message_from_summary(self, summary: str, template: str | None = None,
                                              custom_prompt: str | None = None) -> str:
        return self._provider.generate_commit_msg_from_summary(summary, template=template,
                                                                custom_prompt=custom_prompt)

    def interview_questions(self, diff: str) -> str:
        return self._provider.interview_questions(diff)

    def interview_generate(self, answers: str, diff: str, template: str | None = None) -> str:
        return self._provider.interview_generate(answers, diff, template=template)

    def check_provider_health(self) -> tuple[bool, str]:
        return self._provider.health_check()
