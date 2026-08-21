"""CircleCI REST API v2 HTTP client -- Personal API Token auth against the
user's own CircleCI account. Thin async wrappers around Pipeline/Workflow/
Job/Insights/Context/Project/Schedule/Webhook/Checkout-Key/Trigger
endpoints, plus the separate self-hosted Runner API (runner.circleci.com).
Built on the SDK's `ctx.http.*` async client, same pattern as n8n
Connector's n8n_client.py / MuleSoft Connector's mulesoft_client.py.

WHY `Circle-Token` HEADER -- see app.py module docstring for the full
architectural reasoning. Every request carries `Circle-Token: <token>`.

WHY 401 vs 404 ARE HANDLED DIFFERENTLY, SAME PRINCIPLE AS n8n/MuleSoft/
GitLab CI/CD CONNECTOR's clients.

A 401 means the Personal API Token itself is not accepted (missing,
revoked, or wrong). A 404 on a project/pipeline/workflow/job lookup
usually means either the id/slug is wrong OR the token's owner lacks
access to that particular project -- CircleCI does not distinguish "does
not exist" from "you can't see it" at the API level, so both are
surfaced as a single not-found ClientFail with that caveat in the message.
"""
from __future__ import annotations

from typing import Any

BASE_URL = "https://circleci.com/api/v2"
RUNNER_BASE_URL = "https://runner.circleci.com/api/v3"


class ClientFail(Exception):
    """Raised for any non-2xx CircleCI response, carrying a human message."""

    def __init__(self, message: str, status: int = 0):
        super().__init__(message)
        self.message = message
        self.status = status


def _headers(token: str) -> dict:
    return {"Circle-Token": token, "Accept": "application/json"}


def _check(resp) -> Any:
    status = getattr(resp, "status_code", None) or getattr(resp, "status", 0)
    if status == 401:
        raise ClientFail(
            "CircleCI rejected this Personal API Token -- it may be wrong, expired, or revoked.",
            status,
        )
    if status == 403:
        raise ClientFail(
            "CircleCI accepted the token but denied this operation -- the token's owner likely lacks access to this project/organization.",
            status,
        )
    if status == 404:
        raise ClientFail(
            "Not found -- either the id/slug is wrong, or this token's owner doesn't have access to it.",
            status,
        )
    if status == 429:
        raise ClientFail("Rate limited by CircleCI (5000 requests/hour per token) -- try again shortly.", status)
    if status >= 400:
        try:
            body = resp.json()
            msg = body.get("message") or str(body)
        except Exception:
            msg = getattr(resp, "text", "") or f"HTTP {status}"
        raise ClientFail(f"CircleCI API error ({status}): {msg}", status)
    if status == 204:
        return None
    try:
        return resp.json()
    except Exception:
        return None


async def _get(ctx, token: str, path: str, *, params: dict | None = None, base: str = BASE_URL) -> Any:
    clean = {k: v for k, v in (params or {}).items() if v not in (None, "")}
    resp = await ctx.http.get(f"{base}{path}", headers=_headers(token), params=clean)
    return _check(resp)


async def _post(ctx, token: str, path: str, *, json: dict | None = None, base: str = BASE_URL) -> Any:
    resp = await ctx.http.post(f"{base}{path}", headers=_headers(token), json=json or {})
    return _check(resp)


async def _put(ctx, token: str, path: str, *, json: dict | None = None, base: str = BASE_URL) -> Any:
    resp = await ctx.http.put(f"{base}{path}", headers=_headers(token), json=json or {})
    return _check(resp)


async def _patch(ctx, token: str, path: str, *, json: dict | None = None, base: str = BASE_URL) -> Any:
    resp = await ctx.http.patch(f"{base}{path}", headers=_headers(token), json=json or {})
    return _check(resp)


async def _delete(ctx, token: str, path: str, *, base: str = BASE_URL) -> Any:
    resp = await ctx.http.delete(f"{base}{path}", headers=_headers(token))
    return _check(resp)


# ──────────────────────────────────────────────────────────────────────────
# User
# ──────────────────────────────────────────────────────────────────────────


async def get_current_user(ctx, token: str) -> dict:
    return await _get(ctx, token, "/me")


async def get_collaborations(ctx, token: str) -> Any:
    return await _get(ctx, token, "/me/collaborations")


