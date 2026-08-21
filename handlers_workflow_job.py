"""Workflow + Job chat functions for CircleCI Connector: get/approve/cancel/
rerun workflows; get/cancel jobs; artifacts; test results.
Built on circleci_client.py / schemas.py.
"""
from __future__ import annotations

from imperal_sdk import ActionResult

import circleci_client as cc
from app import ext, chat
from handlers_connection import resolve_or_error
from schemas import (
    GetWorkflowParams, Workflow, WorkflowActionParams, WorkflowActionResult,
    ListWorkflowJobsParams, Job, JobList, ApproveJobParams,
    GetJobParams, CancelJobParams, JobActionResult,
    ListJobArtifactsParams, JobArtifact, JobArtifactList,
    ListJobTestsParams, JobTestResult, JobTestResultList,
)


@chat.function(
    "get_workflow",
    "Read one CircleCI workflow in full by its id (UUID) -- status, timing, and which pipeline it belongs to.",
    action_type="read",
    chain_callable=True,
    data_model=Workflow,
    event="circleci-connector.get_workflow",
)
async def get_workflow(ctx, params: GetWorkflowParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        w = await cc.get_workflow(ctx, token, params.workflow_id)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_WORKFLOW_NOT_FOUND")
    return ActionResult.ok(Workflow(
        id=w.get("id", ""), name=w.get("name", ""), status=w.get("status", ""),
        pipeline_id=w.get("pipeline_id", ""), pipeline_number=w.get("pipeline_number", 0),
        project_slug=w.get("project_slug", ""), created_at=w.get("created_at", ""),
        stopped_at=w.get("stopped_at", ""), started_by=w.get("started_by", ""),
        tag=w.get("tag", ""),
    ))


@chat.function(
    "list_workflow_jobs",
    "List the jobs that ran (or are pending approval) as part of one workflow.",
    action_type="read",
    chain_callable=True,
    data_model=JobList,
    event="circleci-connector.list_workflow_jobs",
)
async def list_workflow_jobs(ctx, params: ListWorkflowJobsParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        resp = await cc.list_workflow_jobs(ctx, token, params.workflow_id)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_JOB_LIST_FAILED")
    items = resp.get("items", []) if isinstance(resp, dict) else []
    return ActionResult.ok(JobList(items=[Job(
        id=j.get("id", ""), number=j.get("job_number", 0) or 0, name=j.get("name", ""),
        status=j.get("status", ""), type=j.get("type", ""),
        started_at=j.get("started_at", ""), stopped_at=j.get("stopped_at", ""),
        approval_request_id=j.get("approval_request_id", ""),
    ) for j in items]))


@chat.function(
    "approve_job",
    "Approve a pending on-hold job in a workflow (a manual approval gate) so the workflow continues.",
    action_type="write",
    chain_callable=True,
    data_model=WorkflowActionResult,
    event="circleci-connector.approve_job",
    effects=["circleci.job.approved"],
)
async def approve_job(ctx, params: ApproveJobParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        await cc.approve_workflow_job(ctx, token, params.workflow_id, params.approval_request_id)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_JOB_APPROVE_FAILED")
    return ActionResult.ok(WorkflowActionResult(workflow_id=params.workflow_id, action="approved", ok=True))


@chat.function(
    "cancel_workflow",
    "Cancel a running CircleCI workflow.",
    action_type="write",
    chain_callable=True,
    data_model=WorkflowActionResult,
    event="circleci-connector.cancel_workflow",
    effects=["circleci.workflow.cancelled"],
)
async def cancel_workflow(ctx, params: WorkflowActionParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        await cc.cancel_workflow(ctx, token, params.workflow_id)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_WORKFLOW_CANCEL_FAILED")
    return ActionResult.ok(WorkflowActionResult(workflow_id=params.workflow_id, action="cancelled", ok=True))


@chat.function(
    "rerun_workflow",
    "Rerun a CircleCI workflow -- either from scratch or only its failed jobs.",
    action_type="write",
    chain_callable=True,
    data_model=WorkflowActionResult,
    event="circleci-connector.rerun_workflow",
    effects=["circleci.workflow.rerun"],
)
async def rerun_workflow(ctx, params: WorkflowActionParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        await cc.rerun_workflow(ctx, token, params.workflow_id)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_WORKFLOW_RERUN_FAILED")
    return ActionResult.ok(WorkflowActionResult(workflow_id=params.workflow_id, action="rerun", ok=True))


@chat.function(
    "get_job",
    "Read one CircleCI job in full by its project slug and numeric job number.",
    action_type="read",
    chain_callable=True,
    data_model=Job,
    event="circleci-connector.get_job",
)
async def get_job(ctx, params: GetJobParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        j = await cc.get_job_by_number(ctx, token, params.project_slug, params.job_number)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_JOB_NOT_FOUND")
    return ActionResult.ok(Job(
        id=j.get("id", ""), number=j.get("number", params.job_number), name=j.get("name", ""),
        status=j.get("status", ""), type=j.get("type", ""),
        started_at=j.get("started_at", ""), stopped_at=j.get("stopped_at", ""),
    ))


@chat.function(
    "cancel_job",
    "Cancel a running CircleCI job by its project slug and numeric job number.",
    action_type="write",
    chain_callable=True,
    data_model=JobActionResult,
    event="circleci-connector.cancel_job",
    effects=["circleci.job.cancelled"],
)
async def cancel_job(ctx, params: CancelJobParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        await cc.cancel_job_by_number(ctx, token, params.project_slug, params.job_number)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_JOB_CANCEL_FAILED")
    return ActionResult.ok(JobActionResult(job_number=params.job_number, action="cancelled", ok=True))


@chat.function(
    "list_job_artifacts",
    "List the build artifacts produced by one CircleCI job (files it uploaded, with download URLs).",
    action_type="read",
    chain_callable=True,
    data_model=JobArtifactList,
    event="circleci-connector.list_job_artifacts",
)
async def list_job_artifacts(ctx, params: ListJobArtifactsParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        resp = await cc.get_job_artifacts(ctx, token, params.project_slug, params.job_number)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_ARTIFACTS_LIST_FAILED")
    items = resp.get("items", []) if isinstance(resp, dict) else []
    return ActionResult.ok(JobArtifactList(
        items=[JobArtifact(path=a.get("path", ""), url=a.get("url", ""), node_index=a.get("node_index", 0)) for a in items],
        next_page_token=resp.get("next_page_token", "") if isinstance(resp, dict) else "",
    ))


@chat.function(
    "list_job_tests",
    "List the individual test results (pass/fail, timing) recorded for one CircleCI job, if the job "
    "uploaded JUnit/test-metadata via 'store_test_results'.",
    action_type="read",
    chain_callable=True,
    data_model=JobTestResultList,
    event="circleci-connector.list_job_tests",
)
async def list_job_tests(ctx, params: ListJobTestsParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        resp = await cc.get_job_tests(ctx, token, params.project_slug, params.job_number, params.page_token)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_TESTS_LIST_FAILED")
    items = resp.get("items", []) if isinstance(resp, dict) else []
    return ActionResult.ok(JobTestResultList(
        items=[JobTestResult(
            name=t.get("name", ""), classname=t.get("classname", ""), result=t.get("result", ""),
            message=t.get("message", ""), run_time=t.get("run_time", 0.0), file=t.get("file", ""),
        ) for t in items],
        next_page_token=resp.get("next_page_token", "") if isinstance(resp, dict) else "",
    ))
