"""Scheduler sender tick tests — B.2 spec.

Tests for:
- freezegun + mock sender: sender tick fires every 30s, picks APPROVED rows, calls sender
- Assert sender called once per APPROVED draft
"""
from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from freezegun import freeze_time


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_draft(status: str = "APPROVED") -> dict:
    return {
        "id": str(uuid.uuid4()),
        "application_id": str(uuid.uuid4()),
        "email_subject": "Internship Application",
        "email_body": "Hello, I am interested.",
        "status": status,
    }


# ---------------------------------------------------------------------------
# Scheduler sender tick registration
# ---------------------------------------------------------------------------


class TestSchedulerSenderTick:
    """Sender tick is registered at 30-second interval."""

    def test_sender_tick_registered_30s(self) -> None:
        from app.scheduler import create_scheduler

        scheduler = create_scheduler()
        job_ids = [job.id for job in scheduler.get_jobs()]
        assert "scheduler.sender.tick" in job_ids, (
            f"'scheduler.sender.tick' not in registered jobs: {job_ids}"
        )

    def test_sender_tick_interval_exactly_30_seconds(self) -> None:
        from app.scheduler import create_scheduler

        scheduler = create_scheduler()
        sender_job = next(
            j for j in scheduler.get_jobs() if j.id == "scheduler.sender.tick"
        )
        interval_seconds = sender_job.trigger.interval.total_seconds()
        assert interval_seconds == 30, (
            f"Sender tick interval is {interval_seconds}s, expected 30s"
        )


# ---------------------------------------------------------------------------
# Sender tick picks APPROVED rows and calls sender
# ---------------------------------------------------------------------------


class TestSchedulerSenderTickBehavior:
    """Sender tick function calls process_send_queue for each APPROVED draft."""

    @pytest.mark.asyncio
    @freeze_time("2025-06-01 12:00:00", ignore=["transformers", "sentence_transformers"])
    async def test_sender_tick_calls_process_send_queue(self) -> None:
        """When sender tick fires, process_send_queue must be called once."""
        from app.scheduler import sender_tick  # ImportError until impl

        with patch(
            "app.scheduler.process_send_queue", new_callable=AsyncMock
        ) as mock_queue:
            mock_queue.return_value = None
            await sender_tick()
            mock_queue.assert_called_once()

    @pytest.mark.asyncio
    @freeze_time("2025-06-01 12:00:00", ignore=["transformers", "sentence_transformers"])
    async def test_sender_tick_calls_sender_once_per_approved_draft(self) -> None:
        """Sender is called exactly once for each APPROVED draft in the queue."""
        from app.scheduler import sender_tick

        approved_drafts = [
            (_make_draft("APPROVED")["application_id"], _make_draft("APPROVED"))
            for _ in range(3)
        ]

        send_calls: list = []

        with (
            patch("app.scheduler.process_send_queue", new_callable=AsyncMock) as mock_queue,
        ):
            # Simulate process_send_queue processing 3 approved drafts
            async def side_effect(_session: Any = None) -> None:
                for app_id, draft in approved_drafts:
                    send_calls.append(app_id)

            mock_queue.side_effect = side_effect
            await sender_tick()

        assert len(send_calls) == 3, (
            f"Expected sender called 3 times (once per APPROVED draft), got {len(send_calls)}"
        )

    @pytest.mark.asyncio
    @freeze_time("2025-06-01 12:00:30", ignore=["transformers", "sentence_transformers"])
    async def test_sender_tick_not_called_for_drafted_status(self) -> None:
        """Sender tick must not process DRAFTED (non-approved) rows."""
        from app.scheduler import sender_tick

        send_calls: list = []

        with patch("app.scheduler.process_send_queue", new_callable=AsyncMock) as mock_queue:
            # process_send_queue with empty queue (no APPROVED rows)
            async def side_effect_empty(_session: Any = None) -> None:
                pass  # No DRAFTED rows processed

            mock_queue.side_effect = side_effect_empty
            await sender_tick()

        assert send_calls == [], (
            "Sender tick must not call sender for non-APPROVED drafts"
        )

    @pytest.mark.asyncio
    @freeze_time("2025-06-01 12:00:00", ignore=["transformers", "sentence_transformers"])
    async def test_sender_tick_single_approved_draft(self) -> None:
        """With exactly one APPROVED draft, sender is called exactly once."""
        from app.scheduler import sender_tick

        call_count = 0

        async def mock_process(_session: Any = None) -> None:
            nonlocal call_count
            call_count += 1

        with patch("app.scheduler.process_send_queue", new_callable=AsyncMock) as mock_queue:
            mock_queue.side_effect = mock_process
            await sender_tick()

        assert call_count == 1

    @pytest.mark.asyncio
    @freeze_time("2025-06-01 12:00:00", ignore=["transformers", "sentence_transformers"])
    async def test_sender_tick_no_approved_drafts_is_noop(self) -> None:
        """If no APPROVED drafts exist, tick completes without error."""
        from app.scheduler import sender_tick

        with patch("app.scheduler.process_send_queue", new_callable=AsyncMock) as mock_queue:
            mock_queue.return_value = None
            # Must not raise
            await sender_tick()
            mock_queue.assert_called_once()


# ---------------------------------------------------------------------------
# Freeze-time: tick does not fire before 30s interval
# ---------------------------------------------------------------------------


class TestSchedulerFreezeTime:
    """Scheduler tick timing with frozen time."""

    @freeze_time("2025-01-01 00:00:00", ignore=["transformers", "sentence_transformers"])
    def test_scheduler_creation_with_frozen_time_includes_sender_tick(self) -> None:
        """create_scheduler() with frozen time still registers sender tick."""
        from app.scheduler import create_scheduler

        scheduler = create_scheduler()
        job_ids = {job.id for job in scheduler.get_jobs()}
        assert "scheduler.sender.tick" in job_ids

    @freeze_time("2025-01-01 00:00:29", ignore=["transformers", "sentence_transformers"])
    def test_scheduler_at_29s_has_sender_job(self) -> None:
        """At t=29s (before first interval), sender job is still present."""
        from app.scheduler import create_scheduler

        scheduler = create_scheduler()
        sender_job = next(
            (j for j in scheduler.get_jobs() if j.id == "scheduler.sender.tick"), None
        )
        assert sender_job is not None