async def check_connection(ctx, token: str) -> dict:
    """Verify a Personal API Token actually works by calling GET /me.
    Returns {"ok": True} or {"ok": False, "error": ..., "error_code": ...}.
    """
    try:
        user = await get_current_user(ctx, token)
    except ClientFail as e:
        if e.status == 401:
            return {
                "ok": False,
                "error": "CircleCI rejected this Personal API Token. Double-check it was copied correctly and hasn't been revoked.",
                "error_code": "CIRCLECI_TOKEN_INVALID",
            }
        return {"ok": False, "error": e.message, "error_code": "CIRCLECI_CONNECT_FAILED"}
    if not isinstance(user, dict) or not user.get("id"):
        return {
            "ok": False,
            "error": "CircleCI accepted the request but returned an unexpected response.",
            "error_code": "CIRCLECI_CONNECT_FAILED",
        }
    return {"ok": True}


# ──────────────────────────────────────────────────────────────────────────
# Project
# ──────────────────────────────────────────────────────────────────────────


async def get_project(ctx, token: str, project_slug: str) -> dict:
    return await _get(ctx, token, f"/project/{project_slug}")


async def create_checkout_key(ctx, token: str, project_slug: str, key_type: str) -> dict:
    return await _post(ctx, token, f"/project/{project_slug}/checkout-key", json={"type": key_type})


async def list_checkout_keys(ctx, token: str, project_slug: str) -> Any:
    return await _get(ctx, token, f"/project/{project_slug}/checkout-key")


async def get_checkout_key(ctx, token: str, project_slug: str, fingerprint: str) -> dict:
    return await _get(ctx, token, f"/project/{project_slug}/checkout-key/{fingerprint}")


async def delete_checkout_key(ctx, token: str, project_slug: str, fingerprint: str) -> Any:
    return await _delete(ctx, token, f"/project/{project_slug}/checkout-key/{fingerprint}")


async def list_env_vars(ctx, token: str, project_slug: str) -> Any:
    return await _get(ctx, token, f"/project/{project_slug}/envvar")


async def create_env_var(ctx, token: str, project_slug: str, name: str, value: str) -> dict:
    return await _post(ctx, token, f"/project/{project_slug}/envvar", json={"name": name, "value": value})


async def get_env_var(ctx, token: str, project_slug: str, name: str) -> dict:
    return await _get(ctx, token, f"/project/{project_slug}/envvar/{name}")


async def delete_env_var(ctx, token: str, project_slug: str, name: str) -> Any:
    return await _delete(ctx, token, f"/project/{project_slug}/envvar/{name}")


# ──────────────────────────────────────────────────────────────────────────
# Pipeline
# ──────────────────────────────────────────────────────────────────────────


async def list_project_pipelines(ctx, token: str, project_slug: str, branch: str = "", page_token: str = "") -> dict:
    return await _get(ctx, token, f"/project/{project_slug}/pipeline", params={"branch": branch, "page-token": page_token})


async def list_my_pipelines(ctx, token: str, project_slug: str, page_token: str = "") -> dict:
    return await _get(ctx, token, f"/project/{project_slug}/pipeline/mine", params={"page-token": page_token})


async def trigger_pipeline(
    ctx, token: str, project_slug: str, branch: str = "", tag: str = "",
    parameters: dict | None = None,
) -> dict:
    body: dict = {}
    if branch:
        body["branch"] = branch
    if tag:
        body["tag"] = tag
    if parameters:
        body["parameters"] = parameters
    return await _post(ctx, token, f"/project/{project_slug}/pipeline", json=body)


async def get_pipeline(ctx, token: str, pipeline_id: str) -> dict:
    return await _get(ctx, token, f"/pipeline/{pipeline_id}")


async def get_pipeline_by_number(ctx, token: str, project_slug: str, pipeline_number: int) -> dict:
    return await _get(ctx, token, f"/project/{project_slug}/pipeline/{pipeline_number}")


async def get_pipeline_config(ctx, token: str, pipeline_id: str) -> dict:
    return await _get(ctx, token, f"/pipeline/{pipeline_id}/config")


async def get_pipeline_values(ctx, token: str, pipeline_id: str) -> dict:
    return await _get(ctx, token, f"/pipeline/{pipeline_id}/values")


async def list_pipeline_workflows(ctx, token: str, pipeline_id: str, page_token: str = "") -> dict:
    return await _get(ctx, token, f"/pipeline/{pipeline_id}/workflow", params={"page-token": page_token})


async def continue_pipeline(ctx, token: str, continuation_key: str, configuration: str, parameters: dict | None = None) -> Any:
    body = {"continuation-key": continuation_key, "configuration": configuration, "parameters": parameters or {}}
    return await _post(ctx, token, "/pipeline/continue", json=body)


