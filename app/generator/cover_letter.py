from __future__ import annotations

import pathlib

from app.llm.client import LLMClient

_PROMPT_PATH = pathlib.Path(__file__).parent / "prompts" / "cover_letter.v1.txt"


def build_cover_letter_prompt(
    job_title: str,
    company: str,
    matched_skills: list[str],
) -> str:
    template = _PROMPT_PATH.read_text(encoding="utf-8")
    return template.format(
        job_title=job_title,
        company=company,
        skills=", ".join(matched_skills),
    )


def write_cover_letter(
    job_title: str,
    company: str,
    matched_skills: list[str],
    client: LLMClient,
) -> str:
    prompt = build_cover_letter_prompt(job_title, company, matched_skills)
    return client.complete(prompt)
