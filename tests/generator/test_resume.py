"""Tests for app.generator.resume — tailor_resume function."""
from unittest.mock import MagicMock
from hypothesis import given, settings
import hypothesis.strategies as st

from app.generator.resume import tailor_resume  # noqa: F401 — must fail until impl exists


# ---------------------------------------------------------------------------
# 1. hypothesis property: all headings appear in output (mock echoes prompt)
# ---------------------------------------------------------------------------

@given(
    st.lists(
        st.text(min_size=1, max_size=20).filter(str.strip),
        min_size=1,
        max_size=5,
    )
)
@settings(max_examples=50)
def test_tailor_resume_all_headings_present(headings):
    """tailor_resume output contains every heading from base_md."""
    base_md = "\n".join(f"## {h}\n\nContent." for h in headings)
    mock_client = MagicMock()
    # Echo the prompt back so the output contains all headings
    mock_client.complete.side_effect = lambda prompt, **kwargs: prompt

    result = tailor_resume(
        base_md=base_md,
        job_title="Engineer",
        company="ACME",
        skills=["python"],
        client=mock_client,
    )

    for heading in headings:
        assert heading in result, f"Heading '{heading}' missing from output"


# ---------------------------------------------------------------------------
# 2. test_tailor_resume_nonempty — basic smoke test
# ---------------------------------------------------------------------------

def test_tailor_resume_nonempty():
    """tailor_resume returns a non-empty string."""
    mock_client = MagicMock()
    mock_client.complete.return_value = "Tailored resume content here."

    result = tailor_resume(
        base_md="## Summary\n\nExperienced engineer.",
        job_title="ML Engineer",
        company="DeepMind",
        skills=["python", "pytorch"],
        client=mock_client,
    )

    assert isinstance(result, str)
    assert len(result.strip()) > 0