# ──────────────────────────────────────────────────────────────────────────
# Workflow
# ──────────────────────────────────────────────────────────────────────────


async def get_workflow(ctx, token: str, workflow_id: str) -> dict:
    return await _get(ctx, token, f"/workflow/{workflow_id}")


async def list_workflow_jobs(ctx, token: str, workflow_id: str, page_token: str = "") -> dict:
    return await _get(ctx, token, f"/workflow/{workflow_id}/job", params={"page-token": page_token})


async def approve_workflow_job(ctx, token: str, workflow_id: str, approval_request_id: str) -> Any:
    return await _post(ctx, token, f"/workflow/{workflow_id}/approve/{approval_request_id}")


async def cancel_workflow(ctx, token: str, workflow_id: str) -> Any:
    return await _post(ctx, token, f"/workflow/{workflow_id}/cancel")


async def rerun_workflow(ctx, token: str, workflow_id: str, from_failed: bool = False, jobs: list[str] | None = None, sparse_tree: bool = False) -> dict:
    body: dict = {"from_failed": from_failed, "sparse_tree": sparse_tree}
    if jobs:
        body["jobs"] = jobs
    return await _post(ctx, token, f"/workflow/{workflow_id}/rerun", json=body)


# ──────────────────────────────────────────────────────────────────────────
# Job
# ──────────────────────────────────────────────────────────────────────────


async def get_job_by_number(ctx, token: str, project_slug: str, job_number: int) -> dict:
    return await _get(ctx, token, f"/project/{project_slug}/job/{job_number}")


async def cancel_job_by_number(ctx, token: str, project_slug: str, job_number: int) -> Any:
    return await _post(ctx, token, f"/project/{project_slug}/job/{job_number}/cancel")


async def get_job_artifacts(ctx, token: str, project_slug: str, job_number: int) -> dict:
    return await _get(ctx, token, f"/project/{project_slug}/{job_number}/artifacts")


async def get_job_by_id(ctx, token: str, job_id: str) -> dict:
    return await _get(ctx, token, f"/job/{job_id}")


async def cancel_job_by_id(ctx, token: str, job_id: str) -> Any:
    return await _post(ctx, token, f"/job/{job_id}/cancel")


async def get_job_tests(ctx, token: str, project_slug: str, job_number: int, page_token: str = "") -> dict:
    return await _get(ctx, token, f"/project/{project_slug}/{job_number}/tests", params={"page-token": page_token})


# ──────────────────────────────────────────────────────────────────────────
# Insights
# ──────────────────────────────────────────────────────────────────────────


async def get_workflow_insights(ctx, token: str, project_slug: str, workflow_name: str, branch: str = "", reporting_window: str = "last-90-days", page_token: str = "") -> dict:
    return await _get(
        ctx, token, f"/insights/{project_slug}/workflows/{workflow_name}",
        params={"branch": branch, "reporting-window": reporting_window, "page-token": page_token},
    )


async def get_workflow_run_insights(ctx, token: str, project_slug: str, workflow_name: str, branch: str = "", page_token: str = "") -> dict:
    return await _get(
        ctx, token, f"/insights/{project_slug}/workflows/{workflow_name}/jobs",
        params={"branch": branch, "page-token": page_token},
    )


async def get_job_timeseries_insights(ctx, token: str, project_slug: str, workflow_name: str, job_name: str, branch: str = "", page_token: str = "") -> dict:
    return await _get(
        ctx, token, f"/insights/{project_slug}/workflows/{workflow_name}/jobs/{job_name}",
        params={"branch": branch, "page-token": page_token},
    )


async def get_flaky_tests(ctx, token: str, project_slug: str) -> dict:
    return await _get(ctx, token, f"/insights/{project_slug}/flaky-tests")


async def get_project_insights_summary(ctx, token: str, project_slug: str, reporting_window: str = "last-90-days", branches: str = "", all_branches: bool = False, page_token: str = "") -> dict:
    return await _get(
        ctx, token, f"/insights/{project_slug}/summary",
        params={"reporting-window": reporting_window, "branches": branches, "all-branches": str(all_branches).lower(), "page-token": page_token},
    )


async def get_org_summary_insights(ctx, token: str, org_slug: str, reporting_window: str = "last-90-days", page_token: str = "") -> dict:
    return await _get(ctx, token, f"/insights/{org_slug}/summary", params={"reporting-window": reporting_window, "page-token": page_token})


