"""LLM judge tests — B.1 spec."""
from __future__ import annotations

import json
import pytest
from hypothesis import given, settings as h_settings, HealthCheck
import hypothesis.strategies as st
from unittest.mock import MagicMock

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


def _groq_response(content: str) -> dict:
    return {
        "id": "test",
        "object": "chat.completion",
        "created": 1714000000,
        "model": "llama-3.3-70b-versatile",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    }


VALID_JUDGE_RESPONSE = json.dumps({
    "score": 85,
    "reasoning": "Strong match on Python and PyTorch skills required for ML engineering role.",
    "matched_skills": ["python", "pytorch", "numpy"],
})

SCORE_TOO_HIGH = json.dumps({"score": 150, "reasoning": "good", "matched_skills": []})
SCORE_NEGATIVE = json.dumps({"score": -5, "reasoning": "bad", "matched_skills": []})
MISSING_SCORE = json.dumps({"reasoning": "ok", "matched_skills": []})
MISSING_REASONING = json.dumps({"score": 50, "matched_skills": []})
NOT_JSON = "This is not valid JSON at all."
EMPTY_REASONING = json.dumps({"score": 50, "reasoning": "", "matched_skills": []})


class TestLLMJudgeOutputSchema:
    """judge_job returns correct schema; malformed JSON raises LLMJudgeParseError."""

    def test_valid_response_returns_judge_result(self) -> None:
        from app.ranker.llm_judge import judge_job, LLMJudgeResult

        mock_client = MagicMock()
        mock_client.complete = MagicMock(return_value=VALID_JUDGE_RESPONSE)

        result = judge_job(
            job_description="Python ML engineering internship requiring pytorch and numpy",
            candidate_skills=["python", "pytorch", "numpy"],
            client=mock_client,
            session=None,
        )
        assert isinstance(result, LLMJudgeResult)
        assert 0 <= result.score <= 100
        assert len(result.reasoning) > 0
        assert isinstance(result.matched_skills, list)

    def test_score_is_integer_in_0_100_range(self) -> None:
        from app.ranker.llm_judge import judge_job

        mock_client = MagicMock()
        mock_client.complete = MagicMock(return_value=VALID_JUDGE_RESPONSE)
        result = judge_job(
            job_description="Python ML role",
            candidate_skills=["python"],
            client=mock_client,
            session=None,
        )
        assert isinstance(result.score, int)
        assert 0 <= result.score <= 100

    def test_reasoning_is_non_empty_string(self) -> None:
        from app.ranker.llm_judge import judge_job

        mock_client = MagicMock()
        mock_client.complete = MagicMock(return_value=VALID_JUDGE_RESPONSE)
        result = judge_job("Python role", ["python"], mock_client, None)
        assert isinstance(result.reasoning, str)
        assert len(result.reasoning) > 0

    def test_matched_skills_is_list_of_strings(self) -> None:
        from app.ranker.llm_judge import judge_job

        mock_client = MagicMock()
        mock_client.complete = MagicMock(return_value=VALID_JUDGE_RESPONSE)
        result = judge_job("Python role", ["python"], mock_client, None)
        assert isinstance(result.matched_skills, list)
        for skill in result.matched_skills:
            assert isinstance(skill, str)

    @pytest.mark.parametrize("bad_response,desc", [
        (NOT_JSON, "not JSON"),
        (SCORE_TOO_HIGH, "score > 100"),
        (SCORE_NEGATIVE, "score < 0"),
        (MISSING_SCORE, "missing score"),
        (MISSING_REASONING, "missing reasoning"),
        (EMPTY_REASONING, "empty reasoning"),
        ("{}", "empty object"),
        ("null", "null"),
        ("[]", "array instead of object"),
    ])
    def test_malformed_response_raises_llm_judge_parse_error(
        self, bad_response: str, desc: str
    ) -> None:
        """Any malformed/schema-violating response raises LLMJudgeParseError — never silently accepted."""
        from app.ranker.llm_judge import judge_job, LLMJudgeParseError

        mock_client = MagicMock()
        mock_client.complete = MagicMock(return_value=bad_response)
        with pytest.raises(LLMJudgeParseError, match=r".+"):
            judge_job("Python role", ["python"], mock_client, None)

    @given(
        st.text(min_size=1, max_size=200),
        st.lists(st.text(min_size=2, max_size=20), min_size=1, max_size=10),
    )
    @h_settings(max_examples=10, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_valid_response_never_raises_property(
        self, job_desc: str, skills: list[str]
    ) -> None:
        """Property: valid judge JSON never causes exception."""
        from app.ranker.llm_judge import judge_job

        valid = json.dumps({"score": 50, "reasoning": "ok match", "matched_skills": skills[:2]})
        mock_client = MagicMock()
        mock_client.complete = MagicMock(return_value=valid)
        result = judge_job(job_desc, skills, mock_client, None)
        assert 0 <= result.score <= 100
