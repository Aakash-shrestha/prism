import asyncio

from celery import Celery
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from prism.agent import run_review
from prism.config import settings
from prism.github_client import fetch_pr_diff, post_review_comment
from prism.repository import ReviewRepository

celery_app = Celery(
    "prism",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(task_serializer="json")


@celery_app.task
def review_pr_task(repo: str, pr_number: int, commit_sha: str) -> None:
    async def _run() -> None:
        engine = create_async_engine(settings.database_url, poolclass=NullPool)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with session_factory() as session:
                repo_db = ReviewRepository(session)

                if await repo_db.get_review(repo, pr_number) is not None:
                    print(f"Review for {repo}#{pr_number} already exists. Skipping.")
                    return

                raw_diff = await fetch_pr_diff(repo, pr_number)
                classification, filtered_comments = run_review(repo, pr_number, raw_diff)

                if not filtered_comments:
                    return

                review = await repo_db.create_review(
                    repo, pr_number, classification.diff_type, classification.reasoning
                )

                for comment in filtered_comments:
                    await repo_db.create_comment(
                        review.id,
                        comment.filename,
                        comment.line,
                        comment.comment,
                        comment.severity,
                    )

                await post_review_comment(repo, pr_number, commit_sha, filtered_comments)
        finally:
            await engine.dispose()

    asyncio.run(_run())