# ──────────────────────────────────────────────────────────────────────────
# Pipeline Definitions + Triggers
# ──────────────────────────────────────────────────────────────────────────


async def list_pipeline_definitions(ctx, token: str, project_slug: str, page_token: str = "") -> dict:
    return await _get(ctx, token, f"/project/{project_slug}/pipeline-definition", params={"page-token": page_token})


async def list_triggers(ctx, token: str, project_id: str, page_token: str = "") -> dict:
    return await _get(ctx, token, f"/project/{project_id}/trigger", params={"page-token": page_token})


async def delete_trigger(ctx, token: str, project_id: str, trigger_id: str) -> Any:
    return await _delete(ctx, token, f"/project/{project_id}/trigger/{trigger_id}")


# ──────────────────────────────────────────────────────────────────────────
# Context (secrets)
# ──────────────────────────────────────────────────────────────────────────


async def list_contexts(ctx, token: str, owner_id: str = "", owner_slug: str = "", owner_type: str = "organization", page_token: str = "") -> dict:
    return await _get(
        ctx, token, "/context",
        params={"owner-id": owner_id, "owner-slug": owner_slug, "owner-type": owner_type, "page-token": page_token},
    )


async def create_context(ctx, token: str, name: str, owner_id: str = "", owner_slug: str = "", owner_type: str = "organization") -> dict:
    body: dict = {"name": name, "owner": {"type": owner_type}}
    if owner_id:
        body["owner"]["id"] = owner_id
    if owner_slug:
        body["owner"]["slug"] = owner_slug
    return await _post(ctx, token, "/context", json=body)


async def get_context(ctx, token: str, context_id: str) -> dict:
    return await _get(ctx, token, f"/context/{context_id}")


async def delete_context(ctx, token: str, context_id: str) -> Any:
    return await _delete(ctx, token, f"/context/{context_id}")


async def list_context_env_vars(ctx, token: str, context_id: str, page_token: str = "") -> dict:
    return await _get(ctx, token, f"/context/{context_id}/environment-variable", params={"page-token": page_token})


async def set_context_env_var(ctx, token: str, context_id: str, env_var_name: str, value: str) -> dict:
    return await _put(ctx, token, f"/context/{context_id}/environment-variable/{env_var_name}", json={"value": value})


async def delete_context_env_var(ctx, token: str, context_id: str, env_var_name: str) -> Any:
    return await _delete(ctx, token, f"/context/{context_id}/environment-variable/{env_var_name}")


async def list_context_restrictions(ctx, token: str, context_id: str) -> Any:
    return await _get(ctx, token, f"/context/{context_id}/restrictions")


async def create_context_restriction(ctx, token: str, context_id: str, restriction_type: str, restriction_value: str) -> dict:
    return await _post(
        ctx, token, f"/context/{context_id}/restrictions",
        json={"restriction_type": restriction_type, "restriction_value": restriction_value},
    )


async def delete_context_restriction(ctx, token: str, context_id: str, restriction_id: str) -> Any:
    return await _delete(ctx, token, f"/context/{context_id}/restrictions/{restriction_id}")


# ──────────────────────────────────────────────────────────────────────────
# Schedule
# ──────────────────────────────────────────────────────────────────────────


async def list_project_schedules(ctx, token: str, project_slug: str, page_token: str = "") -> dict:
    return await _get(ctx, token, f"/project/{project_slug}/schedule", params={"page-token": page_token})


async def create_schedule(ctx, token: str, project_slug: str, name: str, description: str, timetable: dict, attribution_actor: str, parameters: dict) -> dict:
    body = {
        "name": name, "description": description, "attribution-actor": attribution_actor,
        "parameters": parameters, "timetable": timetable,
    }
    return await _post(ctx, token, f"/project/{project_slug}/schedule", json=body)


async def get_schedule(ctx, token: str, schedule_id: str) -> dict:
    return await _get(ctx, token, f"/schedule/{schedule_id}")


async def update_schedule(ctx, token: str, schedule_id: str, **fields) -> dict:
    body = {k.replace("_", "-"): v for k, v in fields.items() if v is not None}
    return await _patch(ctx, token, f"/schedule/{schedule_id}", json=body)


async def delete_schedule(ctx, token: str, schedule_id: str) -> Any:
    return await _delete(ctx, token, f"/schedule/{schedule_id}")


# ──────────────────────────────────────────────────────────────────────────
# Webhook
# ──────────────────────────────────────────────────────────────────────────


