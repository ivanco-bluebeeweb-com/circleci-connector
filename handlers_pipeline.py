"""Pipeline chat functions for CircleCI Connector: list/trigger/get/config/
workflows/continue. Built on circleci_client.py / schemas.py.
"""
from __future__ import annotations

import json

from imperal_sdk import ActionResult

import circleci_client as cc
from app import ext, chat
from handlers_connection import resolve_or_error
from schemas import (
    ListPipelinesParams, Pipeline, PipelineList,
    GetPipelineParams, TriggerPipelineParams, ContinuePipelineParams,
    GetPipelineConfigParams, PipelineConfig,
    ListPipelineWorkflowsParams, Workflow, WorkflowList,
)


def _pipeline_from(p: dict) -> Pipeline:
    vcs = p.get("vcs") or {}
    return Pipeline(
        id=p.get("id", ""), number=p.get("number", 0),
        project_slug=p.get("project_slug", ""), state=p.get("state", ""),
        created_at=p.get("created_at", ""), updated_at=p.get("updated_at", ""),
        trigger_type=(p.get("trigger") or {}).get("type", ""),
        trigger_actor=((p.get("trigger") or {}).get("actor") or {}).get("login", ""),
        vcs_branch=vcs.get("branch", ""), vcs_revision=vcs.get("revision", ""),
        vcs_subject=(vcs.get("commit") or {}).get("subject", ""),
    )


@chat.function(
    "list_pipelines",
    "List pipelines for a CircleCI project, optionally filtered to one branch.",
    action_type="read",
    chain_callable=True,
    data_model=PipelineList,
    event="circleci-connector.list_pipelines",
)
async def list_pipelines(ctx, params: ListPipelinesParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        resp = await cc.list_project_pipelines(ctx, token, params.project_slug, params.branch, params.page_token)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_PIPELINE_LIST_FAILED")
    items = resp.get("items", []) if isinstance(resp, dict) else []
    return ActionResult.ok(PipelineList(
        items=[_pipeline_from(p) for p in items],
        next_page_token=resp.get("next_page_token", "") if isinstance(resp, dict) else "",
    ))


@chat.function(
    "get_pipeline",
    "Read one CircleCI pipeline in full by its id (UUID).",
    action_type="read",
    chain_callable=True,
    data_model=Pipeline,
    event="circleci-connector.get_pipeline",
)
async def get_pipeline(ctx, params: GetPipelineParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        p = await cc.get_pipeline(ctx, token, params.pipeline_id)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_PIPELINE_NOT_FOUND")
    return ActionResult.ok(_pipeline_from(p))


@chat.function(
    "trigger_pipeline",
    "Trigger a new CircleCI pipeline run for a project on a branch or tag, optionally passing "
    "pipeline parameters declared in .circleci/config.yml.",
    action_type="write",
    chain_callable=True,
    data_model=Pipeline,
    event="circleci-connector.trigger_pipeline",
    effects=["circleci.pipeline.triggered"],
)
async def trigger_pipeline(ctx, params: TriggerPipelineParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    parameters = None
    if params.parameters_json.strip():
        try:
            parameters = json.loads(params.parameters_json)
        except (TypeError, ValueError):
            return ActionResult.error("parameters_json is not valid JSON.", code="CIRCLECI_BAD_PARAMETERS")
    try:
        p = await cc.trigger_pipeline(ctx, token, params.project_slug, params.branch, params.tag, parameters)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_PIPELINE_TRIGGER_FAILED")
    return ActionResult.ok(_pipeline_from(p))


@chat.function(
    "continue_pipeline",
    "Continue a setup workflow's pipeline with a configuration (used with dynamic config/'setup' "
    "workflows) -- requires the continuation_key handed to the setup job.",
    action_type="write",
    chain_callable=True,
    data_model=Pipeline,
    event="circleci-connector.continue_pipeline",
    effects=["circleci.pipeline.continued"],
)
async def continue_pipeline(ctx, params: ContinuePipelineParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    parameters = None
    if params.parameters_json.strip():
        try:
            parameters = json.loads(params.parameters_json)
        except (TypeError, ValueError):
            return ActionResult.error("parameters_json is not valid JSON.", code="CIRCLECI_BAD_PARAMETERS")
    try:
        await cc.continue_pipeline(ctx, token, params.continuation_key, params.configuration, parameters)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_PIPELINE_CONTINUE_FAILED")
    return ActionResult.ok(Pipeline())


@chat.function(
    "get_pipeline_config",
    "Read the source and compiled .circleci/config.yml of one pipeline.",
    action_type="read",
    chain_callable=True,
    data_model=PipelineConfig,
    event="circleci-connector.get_pipeline_config",
)
async def get_pipeline_config(ctx, params: GetPipelineConfigParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        c = await cc.get_pipeline_config(ctx, token, params.pipeline_id)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_PIPELINE_CONFIG_NOT_FOUND")
    return ActionResult.ok(PipelineConfig(source=c.get("source", ""), compiled=c.get("compiled", "")))


@chat.function(
    "list_pipeline_workflows",
    "List the workflows that ran as part of one pipeline.",
    action_type="read",
    chain_callable=True,
    data_model=WorkflowList,
    event="circleci-connector.list_pipeline_workflows",
)
async def list_pipeline_workflows(ctx, params: ListPipelineWorkflowsParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        resp = await cc.list_pipeline_workflows(ctx, token, params.pipeline_id, params.page_token)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_WORKFLOW_LIST_FAILED")
    items = resp.get("items", []) if isinstance(resp, dict) else []
    return ActionResult.ok(WorkflowList(
        items=[Workflow(
            id=w.get("id", ""), name=w.get("name", ""), status=w.get("status", ""),
            pipeline_id=w.get("pipeline_id", ""), pipeline_number=w.get("pipeline_number", 0),
            project_slug=w.get("project_slug", ""), created_at=w.get("created_at", ""),
            stopped_at=w.get("stopped_at", ""), started_by=w.get("started_by", ""),
            tag=w.get("tag", ""),
        ) for w in items],
        next_page_token=resp.get("next_page_token", "") if isinstance(resp, dict) else "",
    ))
