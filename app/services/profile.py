from __future__ import annotations

KNOWN_SKILLS = [
    "python", "javascript", "typescript", "java", "go", "rust", "c++", "c#",
    "ruby", "php", "swift", "kotlin", "scala", "r", "matlab",
    "react", "vue", "angular", "nextjs", "svelte",
    "fastapi", "django", "flask", "express", "spring", "laravel",
    "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
    "docker", "kubernetes", "aws", "gcp", "azure", "terraform",
    "pytorch", "tensorflow", "scikit-learn", "pandas", "numpy",
    "machine learning", "deep learning", "nlp", "computer vision",
    "sql", "graphql", "rest", "grpc",
    "git", "linux", "bash", "ci/cd", "devops",
    "node.js", "nodejs", "celery", "kafka",
]


def extract_skills(resume_text: str) -> list[str]:
    if not resume_text or not resume_text.strip():
        return []
    lower = resume_text.lower()
    found = []
    seen: set[str] = set()
    for skill in KNOWN_SKILLS:
        if skill in lower and skill not in seen:
            found.append(skill)
            seen.add(skill)
    return found
