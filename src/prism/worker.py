import asyncio
import uuid

from celery import Celery
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from prism.agent import run_review
from prism.config import settings
from prism.github_auth import get_installation_token
from prism.github_client import fetch_pr_diff, post_review_comment
from prism.logging import configure_logging, get_logger
from prism.repository import ReviewRepository

configure_logging()

logger = get_logger(__name__)

celery_app = Celery(
    "prism",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(task_serializer="json")


@celery_app.task
def review_pr_task(repo: str, pr_number: int, commit_sha: str, installation_id: int) -> None:
    correlation_id = str(uuid.uuid4())
    ctx = {"repo": repo, "pr_number": pr_number, "correlation_id": correlation_id}

    async def _run() -> None:
        engine = create_async_engine(settings.database_url, poolclass=NullPool)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with session_factory() as session:
                repo_db = ReviewRepository(session)

                if await repo_db.get_review(repo, pr_number) is not None:
                    logger.info("review already exists, skipping", extra=ctx)
                    return
                token = await get_installation_token(installation_id)

                raw_diff = await fetch_pr_diff(repo, pr_number, token)
                classification, filtered_comments = run_review(repo, pr_number, raw_diff)
                logger.info(
                    "review generated",
                    extra={
                        **ctx,
                        "diff_type": classification.diff_type,
                        "num_comments": len(filtered_comments),
                    },
                )

                if not filtered_comments:
                    logger.info("no comments after filtering, skipping post", extra=ctx)
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

                await post_review_comment(repo, pr_number, commit_sha, filtered_comments, token)
                logger.info(
                    "review posted",
                    extra={**ctx, "review_id": review.id, "num_comments": len(filtered_comments)},
                )
        finally:
            await engine.dispose()

    asyncio.run(_run())
