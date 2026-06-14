import httpx

from prism.config import settings
from prism.schemas import FileDiff, ParsedDiff


async def fetch_pr_diff(repo: str, pr_number: int) -> str:
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
    headers = {
        "Authorization": f"Bearer {settings.github_token}",
        "Accept": "application/vnd.github.v3.diff",
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)  # sends the http request
        response.raise_for_status()  # httpx does not directly raise for non-2xx status codes, so we need to call this method to raise an exception if the request failed
        return response.text  # raw text instead of json, due to accept header


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
