"""Context (secrets) chat functions for CircleCI Connector: list/create/get/
delete contexts, list/set/remove context env vars, restrictions.
Built on circleci_client.py / schemas.py.
"""
from __future__ import annotations

from imperal_sdk import ActionResult

import circleci_client as cc
from app import ext, chat
from handlers_connection import resolve_or_error
from schemas import (
    ListContextsParams, Context, ContextList,
    CreateContextParams, GetContextParams, DeleteContextParams, DeleteResult,
    ListContextEnvVarsParams, ContextEnvVar, ContextEnvVarList,
    SetContextEnvVarParams, RemoveContextEnvVarParams,
)


@chat.function(
    "list_contexts",
    "List CircleCI contexts (shared secret groups usable across projects) for an organization.",
    action_type="read",
    chain_callable=True,
    data_model=ContextList,
    event="circleci-connector.list_contexts",
)
async def list_contexts(ctx, params: ListContextsParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        resp = await cc.list_contexts(ctx, token, owner_slug=params.owner_slug, page_token=params.page_token)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_CONTEXTS_LIST_FAILED")
    items = resp.get("items", []) if isinstance(resp, dict) else []
    return ActionResult.ok(ContextList(
        items=[Context(id=c.get("id", ""), name=c.get("name", ""), created_at=c.get("created-at", "")) for c in items],
        next_page_token=resp.get("next_page_token", "") if isinstance(resp, dict) else "",
    ))


@chat.function(
    "create_context",
    "Create a new CircleCI context -- a named group of secrets shareable across multiple projects in an organization.",
    action_type="write",
    chain_callable=True,
    data_model=Context,
    event="circleci-connector.create_context",
    effects=["circleci.context.created"],
)
async def create_context(ctx, params: CreateContextParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    if not params.name.strip() or not params.owner_slug.strip():
        return ActionResult.error("name and owner_slug are both required.", code="CIRCLECI_MISSING_FIELDS")
    try:
        c = await cc.create_context(ctx, token, params.name.strip(), owner_slug=params.owner_slug.strip())
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_CONTEXT_CREATE_FAILED")
    return ActionResult.ok(Context(id=c.get("id", ""), name=c.get("name", params.name), created_at=c.get("created-at", "")))


@chat.function(
    "get_context",
    "Read one CircleCI context in full by its id.",
    action_type="read",
    chain_callable=True,
    data_model=Context,
    event="circleci-connector.get_context",
)
async def get_context(ctx, params: GetContextParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        c = await cc.get_context(ctx, token, params.context_id)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_CONTEXT_NOT_FOUND")
    return ActionResult.ok(Context(id=c.get("id", ""), name=c.get("name", ""), created_at=c.get("created-at", "")))


@chat.function(
    "delete_context",
    "Permanently delete a CircleCI context and every secret stored inside it. Cannot be undone.",
    action_type="destructive",
    chain_callable=True,
    data_model=DeleteResult,
    event="circleci-connector.delete_context",
    effects=["circleci.context.deleted"],
)
async def delete_context(ctx, params: DeleteContextParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        await cc.delete_context(ctx, token, params.context_id)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_CONTEXT_DELETE_FAILED")
    return ActionResult.ok(DeleteResult(id=params.context_id, deleted=True))


@chat.function(
    "list_context_env_vars",
    "List the environment variable NAMES stored in a CircleCI context (values are never returned).",
    action_type="read",
    chain_callable=True,
    data_model=ContextEnvVarList,
    event="circleci-connector.list_context_env_vars",
)
async def list_context_env_vars(ctx, params: ListContextEnvVarsParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        resp = await cc.list_context_env_vars(ctx, token, params.context_id, params.page_token)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_CONTEXT_ENVVARS_LIST_FAILED")
    items = resp.get("items", []) if isinstance(resp, dict) else []
    return ActionResult.ok(ContextEnvVarList(
        items=[ContextEnvVar(variable=v.get("variable", ""), created_at=v.get("created-at", ""), context_id=v.get("context-id", "")) for v in items],
        next_page_token=resp.get("next_page_token", "") if isinstance(resp, dict) else "",
    ))


@chat.function(
    "set_context_env_var",
    "Add or update a secret environment variable in a CircleCI context. The value is never echoed back once set.",
    action_type="write",
    chain_callable=True,
    data_model=ContextEnvVar,
    event="circleci-connector.set_context_env_var",
    effects=["circleci.context.env_var.set"],
)
async def set_context_env_var(ctx, params: SetContextEnvVarParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    if not params.variable_name.strip():
        return ActionResult.error("variable_name is required.", code="CIRCLECI_MISSING_VARIABLE_NAME")
    try:
        v = await cc.set_context_env_var(ctx, token, params.context_id, params.variable_name.strip(), params.value)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_CONTEXT_ENVVAR_SET_FAILED")
    return ActionResult.ok(ContextEnvVar(variable=v.get("variable", params.variable_name), context_id=params.context_id))


@chat.function(
    "remove_context_env_var",
    "Permanently remove one environment variable from a CircleCI context. Cannot be undone.",
    action_type="destructive",
    chain_callable=True,
    data_model=DeleteResult,
    event="circleci-connector.remove_context_env_var",
    effects=["circleci.context.env_var.removed"],
)
async def remove_context_env_var(ctx, params: RemoveContextEnvVarParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        await cc.delete_context_env_var(ctx, token, params.context_id, params.variable_name)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_CONTEXT_ENVVAR_DELETE_FAILED")
    return ActionResult.ok(DeleteResult(id=params.variable_name, deleted=True))
