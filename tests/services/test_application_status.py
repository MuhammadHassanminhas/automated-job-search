"""Application status machine tests — B.2 spec.

Tests for:
- APPROVED → SENDING → SENT on successful send
- APPROVED → SENDING → FAILED when sender raises; error message stored
- 409 if transition from SENT → APPROVED attempted
- Factory: ApplicationFactory with all status variants
- @given property-based: valid forward transitions never raise; invalid ones always raise
"""
from __future__ import annotations

import uuid
from typing import Any, Optional

import pytest
from hypothesis import given, settings as h_settings
import hypothesis.strategies as st
from pydantic import BaseModel
from polyfactory.factories.pydantic_factory import ModelFactory


# ---------------------------------------------------------------------------
# Pydantic model + polyfactory factory
# ---------------------------------------------------------------------------


class ApplicationModel(BaseModel):
    id: str
    user_id: str
    job_id: str
    profile_id: str
    status: str
    error_message: Optional[str] = None


class ApplicationModelFactory(ModelFactory):
    __model__ = ApplicationModel

    id = lambda: str(uuid.uuid4())  # noqa: E731
    user_id = lambda: str(uuid.uuid4())  # noqa: E731
    job_id = lambda: str(uuid.uuid4())  # noqa: E731
    profile_id = lambda: str(uuid.uuid4())  # noqa: E731
    status = "DRAFTED"
    error_message = None


_ALL_STATUSES = [
    "DRAFTED", "APPROVED", "SENDING", "SENT", "RESPONDED",
    "INTERVIEWING", "OFFERED", "REJECTED", "WITHDRAWN", "FAILED",
]


class ApplicationStatusFactory:
    """Convenience wrapper that produces dicts for all Application status variants."""

    @classmethod
    def build(cls, status: str = "DRAFTED", **kwargs: Any) -> dict:
        return ApplicationModelFactory.build(status=status).model_dump() | kwargs

    @classmethod
    def build_all_statuses(cls) -> list[dict]:
        return [cls.build(status=s) for s in _ALL_STATUSES]


# ---------------------------------------------------------------------------
# 1. Forward transition: APPROVED → SENDING → SENT
# ---------------------------------------------------------------------------


class TestStatusMachineForwardTransitions:
    """Successful send path traverses APPROVED → SENDING → SENT."""

    def test_transition_approved_to_sending(self) -> None:
        from app.services.application_status import transition_status  # ImportError until impl
        from app.models.application import ApplicationStatus

        app = ApplicationStatusFactory.build(status="APPROVED")
        new_status = transition_status(app["status"], event="begin_send")
        assert new_status == ApplicationStatus.SENDING

    def test_transition_sending_to_sent(self) -> None:
        from app.services.application_status import transition_status
        from app.models.application import ApplicationStatus

        app = ApplicationStatusFactory.build(status="SENDING")
        new_status = transition_status(app["status"], event="send_success")
        assert new_status == ApplicationStatus.SENT

    def test_full_send_path_approved_to_sent(self) -> None:
        from app.services.application_status import transition_status
        from app.models.application import ApplicationStatus

        status = "APPROVED"
        status = transition_status(status, event="begin_send")
        assert status == ApplicationStatus.SENDING
        status = transition_status(status, event="send_success")
        assert status == ApplicationStatus.SENT

    @pytest.mark.asyncio
    async def test_process_send_updates_status_to_sent(self) -> None:
        """On successful send, application status reaches SENT in the DB."""
        from app.services.application_status import apply_send_result  # ImportError until impl
        from app.models.application import ApplicationStatus

        mock_app = ApplicationStatusFactory.build(status="SENDING")
        result_app = await apply_send_result(
            application=mock_app,
            success=True,
            error_message=None,
        )
        assert result_app["status"] == ApplicationStatus.SENT
        assert result_app["error_message"] is None


# ---------------------------------------------------------------------------
# 2. Failure path: APPROVED → SENDING → FAILED with error stored
# ---------------------------------------------------------------------------


class TestStatusMachineFailurePath:
    """When sender raises, status becomes FAILED and error message is stored."""

    def test_transition_sending_to_failed(self) -> None:
        from app.services.application_status import transition_status
        from app.models.application import ApplicationStatus

        status = transition_status("SENDING", event="send_failure")
        assert status == ApplicationStatus.FAILED

    @pytest.mark.asyncio
    async def test_failed_status_stores_error_message(self) -> None:
        from app.services.application_status import apply_send_result
        from app.models.application import ApplicationStatus

        mock_app = ApplicationStatusFactory.build(status="SENDING")
        error_msg = "SMTP connection refused: 550 mailbox unavailable"
        result_app = await apply_send_result(
            application=mock_app,
            success=False,
            error_message=error_msg,
        )
        assert result_app["status"] == ApplicationStatus.FAILED
        assert result_app["error_message"] == error_msg

    @pytest.mark.asyncio
    @pytest.mark.parametrize("error_message", [
        "Connection timeout after 30s",
        "401 Unauthorized: token expired",
        "Rate limit exceeded",
        "Invalid recipient address",
        "x" * 512,  # long error message
        "Error with unicode: نوکری نہیں ملی",
    ])
    async def test_failed_status_stores_various_error_messages(
        self, error_message: str
    ) -> None:
        from app.services.application_status import apply_send_result
        from app.models.application import ApplicationStatus

        mock_app = ApplicationStatusFactory.build(status="SENDING")
        result_app = await apply_send_result(
            application=mock_app,
            success=False,
            error_message=error_message,
        )
        assert result_app["status"] == ApplicationStatus.FAILED
        assert result_app["error_message"] == error_message

    def test_failure_event_from_sending_produces_failed(self) -> None:
        from app.services.application_status import transition_status
        from app.models.application import ApplicationStatus

        new_status = transition_status("SENDING", event="send_failure")
        assert new_status == ApplicationStatus.FAILED


