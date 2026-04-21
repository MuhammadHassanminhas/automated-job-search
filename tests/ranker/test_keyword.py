"""Tests for app.ranker.keyword — keyword_score function."""
import pytest
from hypothesis import given, settings
import hypothesis.strategies as st

from app.ranker.keyword import keyword_score


def test_empty_skills_returns_zero():
    """Empty skills list must return 0.0."""
    result = keyword_score([], "Python ML TensorFlow role")
    assert result == 0.0


def test_empty_description_returns_zero():
    """Empty description must return 0.0."""
    result = keyword_score(["python", "ml"], "")
    assert result == 0.0


def test_whitespace_description_returns_zero():
    """Whitespace-only description must return 0.0."""
    result = keyword_score(["python", "ml"], "   \t\n  ")
    assert result == 0.0


def test_all_skills_present_returns_one():
    """All skills present in description must return 1.0."""
    skills = ["python", "tensorflow", "ml"]
    description = "Python ML TensorFlow role building production models"
    result = keyword_score(skills, description)
    assert result == pytest.approx(1.0)


def test_no_skills_present_returns_zero():
    """No skills present in description must return 0.0."""
    skills = ["java", "kotlin", "android"]
    description = "Python ML TensorFlow role building production models"
    result = keyword_score(skills, description)
    assert result == 0.0


def test_partial_skills_match():
    """2 out of 4 skills present → score == 0.5."""
    skills = ["python", "tensorflow", "java", "kotlin"]
    description = "Python and TensorFlow for ML pipelines"
    result = keyword_score(skills, description)
    assert result == pytest.approx(0.5)


def test_score_is_case_insensitive():
    """Skill matching must be case-insensitive."""
    skills = ["Python", "TensorFlow"]
    description = "python tensorflow ml"
    result = keyword_score(skills, description)
    assert result == pytest.approx(1.0)


@given(
    st.lists(st.text(min_size=1, max_size=20), min_size=0, max_size=10),
    st.text(min_size=0, max_size=500),
)
@settings(max_examples=100)
def test_score_always_in_unit_interval(skills, description):
    """Property: keyword_score always returns a value in [0.0, 1.0]."""
    result = keyword_score(skills, description)
    assert 0.0 <= result <= 1.0


@given(st.integers(min_value=1, max_value=8))
@settings(max_examples=30)
def test_score_monotonicity_n_matched(n_matched: int):
    """Property: score == n_matched / total_skills when n_matched skills are in description."""
    total_skills = 8
    # First n_matched skills are present in the description, rest are not
    all_skills = [f"skill{i}" for i in range(total_skills)]
    present = all_skills[:n_matched]
    absent = all_skills[n_matched:]

    # Build description that contains exactly the present skills
    description = " ".join(present) + " unrelated words here"

    # Verify absent skills are truly absent from description
    for s in absent:
        assert s not in description

    result = keyword_score(all_skills, description)
    expected = n_matched / total_skills
    assert result == pytest.approx(expected, abs=1e-9)