async def list_webhooks(ctx, token: str, scope_id: str, scope_type: str = "project") -> dict:
    return await _get(ctx, token, "/webhook", params={"scope-id": scope_id, "scope-type": scope_type})


async def create_webhook(ctx, token: str, name: str, events: list[str], url: str, verify_tls: bool, signing_secret: str, scope_id: str, scope_type: str = "project") -> dict:
    body = {
        "name": name, "events": events, "url": url, "verify-tls": verify_tls,
        "signing-secret": signing_secret, "scope": {"id": scope_id, "type": scope_type},
    }
    return await _post(ctx, token, "/webhook", json=body)


async def get_webhook(ctx, token: str, webhook_id: str) -> dict:
    return await _get(ctx, token, f"/webhook/{webhook_id}")


async def update_webhook(ctx, token: str, webhook_id: str, **fields) -> dict:
    body = {k.replace("_", "-"): v for k, v in fields.items() if v is not None}
    return await _put(ctx, token, f"/webhook/{webhook_id}", json=body)


async def delete_webhook(ctx, token: str, webhook_id: str) -> Any:
    return await _delete(ctx, token, f"/webhook/{webhook_id}")


# ──────────────────────────────────────────────────────────────────────────
# Self-hosted Runner API (separate host: runner.circleci.com)
# ──────────────────────────────────────────────────────────────────────────


async def list_runners(ctx, token: str, resource_class: str = "", namespace: str = "") -> Any:
    return await _get(ctx, token, "/runner", params={"resource-class": resource_class, "namespace": namespace}, base=RUNNER_BASE_URL)


async def list_runner_tokens(ctx, token: str, resource_class: str) -> Any:
    return await _get(ctx, token, "/runner/token", params={"resource-class": resource_class}, base=RUNNER_BASE_URL)


async def create_runner_token(ctx, token: str, resource_class: str, nickname: str = "") -> dict:
    return await _post(ctx, token, "/runner/token", json={"resource-class": resource_class, "nickname": nickname}, base=RUNNER_BASE_URL)


async def delete_runner_by_token_id(ctx, token: str, token_id: str) -> Any:
    return await _delete(ctx, token, f"/runner/token/{token_id}", base=RUNNER_BASE_URL)


async def delete_runner_by_resource_id(ctx, token: str, resource_id: str) -> Any:
    return await _delete(ctx, token, f"/runner/{resource_id}", base=RUNNER_BASE_URL)


async def list_runner_resource_classes(ctx, token: str, namespace: str) -> Any:
    return await _get(ctx, token, "/runner/resource", params={"namespace": namespace}, base=RUNNER_BASE_URL)


async def create_runner_resource_class(ctx, token: str, resource_class: str, description: str) -> dict:
    return await _post(ctx, token, "/runner/resource", json={"resource-class": resource_class, "description": description}, base=RUNNER_BASE_URL)


async def delete_runner_resource_class(ctx, token: str, resource_id: str) -> Any:
    return await _delete(ctx, token, f"/runner/resource/{resource_id}", base=RUNNER_BASE_URL)


# ──────────────────────────────────────────────────────────────────────────
# Ярус 3 value-add: project health audit
# ──────────────────────────────────────────────────────────────────────────


async def audit_project_health(ctx, token: str, project_slug: str, workflow_name: str = "") -> dict:
    """Aggregate a project's own health: pipeline count from the most recent
    fetch, flaky tests, and (if a workflow_name is given) its Insights
    summary -- one call instead of manually cross-referencing 3+ endpoints.
    """
    result: dict = {"project_slug": project_slug}
    try:
        pipelines = await list_project_pipelines(ctx, token, project_slug)
        items = pipelines.get("items", []) if isinstance(pipelines, dict) else []
        result["recent_pipeline_count"] = len(items)
        result["latest_pipeline_state"] = (items[0].get("state") if items else None)
    except ClientFail as e:
        result["pipelines_error"] = e.message
    try:
        flaky = await get_flaky_tests(ctx, token, project_slug)
        result["flaky_tests_count"] = len(flaky.get("flaky_tests", [])) if isinstance(flaky, dict) else 0
    except ClientFail as e:
        result["flaky_tests_error"] = e.message
    if workflow_name:
        try:
            summary = await get_workflow_insights(ctx, token, project_slug, workflow_name)
            result["workflow_insights"] = summary
        except ClientFail as e:
            result["workflow_insights_error"] = e.message
    return result
