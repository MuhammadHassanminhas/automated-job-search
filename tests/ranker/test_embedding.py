"""Tests for app.ranker.embedding — encode_texts and cosine_similarity."""
import math

from app.ranker.embedding import encode_texts, cosine_similarity

EXPECTED_DIM = 384


def _norm(vec: list[float]) -> float:
    """Compute L2 norm of a vector."""
    return math.sqrt(sum(x * x for x in vec))


def test_identical_texts_high_cosine():
    """Identical texts must have cosine similarity > 0.99."""
    text = "Python machine learning engineer with TensorFlow experience"
    vecs = encode_texts([text, text])
    assert len(vecs) == 2
    sim = cosine_similarity(vecs[0], vecs[1])
    assert sim > 0.99, f"Expected cosine > 0.99 for identical texts, got {sim}"


def test_semantically_distant_texts_low_cosine():
    """Semantically distant texts (ML vs plumbing) must have cosine < 0.5."""
    texts = [
        "machine learning deep learning neural networks python tensorflow pytorch",
        "plumbing pipe wrench water heater drain toilet bathroom repair",
    ]
    vecs = encode_texts(texts)
    sim = cosine_similarity(vecs[0], vecs[1])
    assert sim < 0.5, f"Expected cosine < 0.5 for distant texts, got {sim}"


def test_batch_64_returns_64_vectors():
    """Batch of 64 texts must return exactly 64 vectors."""
    texts = [f"internship position {i} at company {i}" for i in range(64)]
    vecs = encode_texts(texts)
    assert len(vecs) == 64


def test_batch_64_each_vector_length_384():
    """Each vector in a batch of 64 must have length 384."""
    texts = [f"job description number {i}" for i in range(64)]
    vecs = encode_texts(texts)
    for i, vec in enumerate(vecs):
        assert len(vec) == EXPECTED_DIM, (
            f"Vector {i} has length {len(vec)}, expected {EXPECTED_DIM}"
        )


def test_output_vectors_unit_normalized():
    """All output vectors must be unit-normalized (norm ≈ 1.0)."""
    texts = [
        "Python developer",
        "machine learning engineer",
        "data scientist with pandas",
        "backend software engineer",
    ]
    vecs = encode_texts(texts)
    for i, vec in enumerate(vecs):
        n = _norm(vec)
        assert abs(n - 1.0) < 1e-4, f"Vector {i} has norm {n}, expected ~1.0"


def test_encode_empty_list():
    """Encoding empty list must return empty list."""
    result = encode_texts([])
    assert result == []


def test_single_text_returns_one_vector():
    """Single text must return a list with exactly one vector of length 384."""
    vecs = encode_texts(["machine learning internship"])
    assert len(vecs) == 1
    assert len(vecs[0]) == EXPECTED_DIM


def test_cosine_similarity_same_vector_is_one():
    """cosine_similarity of a vector with itself must equal 1.0."""
    vecs = encode_texts(["deep learning researcher"])
    sim = cosine_similarity(vecs[0], vecs[0])
    assert abs(sim - 1.0) < 1e-4


def test_cosine_similarity_range():
    """cosine_similarity must return a value in [-1.0, 1.0]."""
    texts = ["python ml engineer", "java enterprise developer"]
    vecs = encode_texts(texts)
    sim = cosine_similarity(vecs[0], vecs[1])
    assert -1.0 <= sim <= 1.0