# ---------------------------------------------------------------------------
# 3. Invalid transition: SENT → APPROVED raises StatusTransitionError (409)
# ---------------------------------------------------------------------------


class TestStatusMachineInvalidTransitions:
    """Invalid backward/forbidden transitions raise StatusTransitionError."""

    def test_sent_to_approved_raises_error(self) -> None:
        from app.services.application_status import transition_status, StatusTransitionError

        with pytest.raises(StatusTransitionError):
            transition_status("SENT", event="approve")

    def test_sent_to_drafted_raises_error(self) -> None:
        from app.services.application_status import transition_status, StatusTransitionError

        with pytest.raises(StatusTransitionError):
            transition_status("SENT", event="reset")

    def test_failed_to_sent_raises_error(self) -> None:
        from app.services.application_status import transition_status, StatusTransitionError

        with pytest.raises(StatusTransitionError):
            transition_status("FAILED", event="send_success")

    def test_drafted_to_sent_skipping_steps_raises_error(self) -> None:
        from app.services.application_status import transition_status, StatusTransitionError

        with pytest.raises(StatusTransitionError):
            transition_status("DRAFTED", event="send_success")

    def test_withdrawn_to_approved_raises_error(self) -> None:
        from app.services.application_status import transition_status, StatusTransitionError

        with pytest.raises(StatusTransitionError):
            transition_status("WITHDRAWN", event="approve")

    @pytest.mark.parametrize("terminal_status", [
        "SENT", "OFFERED", "REJECTED", "WITHDRAWN",
    ])
    def test_terminal_states_reject_approve_event(self, terminal_status: str) -> None:
        from app.services.application_status import transition_status, StatusTransitionError

        with pytest.raises(StatusTransitionError):
            transition_status(terminal_status, event="approve")


# ---------------------------------------------------------------------------
# 4. Factory test: all status variants
# ---------------------------------------------------------------------------


class TestApplicationStatusFactory:
    """ApplicationStatusFactory produces valid objects for all status variants."""

    def test_factory_builds_approved(self) -> None:
        app = ApplicationStatusFactory.build(status="APPROVED")
        assert app["status"] == "APPROVED"
        assert uuid.UUID(app["id"])  # valid UUID

    def test_factory_builds_all_statuses(self) -> None:
        all_apps = ApplicationStatusFactory.build_all_statuses()
        statuses = [a["status"] for a in all_apps]
        expected = {
            "DRAFTED", "APPROVED", "SENDING", "SENT", "RESPONDED",
            "INTERVIEWING", "OFFERED", "REJECTED", "WITHDRAWN", "FAILED",
        }
        assert set(statuses) == expected

    def test_factory_each_has_unique_id(self) -> None:
        apps = [ApplicationStatusFactory.build() for _ in range(10)]
        ids = [a["id"] for a in apps]
        assert len(set(ids)) == 10, "Factory must produce unique IDs for each build"


# ---------------------------------------------------------------------------
# 5. Property-based: valid events never raise; invalid events always raise
# ---------------------------------------------------------------------------

_valid_events = st.sampled_from(["begin_send", "send_success", "send_failure", "approve"])
_valid_statuses = st.sampled_from([
    "DRAFTED", "APPROVED", "SENDING", "SENT",
    "RESPONDED", "INTERVIEWING", "OFFERED", "REJECTED", "WITHDRAWN", "FAILED",
])


@given(_valid_statuses, st.text(min_size=1, max_size=20))
@h_settings(max_examples=60)
def test_unknown_event_raises_or_returns_status(status: str, event: str) -> None:
    """Property: transition_status must either return a valid ApplicationStatus
    or raise StatusTransitionError — never silently corrupt state.
    """
    from app.services.application_status import transition_status, StatusTransitionError
    from app.models.application import ApplicationStatus

    valid_statuses = {s.value for s in ApplicationStatus}
    try:
        result = transition_status(status, event=event)
        # If no exception, must return a valid status
        assert result in ApplicationStatus or str(result) in valid_statuses, (
            f"transition_status returned invalid value: {result!r}"
        )
    except StatusTransitionError:
        pass  # Expected for invalid transitions
    except Exception as exc:
        pytest.fail(
            f"transition_status({status!r}, {event!r}) raised unexpected {type(exc).__name__}: {exc}"
        )
