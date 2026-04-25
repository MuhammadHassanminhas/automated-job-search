from __future__ import annotations
import argparse
import asyncio
import hashlib
import pathlib
import time
import uuid


def cmd_discover(args: argparse.Namespace) -> None:
    from app.scrapers.remoteok import RemoteOKScraper
    from app.scrapers.internshala import InternshalasScraper
    from app.scrapers.rozee import RozeeScraper
    from app.services.dedup import dedup_jobs
    from app.models.job import Job, JobSource as JobSourceEnum
    from app.db import AsyncSessionFactory
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    if getattr(args, "all", False):
        raw_jobs = (
            RemoteOKScraper().run()
            + InternshalasScraper().run()
            + RozeeScraper().run()
        )
        source_label = "all"
    else:
        raw_jobs = RemoteOKScraper().run()
        source_label = args.source

    raw_jobs = raw_jobs[: args.limit]
    deduped = dedup_jobs(raw_jobs)

    source_map = {
        "remoteok": JobSourceEnum.REMOTEOK,
        JobSourceEnum.INTERNSHALA: JobSourceEnum.INTERNSHALA,
        JobSourceEnum.ROZEE: JobSourceEnum.ROZEE,
    }

    def _hash(rj) -> str:
        key = f"{rj.company.lower().strip()}|{rj.title.lower().strip()}|{(rj.location or '').lower().strip()}"
        return hashlib.sha256(key.encode()).hexdigest()

    async def _persist() -> int:
        saved = 0
        async with AsyncSessionFactory() as session:
            for rj in deduped:
                src = rj.source if isinstance(rj.source, JobSourceEnum) else source_map.get(rj.source, JobSourceEnum.REMOTEOK)
                stmt = (
                    pg_insert(Job)
                    .values(
                        id=uuid.uuid4(),
                        source=src,
                        external_id=rj.external_id,
                        url=rj.url,
                        title=rj.title,
                        company=rj.company,
                        location=rj.location,
                        description=rj.description,
                        remote_allowed=rj.remote_allowed,
                        posted_at=rj.posted_at,
                        hash=_hash(rj),
                    )
                    .on_conflict_do_nothing()
                )
                result = await session.execute(stmt)
                saved += result.rowcount
            await session.commit()
        return saved

    saved = asyncio.run(_persist())
    print(f"Discovered {len(deduped)} jobs from {source_label}, saved {saved} new")


def cmd_rank(args: argparse.Namespace) -> None:
    import logging
    from app.models.job import Job
    from app.models.profile import Profile
    from app.ranker.keyword import keyword_score
    from app.ranker.embedding import encode_texts, cosine_similarity
    from app.db import AsyncSessionFactory
    from sqlalchemy import select

    async def _rank() -> None:
        async with AsyncSessionFactory() as session:
            profile = await session.scalar(
                select(Profile).order_by(Profile.created_at.desc())
            )
            if not profile:
                print("No profile found. Run: python -m app profile import <path>")
                return
            skills: list[str] = profile.skills or []
            jobs = list((await session.scalars(select(Job))).all())
            if not jobs:
                print("No jobs found. Run: python -m app discover first.")
                return
            profile_text = " ".join(skills)
            descriptions = [j.description or j.title for j in jobs]
            all_vecs = encode_texts([profile_text] + descriptions)
            profile_vec = all_vecs[0]
            job_vecs = all_vecs[1:]
            for job, vec in zip(jobs, job_vecs):
                job.keyword_score = keyword_score(skills, job.description or job.title)
                job.embedding_score = cosine_similarity(profile_vec, vec)

            if getattr(args, "full", False):
                try:
                    from app.ranker.llm_judge import judge_job
                    from app.llm import make_llm_client
                    client = make_llm_client()
                    top_n = [j for j in jobs if j.llm_score is None]
                    for job in top_n:
                        try:
                            result = judge_job(
                                job.description or job.title,
                                skills,
                                client,
                                session,
                            )
                            job.llm_score = float(result.score)
                            job.llm_reasoning = result.reasoning
                            job.llm_matched_skills = result.matched_skills
                        except Exception as exc:
                            logging.getLogger(__name__).warning(
                                "LLM judge skipped for job %s: %s", job.id, exc
                            )
                        time.sleep(2)
                except ImportError:
                    logging.getLogger(__name__).warning(
                        "app.ranker.llm_judge not available — skipping LLM judge step"
                    )

            await session.commit()
        print(f"Ranked {len(jobs)} jobs.")

    asyncio.run(_rank())


def cmd_profile_import(args: argparse.Namespace) -> None:
    from app.services.profile import extract_skills
    from app.models.profile import Profile
    from app.db import AsyncSessionFactory

    text = pathlib.Path(args.path).read_text(encoding="utf-8")
    skills = extract_skills(text)
    print(f"Extracted {len(skills)} skills: {skills}")

    async def _persist() -> None:
        async with AsyncSessionFactory() as session:
            profile = Profile(
                full_name="User",
                email="user@example.com",
                skills=skills,
                base_resume_md=text,
            )
            session.add(profile)
            await session.commit()

    asyncio.run(_persist())
    print("Profile saved to DB.")


def cmd_generate(args: argparse.Namespace) -> None:
    from app.db import AsyncSessionFactory
    from app.models.profile import Profile
    from app.services.generation import DraftLimitExceeded, generate_draft
    from sqlalchemy import select

    async def _run() -> None:
        job_id = uuid.UUID(args.job_id)
        async with AsyncSessionFactory() as session:
            profile = await session.scalar(
                select(Profile).order_by(Profile.created_at.desc())
            )
            if not profile:
                print("No profile. Run: python -m app profile import <path>")
                return
            try:
                draft = await generate_draft(job_id, profile.id, session)
            except DraftLimitExceeded:
                print("Daily draft limit reached.")
                return
        out = pathlib.Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "resume.md").write_text(draft.resume_md or "", encoding="utf-8")
        (out / "cover_letter.md").write_text(draft.cover_letter_md or "", encoding="utf-8")
        (out / "email.md").write_text(
            f"Subject: {draft.email_subject}\n\n{draft.email_body or ''}",
            encoding="utf-8",
        )
        print(f"Drafts written to {out}/")

    asyncio.run(_run())


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app")
    sub = parser.add_subparsers(dest="command", required=True)

    disc = sub.add_parser("discover")
    disc.add_argument("--source", default="remoteok")
    disc.add_argument("--limit", type=int, default=50)
    disc.add_argument("--all", action="store_true", dest="all", default=False)
    disc.set_defaults(func=cmd_discover)

    rank_p = sub.add_parser("rank")
    rank_p.add_argument("--full", action="store_true", dest="full", default=False)
    rank_p.set_defaults(func=cmd_rank)

    prof = sub.add_parser("profile")
    prof_sub = prof.add_subparsers(dest="profile_cmd", required=True)
    imp = prof_sub.add_parser("import")
    imp.add_argument("path")
    imp.set_defaults(func=cmd_profile_import)

    gen = sub.add_parser("generate")
    gen.add_argument("--job-id", required=True)
    gen.add_argument("--out", default="./drafts")
    gen.set_defaults(func=cmd_generate)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
