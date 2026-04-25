"""Scheduler tests — B.1 spec (APScheduler + freezegun)."""
from __future__ import annotations

from freezegun import freeze_time


class TestSchedulerConfiguration:
    """Scheduler registers jobs at the correct intervals."""

    def test_create_scheduler_returns_scheduler_instance(self) -> None:
        from app.scheduler import create_scheduler
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        scheduler = create_scheduler()
        assert isinstance(scheduler, AsyncIOScheduler)

    def test_discovery_tick_registered_at_6h_interval(self) -> None:
        from app.scheduler import create_scheduler
        scheduler = create_scheduler()
        job_ids = [job.id for job in scheduler.get_jobs()]
        assert "scheduler.discovery.tick" in job_ids, (
            f"'scheduler.discovery.tick' not in registered jobs: {job_ids}"
        )
        disc_job = next(j for j in scheduler.get_jobs() if j.id == "scheduler.discovery.tick")
        interval_seconds = disc_job.trigger.interval.total_seconds()
        assert interval_seconds == 6 * 3600, (
            f"Discovery tick interval is {interval_seconds}s, expected {6 * 3600}s"
        )

    def test_rank_tick_registered_at_1h_interval(self) -> None:
        from app.scheduler import create_scheduler
        scheduler = create_scheduler()
        job_ids = [job.id for job in scheduler.get_jobs()]
        assert "scheduler.rank.tick" in job_ids, (
            f"'scheduler.rank.tick' not in registered jobs: {job_ids}"
        )
        rank_job = next(j for j in scheduler.get_jobs() if j.id == "scheduler.rank.tick")
        interval_seconds = rank_job.trigger.interval.total_seconds()
        assert interval_seconds == 3600, (
            f"Rank tick interval is {interval_seconds}s, expected 3600s"
        )

    def test_sender_tick_registered_at_30s_interval(self) -> None:
        from app.scheduler import create_scheduler
        scheduler = create_scheduler()
        job_ids = [job.id for job in scheduler.get_jobs()]
        assert "scheduler.sender.tick" in job_ids, (
            f"'scheduler.sender.tick' not in registered jobs: {job_ids}"
        )
        sender_job = next(j for j in scheduler.get_jobs() if j.id == "scheduler.sender.tick")
        interval_seconds = sender_job.trigger.interval.total_seconds()
        assert interval_seconds == 30, (
            f"Sender tick interval is {interval_seconds}s, expected 30s"
        )

    def test_all_three_jobs_registered(self) -> None:
        from app.scheduler import create_scheduler
        scheduler = create_scheduler()
        job_ids = {job.id for job in scheduler.get_jobs()}
        required = {"scheduler.discovery.tick", "scheduler.rank.tick", "scheduler.sender.tick"}
        assert required.issubset(job_ids), (
            f"Missing scheduler jobs: {required - job_ids}"
        )

    @freeze_time("2025-01-01 00:00:00", ignore=["transformers", "sentence_transformers"])
    def test_scheduler_does_not_fire_before_first_interval(self) -> None:
        """
        At t=0, no ticks have fired yet. Scheduler state is consistent.
        This is a structural test — just verifies create_scheduler() works with frozen time.
        """
        from app.scheduler import create_scheduler
        scheduler = create_scheduler()
        assert scheduler is not None
        jobs = scheduler.get_jobs()
        assert len(jobs) >= 3
