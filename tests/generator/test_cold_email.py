"""Tests for app.generator.cold_email — write_cold_email function."""
import pytest
from dataclasses import dataclass
from unittest.mock import MagicMock
from hypothesis import given, settings
import hypothesis.strategies as st
from polyfactory.factories.dataclass_factory import DataclassFactory

from app.generator.cold_email import write_cold_email  # noqa: F401 — must fail until impl exists


# ---------------------------------------------------------------------------
# Helper dataclass + factory for job variants
# ---------------------------------------------------------------------------

@dataclass
class JobVariant:
    job_title: str
    company: str


class JobVariantFactory(DataclassFactory):
    __model__ = JobVariant


# Fixed valid LLM response for cold-email tests
_VALID_EMAIL_RESPONSE = "Subject: Apply Now\n\nBody: " + ("word " * 150)


# ---------------------------------------------------------------------------
# 1. parameterized: subject <= 70 chars, body <= 200 words
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "job_title,company",
    [
        ("ML Intern", "DeepMind"),
        ("Software Engineer Intern", "Google"),
        ("AI Research Intern", "OpenAI"),
        ("Backend Intern", "Stripe"),
        ("Data Science Intern", "Meta"),
    ],
)
def test_cold_email_length_constraints(job_title, company):
    """write_cold_email returns subject <= 70 chars and body <= 200 words."""
    mock_client = MagicMock()
    mock_client.complete.return_value = _VALID_EMAIL_RESPONSE

    subject, body = write_cold_email(
        job_title=job_title,
        company=company,
        client=mock_client,
    )

    assert len(subject) <= 70, (
        f"Subject too long ({len(subject)} chars): '{subject}'"
    )
    assert len(body.split()) <= 200, (
        f"Body too long ({len(body.split())} words)"
    )


# ---------------------------------------------------------------------------
# 2. hypothesis: subject always <= 70 chars for any job_title/company
# ---------------------------------------------------------------------------

@given(
    st.text(min_size=1, max_size=50),
    st.text(min_size=1, max_size=50),
)
@settings(max_examples=50)
def test_cold_email_subject_max_length_hypothesis(job_title: str, company: str):
    """Hypothesis: subject length <= 70 for any valid job title and company."""
    mock_client = MagicMock()
    mock_client.complete.return_value = _VALID_EMAIL_RESPONSE

    subject, _body = write_cold_email(
        job_title=job_title,
        company=company,
        client=mock_client,
    )

    assert len(subject) <= 70, (
        f"Subject too long ({len(subject)} chars): '{subject}'"
    )
