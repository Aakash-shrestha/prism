import asyncio

from celery import Celery

from prism.agent import run_review
from prism.config import settings
from prism.github_client import fetch_pr_diff
from prism.schemas import ReviewComment

celery_app = Celery(
    "prism",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(task_serializer="json")


@celery_app.task
def review_pr_task(repo: str, pr_number: int) -> None:
    raw_diff = asyncio.run(fetch_pr_diff(repo, pr_number))
    filtered_comments: list[ReviewComment] = run_review(repo, pr_number, raw_diff)

    for comment in filtered_comments:
        print(
            f"Posting comment on {comment.filename} line {comment.line}: [{comment.severity.upper()}] {comment.comment}"
        )
