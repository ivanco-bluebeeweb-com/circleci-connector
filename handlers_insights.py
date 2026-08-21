"""Insights chat functions for CircleCI Connector: project/workflow/job
metrics summaries, flaky test detection, org-level summary.
Built on circleci_client.py / schemas.py.
"""
from __future__ import annotations

from imperal_sdk import ActionResult

import circleci_client as cc
from app import ext, chat
from handlers_connection import resolve_or_error
from schemas import (
    GetProjectInsightsParams, InsightsMetricsSummary,
    GetWorkflowJobInsightsParams, JobInsightsRow, JobInsightsList,
    GetFlakyTestsParams, FlakyTest, FlakyTestList,
    GetOrgInsightsSummaryParams,
)


@chat.function(
    "get_project_insights",
    "Read a CircleCI workflow's success-rate/duration/credits Insights summary over a reporting window "
    "(last-24-hours through last-90-days).",
    action_type="read",
    chain_callable=True,
    data_model=InsightsMetricsSummary,
    event="circleci-connector.get_project_insights",
)
async def get_project_insights(ctx, params: GetProjectInsightsParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    if not params.workflow_name:
        return ActionResult.error("workflow_name is required to read Insights.", code="CIRCLECI_MISSING_WORKFLOW_NAME")
    try:
        resp = await cc.get_workflow_insights(
            ctx, token, params.project_slug, params.workflow_name, params.branch, params.reporting_window,
        )
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_INSIGHTS_FAILED")
    items = resp.get("items", []) if isinstance(resp, dict) else []
    metrics = (items[0].get("metrics") if items else None) or {}
    duration_metrics = metrics.get("duration_metrics", {}) or {}
    return ActionResult.ok(InsightsMetricsSummary(
        success_rate=metrics.get("success_rate", 0.0),
        total_runs=metrics.get("total_runs", 0),
        failed_runs=metrics.get("failed_runs", 0),
        successful_runs=metrics.get("successful_runs", 0),
        duration_median_secs=duration_metrics.get("median", 0),
        duration_p95_secs=duration_metrics.get("p95", 0),
        credits_used=metrics.get("total_credits_used", 0),
    ))


@chat.function(
    "get_workflow_job_insights",
    "Read per-job Insights metrics (success rate, median/p95 duration) within one CircleCI workflow -- "
    "helps spot which specific job is the bottleneck or the least reliable.",
    action_type="read",
    chain_callable=True,
    data_model=JobInsightsList,
    event="circleci-connector.get_workflow_job_insights",
)
async def get_workflow_job_insights(ctx, params: GetWorkflowJobInsightsParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        resp = await cc.get_workflow_run_insights(ctx, token, params.project_slug, params.workflow_name, params.branch)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_JOB_INSIGHTS_FAILED")
    items = resp.get("items", []) if isinstance(resp, dict) else []
    rows: list[JobInsightsRow] = []
    for j in items:
        metrics = j.get("metrics", {}) or {}
        duration_data = metrics.get("duration_metrics", {}) or {}
        rows.append(JobInsightsRow(
            name=j.get("name", ""),
            success_rate=metrics.get("success_rate", 0.0),
            total_runs=metrics.get("total_runs", 0),
            duration_median_secs=duration_data.get("median", 0),
        ))
    return ActionResult.ok(JobInsightsList(items=rows))


@chat.function(
    "get_flaky_tests",
    "List tests CircleCI has flagged as flaky (intermittently failing) for a project -- helps prioritise "
    "test suite reliability work.",
    action_type="read",
    chain_callable=True,
    data_model=FlakyTestList,
    event="circleci-connector.get_flaky_tests",
)
async def get_flaky_tests(ctx, params: GetFlakyTestsParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        resp = await cc.get_flaky_tests(ctx, token, params.project_slug)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_FLAKY_TESTS_FAILED")
    items = resp.get("flaky_tests", []) if isinstance(resp, dict) else []
    return ActionResult.ok(FlakyTestList(items=[
        FlakyTest(
            test_name=t.get("test_name", ""), job_name=t.get("job_name", ""),
            times_flaked=t.get("times_flaked", 0), source=t.get("source", ""), file=t.get("file", ""),
        ) for t in items
    ]))


@chat.function(
    "get_org_insights_summary",
    "Read an organization-wide CircleCI Insights summary across all its projects for a reporting window.",
    action_type="read",
    chain_callable=True,
    data_model=InsightsMetricsSummary,
    event="circleci-connector.get_org_insights_summary",
)
async def get_org_insights_summary(ctx, params: GetOrgInsightsSummaryParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        resp = await cc.get_org_summary_insights(ctx, token, params.org_slug, params.reporting_window)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_ORG_INSIGHTS_FAILED")
    m = resp.get("metrics", {}) if isinstance(resp, dict) else {}
    duration_metrics = m.get("duration_metrics", {}) or {}
    return ActionResult.ok(InsightsMetricsSummary(
        success_rate=m.get("success_rate", 0.0), total_runs=m.get("total_runs", 0),
        failed_runs=m.get("failed_runs", 0), successful_runs=m.get("successful_runs", 0),
        duration_median_secs=duration_metrics.get("median", 0),
        duration_p95_secs=duration_metrics.get("p95", 0),
        credits_used=m.get("total_credits_used", 0),
    ))
