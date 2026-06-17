import time
from pathlib import Path

import httpx
import jwt

from prism.config import settings


def generate_jwt() -> str:
    private_key = Path(settings.github_app_private_key_path).read_text()
    now = int(time.time())
    payload = {"iat": now - 60, "exp": now + (9 * 60), "iss": settings.github_app_id}
    return jwt.encode(payload, private_key, algorithm="RS256")


async def get_installation_token(installation_id: int) -> str:
    token = generate_jwt()
    url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        response.raise_for_status()
        return response.json()["token"]
