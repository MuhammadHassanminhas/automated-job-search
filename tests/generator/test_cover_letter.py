"""Tests for app.generator.cover_letter — write_cover_letter function."""
import pytest
from unittest.mock import MagicMock

from app.generator.cover_letter import write_cover_letter  # noqa: F401 — must fail until impl exists


# ---------------------------------------------------------------------------
# 1. parameterized: cover letter contains company name and at least 2 skills
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "company,skills",
    [
        ("TestCorp", ["python", "nlp"]),
        ("AlphaTech", ["machine learning", "pytorch"]),
        ("Beta LLC", ["fastapi", "docker", "sql"]),
    ],
)
def test_cover_letter_contains_company_and_skills(company, skills):
    """write_cover_letter output contains company name and at least 2 matched skills."""
    mock_client = MagicMock()
    mock_client.complete.return_value = (
        f"Dear {company} team, I have skills in {', '.join(skills)}."
    )

    result = write_cover_letter(
        job_title="Engineer",
        company=company,
        matched_skills=skills,
        client=mock_client,
    )

    assert company in result, f"Company '{company}' not found in cover letter"

    skills_found = sum(1 for skill in skills if skill in result)
    assert skills_found >= 2, (
        f"Expected at least 2 skills in output, found {skills_found} from {skills}"
    )


# ---------------------------------------------------------------------------
# 2. test_cover_letter_nonempty — basic smoke test
# ---------------------------------------------------------------------------

def test_cover_letter_nonempty():
    """write_cover_letter returns a non-empty string."""
    mock_client = MagicMock()
    mock_client.complete.return_value = "Dear Hiring Manager, I am excited to apply."

    result = write_cover_letter(
        job_title="Data Scientist",
        company="OpenAI",
        matched_skills=["python", "statistics"],
        client=mock_client,
    )

    assert isinstance(result, str)
    assert len(result.strip()) > 0
