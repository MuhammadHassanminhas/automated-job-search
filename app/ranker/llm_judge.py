from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class LLMJudgeResult:
    score: int
    reasoning: str
    matched_skills: list[str]


class LLMJudgeParseError(Exception):
    ...


_PROMPT_TEMPLATE = (
    Path(__file__).parent.parent / "generator" / "prompts" / "llm_judge.v1.txt"
).read_text()


def _validate_result(data: Any) -> LLMJudgeResult:
    """Parse and validate judge JSON. Raises LLMJudgeParseError on any violation."""
    if not isinstance(data, dict):
        raise LLMJudgeParseError(f"Expected dict, got {type(data).__name__}")
    if "score" not in data:
        raise LLMJudgeParseError("Missing 'score' key")
    if "reasoning" not in data:
        raise LLMJudgeParseError("Missing 'reasoning' key")
    score = data["score"]
    reasoning = data["reasoning"]
    matched = data.get("matched_skills", [])
    if not isinstance(score, int) or isinstance(score, bool):
        raise LLMJudgeParseError(f"score must be int, got {type(score).__name__}")
    if not (0 <= score <= 100):
        raise LLMJudgeParseError(f"score {score} out of [0, 100]")
    if not isinstance(reasoning, str) or len(reasoning.strip()) == 0:
        raise LLMJudgeParseError("reasoning must be non-empty string")
    if not isinstance(matched, list):
        raise LLMJudgeParseError("matched_skills must be a list")
    return LLMJudgeResult(
        score=score,
        reasoning=reasoning,
        matched_skills=[str(s) for s in matched],
    )


def judge_job(
    job_description: str,
    candidate_skills: list[str],
    client: Any,
    session: Any,  # reserved for cache look-up in Phase B.2
) -> LLMJudgeResult:
    _ = session
    prompt = _PROMPT_TEMPLATE.format(
        job_description=job_description,
        candidate_skills=", ".join(candidate_skills),
    )
    raw = client.complete(prompt)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LLMJudgeParseError(f"Invalid JSON from LLM: {exc}") from exc
    return _validate_result(data)
