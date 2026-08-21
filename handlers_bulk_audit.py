"""Bulk operations + project health audit (Ярус 3 value-add) chat functions
for CircleCI Connector. Built on circleci_client.py / schemas.py.
"""
from __future__ import annotations

import asyncio
import json

from imperal_sdk import ActionResult

import circleci_client as cc
from app import ext, chat
from handlers_connection import resolve_or_error
from schemas import (
    BulkPipelinesParams, BulkResultItem, BulkResult,
    AuditProjectHealthParams, ProjectHealthReport,
)


@chat.function(
    "bulk_cancel_pipelines",
    "Cancel several CircleCI pipelines' workflows in one call, by explicit pipeline ids. Continues past "
    "per-item failures and reports which succeeded/failed.",
    action_type="destructive",
    chain_callable=True,
    data_model=BulkResult,
    event="circleci-connector.bulk_cancel_pipelines",
    effects=["circleci.pipeline.bulk_cancelled"],
)
async def bulk_cancel_pipelines(ctx, params: BulkPipelinesParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        pipeline_ids = json.loads(params.pipeline_ids_json or "[]")
    except (TypeError, ValueError):
        return ActionResult.error("pipeline_ids_json must be a valid JSON array.", code="CIRCLECI_INVALID_JSON")
    if not isinstance(pipeline_ids, list) or not pipeline_ids:
        return ActionResult.error("At least one pipeline id is required.", code="CIRCLECI_MISSING_PIPELINE_IDS")

    items: list[BulkResultItem] = []
    succeeded = 0
    failed = 0
    for pid in pipeline_ids:
        try:
            workflows_resp = await cc.list_pipeline_workflows(ctx, token, pid)
            workflows = workflows_resp.get("items", []) if isinstance(workflows_resp, dict) else []
            if not workflows:
                items.append(BulkResultItem(id=pid, ok=False, detail="No workflows found for this pipeline."))
                failed += 1
                continue
            errs = []
            for wf in workflows:
                try:
                    await cc.cancel_workflow(ctx, token, wf.get("id", ""))
                except cc.ClientFail as e:
                    errs.append(e.message)
            if errs:
                items.append(BulkResultItem(id=pid, ok=False, detail="; ".join(errs)))
                failed += 1
            else:
                items.append(BulkResultItem(id=pid, ok=True, detail=f"{len(workflows)} workflow(s) cancelled."))
                succeeded += 1
        except cc.ClientFail as e:
            items.append(BulkResultItem(id=pid, ok=False, detail=e.message))
            failed += 1
    return ActionResult.ok(BulkResult(items=items, succeeded=succeeded, failed=failed))


@chat.function(
    "audit_project_health",
    "Build one aggregated health report for a CircleCI project: recent pipeline count/state, flaky test "
    "count, and (if a workflow is given) its success rate and p95 duration -- one call instead of manually "
    "cross-referencing pipelines/Insights/flaky-tests endpoints.",
    action_type="read",
    chain_callable=True,
    data_model=ProjectHealthReport,
    event="circleci-connector.audit_project_health",
)
async def audit_project_health(ctx, params: AuditProjectHealthParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    notes: list[str] = []
    recent_failed_runs = 0
    try:
        pipelines_resp = await cc.list_project_pipelines(ctx, token, params.project_slug)
        pipelines = pipelines_resp.get("items", []) if isinstance(pipelines_resp, dict) else []
        recent_failed_runs = sum(1 for p in pipelines if p.get("state") == "errored")
    except cc.ClientFail as e:
        notes.append(f"Pipelines: {e.message}")

    flaky_count = 0
    try:
        flaky_resp = await cc.get_flaky_tests(ctx, token, params.project_slug)
        flaky_count = len(flaky_resp.get("flaky_tests", [])) if isinstance(flaky_resp, dict) else 0
    except cc.ClientFail as e:
        notes.append(f"Flaky tests: {e.message}")

    success_rate = 0.0
    median_duration = 0
    p95_duration = 0
    if params.workflow_name:
        try:
            insights_resp = await cc.get_workflow_insights(ctx, token, params.project_slug, params.workflow_name)
            wf_items = insights_resp.get("items", []) if isinstance(insights_resp, dict) else []
            metrics = (wf_items[0].get("metrics") if wf_items else None) or {}
            success_rate = metrics.get("success_rate", 0.0)
            median_duration = (metrics.get("duration_metrics") or {}).get("median", 0)
            p95_duration = (metrics.get("duration_metrics") or {}).get("p95", 0)
        except cc.ClientFail as e:
            notes.append(f"Insights: {e.message}")
    else:
        notes.append("No workflow_name given -- success rate and duration metrics were skipped.")

    stale_defs = 0
    try:
        defs_resp = await cc.list_pipeline_definitions(ctx, token, params.project_slug)
        stale_defs = len(defs_resp.get("items", [])) if isinstance(defs_resp, dict) else 0
    except cc.ClientFail:
        pass  # not critical to the health report; omit silently if unavailable

    return ActionResult.ok(ProjectHealthReport(
        project_slug=params.project_slug, workflow_name=params.workflow_name,
        success_rate=success_rate, recent_failed_runs=recent_failed_runs,
        flaky_test_count=flaky_count, median_duration_secs=median_duration,
        p95_duration_secs=p95_duration, stale_pipeline_definitions=stale_defs,
        notes=notes,
    ))
