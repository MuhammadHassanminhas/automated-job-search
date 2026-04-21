"""Tests for app.services.profile — extract_skills function."""
import pytest

from app.services.profile import extract_skills

RESUME_SAMPLES = [
    (
        "short",
        "Python developer with 2 years experience. Skills: Python, FastAPI, PostgreSQL.",
    ),
    (
        "long",
        """
        Senior Software Engineer with 5+ years of experience in Python, Django, FastAPI,
        PostgreSQL, Redis, Docker, Kubernetes, AWS, and CI/CD pipelines.
        Strong background in machine learning with TensorFlow, PyTorch, scikit-learn.
        Experienced in REST APIs, microservices, and agile development.
        Education: BS Computer Science. GPA: 3.8/4.0.
        Projects: Built real-time recommendation engine using Python and TensorFlow.
        """,
    ),
    (
        "unicode",
        "Développeur Python avec expérience en Django, PostgreSQL, et Docker. "
        "Compétences: Python, JavaScript, TypeScript, React, Node.js. "
        "言語: Python, Java, C++",
    ),
    (
        "US resume",
        """
        Jane Smith | jane@email.com | New York, NY
        SKILLS: Python, R, SQL, TensorFlow, PyTorch, Spark, Hadoop
        EXPERIENCE: Data Scientist at Google (2021-present)
        - Built ML pipelines using Python and TensorFlow
        - Deployed models with Docker and Kubernetes on AWS
        EDUCATION: MS Data Science, Stanford University
        """,
    ),
    (
        "PK resume",
        """
        Muhammad Ali | Lahore, Pakistan | ali@email.com
        Technical Skills: Python, Machine Learning, Deep Learning, NLP, FastAPI, MongoDB
        Experience: Junior AI Engineer at Systems Ltd (2023-present)
        - Developed chatbot using Python and NLP libraries
        - Integrated REST APIs with FastAPI framework
        Education: BS Computer Science, LUMS, 2022
        """,
    ),
]


@pytest.mark.parametrize("label,resume_text", RESUME_SAMPLES, ids=[s[0] for s in RESUME_SAMPLES])
def test_extract_skills_non_empty(label, resume_text):
    """extract_skills must return a non-empty list for each resume sample."""
    skills = extract_skills(resume_text)
    assert isinstance(skills, list), f"[{label}] Expected list, got {type(skills)}"
    assert len(skills) > 0, f"[{label}] Expected at least one skill, got empty list"


@pytest.mark.parametrize("label,resume_text", RESUME_SAMPLES, ids=[s[0] for s in RESUME_SAMPLES])
def test_extract_skills_each_skill_appears_in_resume(label, resume_text):
    """Every extracted skill must appear in the resume text (case-insensitive)."""
    skills = extract_skills(resume_text)
    resume_lower = resume_text.lower()
    for skill in skills:
        assert skill.lower() in resume_lower, (
            f"[{label}] Extracted skill '{skill}' not found in resume text"
        )


@pytest.mark.parametrize("label,resume_text", RESUME_SAMPLES, ids=[s[0] for s in RESUME_SAMPLES])
def test_extract_skills_no_duplicates(label, resume_text):
    """Extracted skills list must not contain duplicates (case-insensitive)."""
    skills = extract_skills(resume_text)
    lower_skills = [s.lower() for s in skills]
    assert len(lower_skills) == len(set(lower_skills)), (
        f"[{label}] Duplicate skills found: {skills}"
    )


@pytest.mark.parametrize(
    "blank_input",
    ["", "   ", "\t\n  ", "\n\n\n"],
    ids=["empty", "spaces", "tabs_newlines", "newlines"],
)
def test_extract_skills_blank_input_returns_empty(blank_input):
    """Blank or whitespace-only input must return an empty list."""
    result = extract_skills(blank_input)
    assert result == [], f"Expected empty list for blank input, got {result!r}"
