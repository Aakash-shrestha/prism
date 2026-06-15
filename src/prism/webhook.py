import hashlib
import hmac
import json
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from prism.agent import run_review
from prism.config import settings
from prism.github_client import fetch_pr_diff
from prism.schemas import ReviewComment

router = APIRouter(prefix="/webhook", tags=["webhook"])


def verify_signature(payload: bytes, signature_header: str) -> bool:
    if not signature_header:
        return False

    secret = settings.github_webhook_secret.encode()
    signature = "sha256=" + hmac.new(secret, payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, signature_header)


class Repository(BaseModel):
    model_config = ConfigDict(extra="ignore")
    full_name: str


class PRWebhookPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    repository: Repository
    action: str
    number: int
    pull_request: dict[str, Any]


async def process_pr(repo: str, pr_number: int) -> None:
    raw_diff = await fetch_pr_diff(repo, pr_number)
    filtered_comment: list[ReviewComment] = run_review(repo, pr_number, raw_diff)

    for comment in filtered_comment:
        print(
            f"Posting comment on {comment.filename} line {comment.line}: [{comment.severity.upper()}] {comment.comment}"
        )


@router.post("/github")
async def github_webhook(request: Request, background_task: BackgroundTasks):
    # read raw bytes before it gets parsed into PRWebhookPayload
    raw_bytes = await request.body()

    signature = request.headers.get("X-Hub-Signature-256", "")

    if not verify_signature(raw_bytes, signature):
        raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        payload_dict = json.loads(raw_bytes)
        payload = PRWebhookPayload(**payload_dict)

        repo = payload.repository.full_name
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid payload: {e}") from e
    if payload.action in ["opened", "synchronize"]:
        background_task.add_task(process_pr, repo, payload.number)
        return JSONResponse(
            status_code=202,
            content={"status": "accepted", "pr": payload.number},
        )
    return JSONResponse(status_code=200, content={"status": "ok"})
