from __future__ import annotations


def keyword_score(skills: list[str], description: str) -> float:
    if not skills or not description:
        return 0.0
    desc_lower = description.lower()
    matched = sum(1 for s in skills if s.lower() in desc_lower)
    return matched / len(skills)
