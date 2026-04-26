from __future__ import annotations

from app.models.application import ApplicationStatus


class StatusTransitionError(Exception):
    """Raised for forbidden status transitions."""


# Transition table: (current_status, event) -> new_status
_TRANSITIONS: dict[tuple[str, str], ApplicationStatus] = {
    ("DRAFTED", "approve"): ApplicationStatus.APPROVED,
    ("APPROVED", "begin_send"): ApplicationStatus.SENDING,
    ("SENDING", "send_success"): ApplicationStatus.SENT,
    ("SENDING", "send_failure"): ApplicationStatus.FAILED,
    ("SENT", "respond"): ApplicationStatus.RESPONDED,
    ("RESPONDED", "interview"): ApplicationStatus.INTERVIEWING,
    ("INTERVIEWING", "offer"): ApplicationStatus.OFFERED,
    ("INTERVIEWING", "reject"): ApplicationStatus.REJECTED,
    # withdraw from any non-terminal state
    ("DRAFTED", "withdraw"): ApplicationStatus.WITHDRAWN,
    ("APPROVED", "withdraw"): ApplicationStatus.WITHDRAWN,
    ("SENDING", "withdraw"): ApplicationStatus.WITHDRAWN,
    ("RESPONDED", "withdraw"): ApplicationStatus.WITHDRAWN,
    ("FAILED", "withdraw"): ApplicationStatus.WITHDRAWN,
}


def transition_status(status: str, event: str) -> ApplicationStatus:
    """Return the new ApplicationStatus or raise StatusTransitionError."""
    key = (status, event)
    if key not in _TRANSITIONS:
        raise StatusTransitionError(
            f"Invalid transition: status={status!r}, event={event!r}"
        )
    return _TRANSITIONS[key]


async def apply_send_result(
    application: dict,
    success: bool,
    error_message: str | None = None,
) -> dict:
    """
    Given application dict with status=SENDING:
    - If success: return dict with status=SENT, error_message=None
    - If not success: return dict with status=FAILED, error_message=error_message
    Does NOT touch the DB (pure logic for testability).
    """
    result = dict(application)
    if success:
        result["status"] = ApplicationStatus.SENT
        result["error_message"] = None
    else:
        result["status"] = ApplicationStatus.FAILED
        result["error_message"] = error_message
    return result
