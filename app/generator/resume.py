from __future__ import annotations

import pathlib

from app.llm.client import LLMClient

_PROMPT_PATH = pathlib.Path(__file__).parent / "prompts" / "resume.v1.txt"


def build_resume_prompt(
    base_md: str,
    job_title: str,
    company: str,
    skills: list[str],
) -> str:
    template = _PROMPT_PATH.read_text(encoding="utf-8")
    return template.format(
        base_resume=base_md,
        job_title=job_title,
        company=company,
        skills=", ".join(skills),
    )


def tailor_resume(
    base_md: str,
    job_title: str,
    company: str,
    skills: list[str],
    client: LLMClient,
) -> str:
    prompt = build_resume_prompt(base_md, job_title, company, skills)
    return client.complete(prompt)
