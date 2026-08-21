"""Pipeline Definitions + Triggers + User/Collaborations chat functions for
CircleCI Connector. Built on circleci_client.py / schemas.py.
"""
from __future__ import annotations

from imperal_sdk import ActionResult

import circleci_client as cc
from app import ext, chat
from handlers_connection import resolve_or_error
from schemas import (
    ListPipelineDefinitionsParams, PipelineDefinition, PipelineDefinitionList,
    ListTriggersParams, Trigger, TriggerList, DeleteTriggerParams, DeleteResult,
    CircleciUser, Collaboration, CollaborationList,
)
from schemas import NoParams


@chat.function(
    "list_pipeline_definitions",
    "List the named pipeline definitions configured on a CircleCI project (each maps a config file path to a "
    "checkout source, e.g. main config.yml vs a scheduled-only config).",
    action_type="read",
    chain_callable=True,
    data_model=PipelineDefinitionList,
    event="circleci-connector.list_pipeline_definitions",
)
async def list_pipeline_definitions(ctx, params: ListPipelineDefinitionsParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        resp = await cc.list_pipeline_definitions(ctx, token, params.project_slug, params.page_token)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_PIPELINE_DEFS_LIST_FAILED")
    items = resp.get("items", []) if isinstance(resp, dict) else []
    return ActionResult.ok(PipelineDefinitionList(
        items=[PipelineDefinition(
            id=d.get("id", ""), name=d.get("name", ""),
            config_source_provider=(d.get("config_source") or {}).get("provider", ""),
            config_source_file_path=(d.get("config_source") or {}).get("file-path", ""),
            checkout_source_provider=(d.get("checkout_source") or {}).get("provider", ""),
        ) for d in items],
        next_page_token=resp.get("next_page_token", "") if isinstance(resp, dict) else "",
    ))


@chat.function(
    "list_triggers",
    "List the triggers (webhook/schedule sources that can start a pipeline) configured on a CircleCI project, "
    "by its project id (UUID, from get_project).",
    action_type="read",
    chain_callable=True,
    data_model=TriggerList,
    event="circleci-connector.list_triggers",
)
async def list_triggers(ctx, params: ListTriggersParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        resp = await cc.list_triggers(ctx, token, params.project_id, params.page_token)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_TRIGGERS_LIST_FAILED")
    items = resp.get("items", []) if isinstance(resp, dict) else []
    return ActionResult.ok(TriggerList(
        items=[Trigger(
            id=t.get("id", ""), name=t.get("name", ""),
            event_source_type=(t.get("event_source") or {}).get("type", ""),
            event_source_webhook_url=(t.get("event_source") or {}).get("webhook_url", ""),
            config_source_provider=(t.get("config_source") or {}).get("provider", ""),
        ) for t in items],
        next_page_token=resp.get("next_page_token", "") if isinstance(resp, dict) else "",
    ))


@chat.function(
    "delete_trigger",
    "Permanently delete a trigger from a CircleCI project. Cannot be undone -- pipelines will no longer start from this source.",
    action_type="destructive",
    chain_callable=True,
    data_model=DeleteResult,
    event="circleci-connector.delete_trigger",
    effects=["circleci.trigger.deleted"],
)
async def delete_trigger(ctx, params: DeleteTriggerParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        await cc.delete_trigger(ctx, token, params.project_id, params.trigger_id)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_TRIGGER_DELETE_FAILED")
    return ActionResult.ok(DeleteResult(id=params.trigger_id, deleted=True))


@chat.function(
    "get_current_user",
    "Read the CircleCI user identity that owns the connected Personal API Token.",
    action_type="read",
    chain_callable=True,
    data_model=CircleciUser,
    event="circleci-connector.get_current_user",
)
async def get_current_user(ctx, params: NoParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx)
    if err:
        return err
    try:
        u = await cc.get_current_user(ctx, token)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_USER_FETCH_FAILED")
    return ActionResult.ok(CircleciUser(id=u.get("id", ""), login=u.get("login", ""), name=u.get("name", "")))


@chat.function(
    "list_collaborations",
    "List the VCS organizations/accounts the connected CircleCI user has access to across GitHub/Bitbucket/GitLab.",
    action_type="read",
    chain_callable=True,
    data_model=CollaborationList,
    event="circleci-connector.list_collaborations",
)
async def list_collaborations(ctx, params: NoParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx)
    if err:
        return err
    try:
        resp = await cc.get_collaborations(ctx, token)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_COLLABORATIONS_FETCH_FAILED")
    items = resp if isinstance(resp, list) else []
    return ActionResult.ok(CollaborationList(items=[
        Collaboration(id=c.get("id", ""), slug=c.get("slug", ""), name=c.get("name", ""), vcs_type=c.get("vcs_type", ""))
        for c in items
    ]))
