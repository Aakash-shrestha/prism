from dataclasses import dataclass

from pydantic import BaseModel
from pydantic.config import ConfigDict


@dataclass
class EvalCase:
    id: str
    description: str
    diff: str
    expected_issues: list[str]  # things a good reviewer would catch
    should_not_flag: list[str]  # false positive cases
    diff_type: str  # expected classification, not what is classified by llm


class EvalResult(BaseModel):
    id: str
    diff_type: str
    actual_diff_type: str
    comments: list[dict]
    model_config = ConfigDict(extra="forbid")


EVAL_CASES: list[EvalCase] = [
    EvalCase(
        id="off_by_one",
        description="A common bug where a loop iterates one time too many or too few.",
        diff="""diff --git a/example.py b/example.py
index e69de29..b6fc4de2 100644
--- a/example.py
+++ b/example.py
@@ -0,0 +1,5 @@
+def count_items(items):
+    count = 0
+    for i in range(len(items)):
+        count += 1
""",
        expected_issues=[
            "Missing return statement: `count` is incremented correctly but never returned. The function always returns `None` implicitly. Add `return count` at the end.",
            "Unnecessary use of `range(len(items))`: the loop variable `i` is unused — iterate directly with `for _ in items` or simply use `return len(items)`.",
        ],
        should_not_flag=[
            "The increment logic `count += 1` is correct — it is the missing return that is the bug, not how count is updated.",
        ],
        diff_type="feature",
    ),
    EvalCase(
        id="sql_injection_fstring",
        description="A new user search endpoint builds a SQL query via f-string interpolation instead of parameterized queries.",
        diff="""diff --git a/src/api/users.py b/src/api/users.py
index a3f8c21..7e42d09 100644
--- a/src/api/users.py
+++ b/src/api/users.py
@@ -1,10 +1,20 @@
 from fastapi import APIRouter
 from db import get_connection

 router = APIRouter()


 @router.get("/users/{user_id}")
 def get_user(user_id: int):
     conn = get_connection()
     return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
+
+
+@router.get("/users/search")
+def search_users(q: str):
+    conn = get_connection()
+    query = f"SELECT * FROM users WHERE username LIKE '%{q}%' OR email LIKE '%{q}%'"
+    return conn.execute(query).fetchall()
""",
        expected_issues=[
            "SQL injection: `query` is built by embedding the user-supplied `q` directly into the SQL string via an f-string. An attacker can inject arbitrary SQL — e.g., `q=\"' UNION SELECT password_hash,null FROM users--\"` exfiltrates the password column. Use parameterized queries: `conn.execute('SELECT * FROM users WHERE username LIKE ? OR email LIKE ?', (f'%{q}%', f'%{q}%'))`.",
        ],
        should_not_flag=[
            "The existing `get_user` function correctly uses a parameterized query — it is not a problem.",
            "The LIKE pattern logic is valid; only the injection vector is the issue.",
        ],
        diff_type="feature",
    ),
    EvalCase(
        id="race_condition_lazy_cache",
        description="A new lazy-init module-level cache added to a multi-threaded service — the check-then-act pattern is not atomic, allowing concurrent threads to race.",
        diff="""diff --git a/src/config_cache.py b/src/config_cache.py
new file mode 100644
index 0000000..9f3a817
--- /dev/null
+++ b/src/config_cache.py
@@ -0,0 +1,22 @@
+import threading
+from typing import Any
+from db import get_connection
+
+_cache: dict[str, Any] = {}
+
+
+def get_config(key: str) -> Any:
+    \"\"\"Fetch a config value from the DB, caching after first load.\"\"\"
+    if key in _cache:
+        return _cache[key]
+
+    conn = get_connection()
+    row = conn.execute("SELECT value FROM config WHERE key = ?", (key,)).fetchone()
+    value = row["value"] if row else None
+    _cache[key] = value
+    return value
+
+
+def invalidate_cache() -> None:
+    \"\"\"Call after a config update to force a fresh DB read on next access.\"\"\"
+    _cache.clear()
""",
        expected_issues=[
            "Race condition (TOCTOU): `if key in _cache` and `_cache[key] = value` are not atomic. Two threads can simultaneously find the key absent, both query the DB, and both write — causing duplicate DB calls or a torn write if `invalidate_cache` runs concurrently. Protect the check-and-set with a `threading.Lock`.",
            "`_cache.clear()` in `invalidate_cache` is not thread-safe: a thread iterating `_cache` at the same time will raise `RuntimeError: dictionary changed size during iteration` in CPython.",
        ],
        should_not_flag=[
            "The `threading` import is not yet used in the diff, but this is not dead code — it signals intent and will be required once a lock is added.",
            "Returning `None` for a missing key is a deliberate sentinel and should not be flagged as missing error handling.",
        ],
        diff_type="feature",
    ),
    EvalCase(
        id="mutable_default_argument",
        description="A config validation helper uses a mutable list as a default argument, causing errors to accumulate across separate calls.",
        diff="""diff --git a/src/validation.py b/src/validation.py
new file mode 100644
index 0000000..c2f1a3b
--- /dev/null
+++ b/src/validation.py
@@ -0,0 +1,20 @@
+from typing import Any
+
+
+def validate_config(config: dict[str, Any], errors: list[str] = []) -> list[str]:
+    \"\"\"Validate an app config dict. Returns a list of error messages.\"\"\"
+    if "database_url" not in config:
+        errors.append("Missing required field: database_url")
+    if "secret_key" not in config:
+        errors.append("Missing required field: secret_key")
+    if "debug" in config and not isinstance(config["debug"], bool):
+        errors.append("Field 'debug' must be a boolean")
+    return errors
+
+
+def validate_all(configs: list[dict[str, Any]]) -> dict[int, list[str]]:
+    results = {}
+    for i, cfg in enumerate(configs):
+        results[i] = validate_config(cfg)
+    return results
""",
        expected_issues=[
            "Mutable default argument: `errors: list[str] = []` is evaluated once at function definition time, not on each call. Every invocation without an explicit `errors` argument shares the same list object. After the first call that appends errors, all subsequent calls inherit those old errors. Fix: use `errors: list[str] | None = None` and initialize with `if errors is None: errors = []` inside the body.",
            "`validate_all` calls `validate_config(cfg)` without passing `errors`, so all iterations share and mutate the same list — `results[1]` will contain errors from `results[0]` and so on, making the output completely wrong from the second config onward.",
        ],
        should_not_flag=[
            "The individual field validation checks are logically correct.",
            "The `validate_all` loop structure is fine — the root cause is the signature of `validate_config`, not the caller.",
        ],
        diff_type="feature",
    ),
    EvalCase(
        id="missing_auth_admin_endpoint",
        description="A new admin data-export endpoint is added without the authentication dependency that every other route in the file requires.",
        diff="""diff --git a/src/api/admin.py b/src/api/admin.py
index f8b2c44..3e9a1d7 100644
--- a/src/api/admin.py
+++ b/src/api/admin.py
@@ -1,19 +1,30 @@
 from fastapi import APIRouter, Depends
 from auth import require_admin
 from db import get_connection
+import csv
+import io

 router = APIRouter(prefix="/admin")


 @router.get("/users")
 def list_users(current_user=Depends(require_admin)):
     conn = get_connection()
     return conn.execute("SELECT id, email, role, created_at FROM users").fetchall()


 @router.delete("/users/{user_id}")
 def delete_user(user_id: int, current_user=Depends(require_admin)):
     conn = get_connection()
     conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
     return {"deleted": user_id}
+
+
+@router.get("/export")
+def export_users() -> str:
+    conn = get_connection()
+    rows = conn.execute("SELECT id, email, role, password_hash FROM users").fetchall()
+    output = io.StringIO()
+    writer = csv.writer(output)
+    writer.writerows(rows)
+    return output.getvalue()
""",
        expected_issues=[
            "Missing authentication: `export_users` has no `Depends(require_admin)` unlike every other route in this file. Any unauthenticated request to `GET /admin/export` will receive a full CSV dump of all user data. Add `current_user=Depends(require_admin)` to the function signature.",
            "Sensitive data in export: the query selects `password_hash` and writes it into the CSV response. Even for admin endpoints, exporting password hashes in a bulk download is a significant security risk and likely violates compliance requirements. Remove `password_hash` from the SELECT.",
        ],
        should_not_flag=[
            "The existing `list_users` and `delete_user` routes correctly use `Depends(require_admin)` — they are not issues.",
            "Using `csv.writer` with `io.StringIO` is a valid approach for CSV generation.",
        ],
        diff_type="feature",
    ),
    EvalCase(
        id="silent_none_return_on_exception",
        description="A payment processing function is refactored to add error handling, but none of the except branches return a value, so the function silently returns None on any failure.",
        diff="""diff --git a/src/payments.py b/src/payments.py
index 2d4f8b1..8c73ee9 100644
--- a/src/payments.py
+++ b/src/payments.py
@@ -1,10 +1,22 @@
 import logging
 import stripe
 from models import PaymentResult, PaymentStatus

 logger = logging.getLogger(__name__)


-def process_payment(amount_cents: int, token: str) -> PaymentResult:
-    charge = stripe.Charge.create(amount=amount_cents, currency="usd", source=token)
-    return PaymentResult(status=PaymentStatus.SUCCESS, charge_id=charge.id)
+def process_payment(amount_cents: int, token: str) -> PaymentResult:
+    try:
+        charge = stripe.Charge.create(amount=amount_cents, currency="usd", source=token)
+        return PaymentResult(status=PaymentStatus.SUCCESS, charge_id=charge.id)
+    except stripe.error.CardError as e:
+        logger.error(f"Card declined for token {token}")
+    except stripe.error.StripeError as e:
+        logger.error(f"Stripe API error for token {token}")
+    except Exception as e:
+        logger.error(f"Unexpected error processing payment for token {token}")
""",
        expected_issues=[
            "Silent None return: all three `except` branches log the error but have no `return` statement. Python implicitly returns `None`, which violates the `-> PaymentResult` annotation. Any caller that accesses `.status` or `.charge_id` on the result will raise `AttributeError: 'NoneType' object has no attribute 'status'`. Each branch must either return a failure `PaymentResult` (e.g., `PaymentResult(status=PaymentStatus.FAILED, error=str(e))`) or re-raise the exception.",
            "Exception context is discarded: all three log calls omit the exception details. For example, `stripe.error.CardError` carries a decline code and user-facing message that is completely lost. Add `exc_info=True` to each `logger.error` call, or include `e` in the message, to preserve the traceback in log aggregators.",
            "Sensitive token logged on every error path: `token` (a payment source token) appears in all three error messages. Logging it creates a sensitive data exposure in log files and aggregators. Remove the token from error messages or replace it with a truncated identifier.",
        ],
        should_not_flag=[
            "Catching `stripe.error.CardError` separately before `stripe.error.StripeError` is correct — it is a subclass, and catching the more specific case first is proper exception hierarchy usage.",
            "The layered except structure (CardError → StripeError → Exception) is valid Python and appropriate for this use case.",
        ],
        diff_type="refactor",
    ),
    EvalCase(
        id="style_only",
        description="A pure style cleanup: cryptic single-letter parameter names are renamed to be descriptive, type hints are added, and the multi-line call is reformatted. No logic changes.",
        diff="""diff --git a/src/github_client.py b/src/github_client.py
index 3c81a44..d02f19c 100644
--- a/src/github_client.py
+++ b/src/github_client.py
@@ -1,14 +1,18 @@
 import requests


-def get_pr_diff(r, n, tok):
-    h = {"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github.v3.diff"}
-    resp = requests.get(f"https://api.github.com/repos/{r}/pulls/{n}", headers=h)
-    resp.raise_for_status()
-    return resp.text
+def get_pr_diff(repo: str, pr_number: int, token: str) -> str:
+    \"\"\"Fetch the raw unified diff for a pull request from the GitHub API.\"\"\"
+    headers = {
+        "Authorization": f"Bearer {token}",
+        "Accept": "application/vnd.github.v3.diff",
+    }
+    response = requests.get(
+        f"https://api.github.com/repos/{repo}/pulls/{pr_number}",
+        headers=headers,
+    )
+    response.raise_for_status()
+    return response.text
""",
        expected_issues=[],
        should_not_flag=[
            "The use of `requests` (synchronous) rather than `httpx.AsyncClient` is pre-existing behavior — this diff does not change it and a reviewer should not flag it.",
            "The docstring is accurate and does not introduce any issues.",
            "Renaming `r`, `n`, `tok` to `repo`, `pr_number`, `token` is a straightforward improvement with no behavioral change.",
            "Reformatting the dict literal and the `requests.get` call to multi-line is a style choice, not a bug.",
        ],
        diff_type="style",
    ),
    EvalCase(
        id="clean_addition",
        description="A well-written async utility that paginates through GitHub API results. It has a timeout, handles rate-limit responses explicitly, raises on non-transient errors, and returns a typed list.",
        diff="""diff --git a/src/github_client.py b/src/github_client.py
index d02f19c..a8f3e51 100644
--- a/src/github_client.py
+++ b/src/github_client.py
@@ -1,5 +1,37 @@
+import re
 import requests
+import httpx
+from typing import Any

+GITHUB_API = "https://api.github.com"
+_LINK_RE = re.compile(r'<([^>]+)>;\\s*rel="next"')
+
+
+async def paginate(
+    path: str,
+    token: str,
+    *,
+    per_page: int = 100,
+) -> list[dict[str, Any]]:
+    \"\"\"Collect all pages of a GitHub list endpoint into a single list.
+
+    Raises httpx.HTTPStatusError on non-2xx responses that are not rate-limit
+    retries. Raises httpx.TimeoutException if a single page request times out.
+    \"\"\"
+    url: str | None = f"{GITHUB_API}/{path.lstrip('/')}?per_page={per_page}"
+    headers = {
+        "Authorization": f"Bearer {token}",
+        "Accept": "application/vnd.github+json",
+    }
+    results: list[dict[str, Any]] = []
+
+    async with httpx.AsyncClient(timeout=15.0) as client:
+        while url is not None:
+            response = await client.get(url, headers=headers)
+            if response.status_code == 429 or (
+                response.status_code == 403
+                and "rate limit" in response.text.lower()
+            ):
+                raise httpx.HTTPStatusError(
+                    "GitHub rate limit exceeded", request=response.request, response=response
+                )
+            response.raise_for_status()
+            results.extend(response.json())
+            match = _LINK_RE.search(response.headers.get("Link", ""))
+            url = match.group(1) if match else None
+
+    return results

 def get_pr_diff(repo: str, pr_number: int, token: str) -> str:
""",
        expected_issues=[],
        should_not_flag=[
            "The module-level `_LINK_RE` compiled regex is intentional and correct — compiling once at import time is more efficient than recompiling per call.",
            "`path.lstrip('/')` is a deliberate defensive measure to allow callers to pass paths with or without a leading slash.",
            "Raising `httpx.HTTPStatusError` directly for rate-limit responses is a valid choice — it gives callers a uniform error type to handle rather than a custom exception.",
            "The `timeout=15.0` on `AsyncClient` is an explicit and appropriate choice for a paginated network call.",
            "Using `str | None` for `url` with a `while url is not None` loop is a clean, idiomatic pagination pattern.",
        ],
        diff_type="feature",
    ),
]
