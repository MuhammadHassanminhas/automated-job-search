"""B.3 failing tests — argon2id parameter enforcement.

Current state: app/auth/session.py uses CryptContext(schemes=["argon2"]) with
DEFAULT parameters. Required: argon2id with t=3, m=65536, p=4.

These tests FAIL because:
- Current hash uses argon2i (not argon2id) with default params (t=2, m=102400, p=8 or similar).
- extract_parameters(hash).type != Type.ID
- extract_parameters(hash).time_cost != 3
- etc.
"""
from __future__ import annotations

from hypothesis import given, settings as h_settings
import hypothesis.strategies as st
from argon2 import extract_parameters, Type

from app.auth.session import hash_password


# ---------------------------------------------------------------------------
# Static parameter tests
# ---------------------------------------------------------------------------


class TestArgon2idParams:
    """hash_password must produce argon2id hashes with t=3, m=65536, p=4."""

    def test_hash_uses_argon2id_type(self) -> None:
        h = hash_password("test_password_static")
        params = extract_parameters(h)
        assert params.type == Type.ID, (
            f"Expected argon2id (Type.ID), got {params.type!r}. "
            "Update CryptContext to use argon2id."
        )

    def test_hash_time_cost_is_3(self) -> None:
        h = hash_password("time_cost_check_pw")
        params = extract_parameters(h)
        assert params.time_cost == 3, (
            f"Expected time_cost=3, got {params.time_cost}. "
            "Set argon2__time_cost=3 in CryptContext."
        )

    def test_hash_memory_cost_is_65536(self) -> None:
        h = hash_password("memory_cost_check_pw")
        params = extract_parameters(h)
        assert params.memory_cost == 65536, (
            f"Expected memory_cost=65536 (64 MiB), got {params.memory_cost}. "
            "Set argon2__memory_cost=65536 in CryptContext."
        )

    def test_hash_parallelism_is_4(self) -> None:
        h = hash_password("parallelism_check_pw")
        params = extract_parameters(h)
        assert params.parallelism == 4, (
            f"Expected parallelism=4, got {params.parallelism}. "
            "Set argon2__parallelism=4 in CryptContext."
        )

    def test_hash_starts_with_argon2id_prefix(self) -> None:
        """MCF hash string must begin with $argon2id$ — not $argon2i$ or $argon2d$."""
        h = hash_password("prefix_check_pw")
        assert h.startswith("$argon2id$"), (
            f"Expected hash to start with '$argon2id$', got prefix: {h[:20]!r}"
        )

    def test_all_required_params_simultaneously(self) -> None:
        """Single call verifying all four required attributes at once."""
        h = hash_password("combined_check_pw_abc")
        params = extract_parameters(h)
        failures: list[str] = []
        if params.type != Type.ID:
            failures.append(f"type={params.type!r} (want Type.ID)")
        if params.time_cost != 3:
            failures.append(f"time_cost={params.time_cost} (want 3)")
        if params.memory_cost != 65536:
            failures.append(f"memory_cost={params.memory_cost} (want 65536)")
        if params.parallelism != 4:
            failures.append(f"parallelism={params.parallelism} (want 4)")
        assert not failures, "argon2 parameter mismatches: " + ", ".join(failures)


# ---------------------------------------------------------------------------
# Property test: ANY password always hashes with required params
# ---------------------------------------------------------------------------


@given(st.text(min_size=1, max_size=72))
@h_settings(max_examples=30)
def test_any_password_produces_correct_argon2id_params(password: str) -> None:
    """Property: hash_password(pw) always yields argon2id with t=3 m=65536 p=4
    regardless of the input password content.
    """
    h = hash_password(password)
    params = extract_parameters(h)
    failures: list[str] = []
    if params.type != Type.ID:
        failures.append(f"type={params.type!r} (want Type.ID)")
    if params.time_cost != 3:
        failures.append(f"time_cost={params.time_cost} (want 3)")
    if params.memory_cost != 65536:
        failures.append(f"memory_cost={params.memory_cost} (want 65536)")
    if params.parallelism != 4:
        failures.append(f"parallelism={params.parallelism} (want 4)")
    assert not failures, (
        f"password={password!r}: argon2 param mismatches: " + ", ".join(failures)
    )
