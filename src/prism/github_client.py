import httpx

from prism.config import settings
from prism.schemas import FileDiff, ParsedDiff, ReviewComment


async def fetch_pr_diff(repo: str, pr_number: int) -> str:
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
    headers = {
        "Authorization": f"Bearer {settings.github_token}",
        "Accept": "application/vnd.github.v3.diff",
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.text
        except httpx.HTTPStatusError as e:
            print(
                f"GitHub API error {e.response.status_code} fetching diff for {repo}#{pr_number}: {e}"
            )
            raise


def parse_diff(raw_diff: str) -> ParsedDiff:
    chunks = raw_diff.split("diff --git")
    files = chunks[1:]
    file_diffs: list[FileDiff] = []
    # check if the chunk contains status
    for file in files:
        if "new file mode" in file:
            status = "added"
        elif "deleted file mode" in file:
            status = "deleted"
        else:
            status = "modified"

        filename = ""
        patch_lines: list[str] = []
        # extract the file name of each chunk
        for line in file.splitlines():
            if line.startswith("+++ b/"):
                filename = line[len("+++ b/") :]  # everything after +++ b/
            elif line.startswith("+") or line.startswith("-"):
                patch_lines.append(line)

        patch = "\n".join(patch_lines)

        file_diffs.append(FileDiff(filename=filename, status=status, patch=patch))

    return ParsedDiff(files=file_diffs, total_files=len(files))


async def post_review_comment(
    repo: str,
    pr_number: int,
    commit_sha: str,
    comments: list[ReviewComment],
) -> None:
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/reviews"

    review = {
        "commit_id": commit_sha,
        "body": "prism review",
        "event": "COMMENT",
        "comments": [{"path": c.filename, "line": c.line, "body": c.comment} for c in comments],
    }

    headers = {
        "Authorization": f"Bearer {settings.github_token}",
        "Accept": "application/vnd.github+json",
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=review, headers=headers)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            print(
                f"GitHub API error {e.response.status_code} posting review comment for {repo}#{pr_number}: {e}"
            )
            raise
