from __future__ import annotations

import httpx

from .base import LLMProvider, ReviewResult
from ..exceptions import ProviderError
from ..prompts import (REVIEW_RESPONSE_SCHEMA, get_commit_improve_prompt, get_generate_commit_prompt,
                       get_interview_questions_prompt, get_interview_generate_prompt,
                       get_analyze_diff_prompt, get_generate_from_summary_prompt)

_DEFAULT_TIMEOUT = 120.0


class EnterpriseProvider(LLMProvider):
    def __init__(
        self,
        base_url: str,
        api_path: str,
        model: str,
        auth_type: str = "bearer",
        auth_token: str = "",
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_path = api_path
        self._model = model
        self._headers = self._build_auth_headers(auth_type, auth_token)
        transport = httpx.HTTPTransport(retries=3)
        self._client = httpx.Client(timeout=timeout, headers=self._headers, transport=transport)

    @staticmethod
    def _build_auth_headers(auth_type: str, token: str) -> dict[str, str]:
        if auth_type == "bearer":
            return {"Authorization": f"Bearer {token}"}
        elif auth_type == "api-key":
            return {"X-API-Key": token}
        else:
            return {"Authorization": token}

    def health_check(self) -> tuple[bool, str]:
        try:
            resp = self._client.get(f"{self._base_url}/v1/models")
            if resp.status_code == 200:
                return True, "Connected"
            return False, f"HTTP {resp.status_code}"
        except httpx.ConnectError:
            return False, f"Connection refused: {self._base_url}"
        except httpx.TimeoutException:
            return False, f"Timeout connecting to {self._base_url}"
        except httpx.HTTPError as e:
            return False, str(e)

    def review_code(self, diff: str, prompt: str) -> ReviewResult:
        full_prompt = f"{prompt}\n\n{REVIEW_RESPONSE_SCHEMA}\n\nDiff:\n{diff}"
        content = self._chat(full_prompt)
        return self._parse_review(content)

    def improve_commit_msg(self, message: str, diff: str, template: str | None = None) -> str:
        prompt = get_commit_improve_prompt(message, diff, template=template)
        return self._chat(prompt).strip()

    def generate_commit_msg(self, diff: str, template: str | None = None) -> str:
        prompt = get_generate_commit_prompt(diff, template=template)
        return self._chat(prompt).strip()

    def interview_questions(self, diff: str) -> str:
        prompt = get_interview_questions_prompt(diff)
        return self._chat(prompt).strip()

    def interview_generate(self, answers: str, diff: str, template: str | None = None) -> str:
        prompt = get_interview_generate_prompt(answers, diff, template=template)
        return self._chat(prompt).strip()

    def analyze_diff(self, diff_stat: str, recent_commits: str, diff: str) -> str:
        prompt = get_analyze_diff_prompt(diff_stat, recent_commits, diff)
        return self._chat(prompt).strip()

    def generate_commit_msg_from_summary(self, summary: str, template: str | None = None,
                                         custom_prompt: str | None = None) -> str:
        prompt = get_generate_from_summary_prompt(summary, template=template, custom_prompt=custom_prompt)
        return self._chat(prompt).strip()

    def _chat(self, prompt: str) -> str:
        try:
            resp = self._client.post(
                f"{self._base_url}{self._api_path}",
                json={
                    "model": self._model,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, ValueError) as e:
            raise ProviderError(f"Enterprise API request failed: {e}") from e

