from __future__ import annotations

import pathlib

from app.llm.client import LLMClient

_PROMPT_PATH = pathlib.Path(__file__).parent / "prompts" / "cold_email.v1.txt"


def build_cold_email_prompt(job_title: str, company: str) -> str:
    template = _PROMPT_PATH.read_text(encoding="utf-8")
    return template.format(job_title=job_title, company=company)


def parse_cold_email(llm_output: str) -> tuple[str, str]:
    """Parse LLM output into (subject, body) and enforce length limits."""
    lines = llm_output.strip().splitlines()

    subject = ""
    body_lines: list[str] = []
    body_started = False

    for line in lines:
        if not body_started and line.startswith("Subject:"):
            subject = line[len("Subject:"):].strip()
        elif not body_started and subject:
            # Skip the blank separator line, then body starts
            if line.strip():
                body_lines.append(line)
                body_started = True
        else:
            body_lines.append(line)

    body = "\n".join(body_lines).strip()

    # Enforce limits regardless of LLM output
    subject = subject[:70]
    body = " ".join(body.split()[:200])

    return subject, body


def write_cold_email(
    job_title: str,
    company: str,
    client: LLMClient,
) -> tuple[str, str]:
    prompt = build_cold_email_prompt(job_title, company)
    raw = client.complete(prompt)
    return parse_cold_email(raw)
