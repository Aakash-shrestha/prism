import asyncio
import random

import httpx

from prism.logging import get_logger
from prism.schemas import FileDiff, ParsedDiff, ReviewComment

logger = get_logger(__name__)

_RETRYABLE = {429, 500, 502, 503, 504}
_PERMANENT = {401, 404, 422}


async def _request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    max_retries: int = 3,
    **kwargs,
) -> httpx.Response:
    last_exc: httpx.HTTPStatusError | None = None

    for attempt in range(max_retries):
        response = await client.request(method, url, **kwargs)
        try:
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            if e.response.status_code in _PERMANENT:
                logger.error(
                    "permanent HTTP error, not retrying",
                    extra={"url": url, "status_code": e.response.status_code},
                )
                raise
            if e.response.status_code in _RETRYABLE:
                last_exc = e
                wait = (2**attempt) + random.uniform(0, 1)
                logger.warning(
                    "retryable HTTP error, backing off",
                    extra={
                        "url": url,
                        "status_code": e.response.status_code,
                        "attempt": attempt + 1,
                        "wait": round(wait, 2),
                    },
                )
                await asyncio.sleep(wait)
                continue
            raise

    raise last_exc  # type: ignore[misc]


async def fetch_pr_diff(repo: str, pr_number: int, token: str) -> str:
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3.diff",
    }
    async with httpx.AsyncClient() as client:
        response = await _request_with_retry(client, "GET", url, headers=headers)
        return response.text


def parse_diff(raw_diff: str) -> ParsedDiff:
    chunks = raw_diff.split("diff --git")
    files = chunks[1:]
    file_diffs: list[FileDiff] = []
    for file in files:
        if "new file mode" in file:
            status = "added"
        elif "deleted file mode" in file:
            status = "deleted"
        else:
            status = "modified"

        filename = ""
        patch_lines: list[str] = []
        for line in file.splitlines():
            if line.startswith("+++ b/"):
                filename = line[len("+++ b/") :]
            elif line.startswith("+") or line.startswith("-"):
                patch_lines.append(line)

        file_diffs.append(FileDiff(filename=filename, status=status, patch="\n".join(patch_lines)))

    return ParsedDiff(files=file_diffs, total_files=len(files))


async def post_review_comment(
    repo: str, pr_number: int, commit_sha: str, comments: list[ReviewComment], token: str
) -> None:
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/reviews"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    review = {
        "commit_id": commit_sha,
        "body": "prism review",
        "event": "COMMENT",
        "comments": [{"path": c.filename, "line": c.line, "body": c.comment} for c in comments],
    }
    async with httpx.AsyncClient() as client:
        await _request_with_retry(client, "POST", url, json=review, headers=headers)
