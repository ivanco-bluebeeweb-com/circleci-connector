"""Self-hosted Runner API chat functions for CircleCI Connector (separate
host: runner.circleci.com). Built on circleci_client.py / schemas.py.
"""
from __future__ import annotations

from imperal_sdk import ActionResult

import circleci_client as cc
from app import ext, chat
from handlers_connection import resolve_or_error
from schemas import (
    ListRunnersParams, Runner, RunnerList,
    ListRunnerResourceClassesParams, RunnerResourceClass, RunnerResourceClassList,
    CreateRunnerResourceClassParams, DeleteRunnerResourceClassParams, DeleteResult,
    CreateRunnerTokenParams, RunnerToken,
    ListRunnerTokensParams, RunnerTokenSummary, RunnerTokenList,
    DeleteRunnerTokenParams,
)


@chat.function(
    "list_runners",
    "List self-hosted CircleCI runners (machines you registered to execute jobs), optionally filtered by "
    "resource class or namespace.",
    action_type="read",
    chain_callable=True,
    data_model=RunnerList,
    event="circleci-connector.list_runners",
)
async def list_runners(ctx, params: ListRunnersParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        resp = await cc.list_runners(ctx, token, params.resource_class, params.namespace)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_RUNNERS_LIST_FAILED")
    items = resp.get("items", []) if isinstance(resp, dict) else (resp if isinstance(resp, list) else [])
    return ActionResult.ok(RunnerList(items=[
        Runner(
            id=r.get("id", ""), hostname=r.get("hostname", ""), name=r.get("name", ""),
            version=r.get("version", ""), first_connected=r.get("first_connected", ""),
            last_connected=r.get("last_connected", ""), last_used=r.get("last_used", ""),
        ) for r in items
    ]))


@chat.function(
    "list_runner_resource_classes",
    "List the resource classes (named pools of self-hosted runners) defined under a namespace.",
    action_type="read",
    chain_callable=True,
    data_model=RunnerResourceClassList,
    event="circleci-connector.list_runner_resource_classes",
)
async def list_runner_resource_classes(ctx, params: ListRunnerResourceClassesParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        resp = await cc.list_runner_resource_classes(ctx, token, params.namespace)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_RUNNER_RESOURCE_CLASSES_LIST_FAILED")
    items = resp.get("items", []) if isinstance(resp, dict) else (resp if isinstance(resp, list) else [])
    return ActionResult.ok(RunnerResourceClassList(items=[
        RunnerResourceClass(id=r.get("id", ""), resource_class=r.get("resource_class", ""), description=r.get("description", ""))
        for r in items
    ]))


@chat.function(
    "create_runner_resource_class",
    "Create a new resource class (named pool) for self-hosted CircleCI runners, e.g. 'my-namespace/linux-arm64'.",
    action_type="write",
    chain_callable=True,
    data_model=RunnerResourceClass,
    event="circleci-connector.create_runner_resource_class",
    effects=["circleci.runner_resource_class.created"],
)
async def create_runner_resource_class(ctx, params: CreateRunnerResourceClassParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    if not params.resource_class.strip():
        return ActionResult.error("resource_class is required.", code="CIRCLECI_MISSING_RESOURCE_CLASS")
    try:
        r = await cc.create_runner_resource_class(ctx, token, params.resource_class.strip(), params.description)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_RUNNER_RESOURCE_CLASS_CREATE_FAILED")
    return ActionResult.ok(RunnerResourceClass(
        id=r.get("id", ""), resource_class=r.get("resource_class", params.resource_class), description=r.get("description", params.description),
    ))


@chat.function(
    "delete_runner_resource_class",
    "Permanently delete a self-hosted runner resource class. Cannot be undone -- any runners in it lose their pool.",
    action_type="destructive",
    chain_callable=True,
    data_model=DeleteResult,
    event="circleci-connector.delete_runner_resource_class",
    effects=["circleci.runner_resource_class.deleted"],
)
async def delete_runner_resource_class(ctx, params: DeleteRunnerResourceClassParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        await cc.delete_runner_resource_class(ctx, token, params.resource_class_id)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_RUNNER_RESOURCE_CLASS_DELETE_FAILED")
    return ActionResult.ok(DeleteResult(id=params.resource_class_id, deleted=True))


@chat.function(
    "create_runner_token",
    "Create a new auth token that lets a self-hosted runner register itself under a resource class. "
    "The token value is only ever returned once, at creation.",
    action_type="write",
    chain_callable=True,
    data_model=RunnerToken,
    event="circleci-connector.create_runner_token",
    effects=["circleci.runner_token.created"],
)
async def create_runner_token(ctx, params: CreateRunnerTokenParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    if not params.resource_class.strip():
        return ActionResult.error("resource_class is required.", code="CIRCLECI_MISSING_RESOURCE_CLASS")
    try:
        r = await cc.create_runner_token(ctx, token, params.resource_class.strip(), params.nickname)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_RUNNER_TOKEN_CREATE_FAILED")
    return ActionResult.ok(RunnerToken(
        id=r.get("id", ""), token=r.get("token", ""), nickname=r.get("nickname", params.nickname),
        resource_class=r.get("resource_class", params.resource_class),
    ))


@chat.function(
    "list_runner_tokens",
    "List auth tokens issued for a self-hosted runner resource class (never reveals the token value itself, only metadata).",
    action_type="read",
    chain_callable=True,
    data_model=RunnerTokenList,
    event="circleci-connector.list_runner_tokens",
)
async def list_runner_tokens(ctx, params: ListRunnerTokensParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        resp = await cc.list_runner_tokens(ctx, token, params.resource_class)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_RUNNER_TOKENS_LIST_FAILED")
    items = resp.get("items", []) if isinstance(resp, dict) else (resp if isinstance(resp, list) else [])
    return ActionResult.ok(RunnerTokenList(items=[
        RunnerTokenSummary(
            id=t.get("id", ""), nickname=t.get("nickname", ""),
            resource_class=t.get("resource_class", ""), created_at=t.get("created_at", ""),
        ) for t in items
    ]))


@chat.function(
    "delete_runner_token",
    "Permanently revoke a self-hosted runner auth token. Cannot be undone -- runners using it can no longer authenticate.",
    action_type="destructive",
    chain_callable=True,
    data_model=DeleteResult,
    event="circleci-connector.delete_runner_token",
    effects=["circleci.runner_token.deleted"],
)
async def delete_runner_token(ctx, params: DeleteRunnerTokenParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        await cc.delete_runner_by_token_id(ctx, token, params.token_id)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_RUNNER_TOKEN_DELETE_FAILED")
    return ActionResult.ok(DeleteResult(id=params.token_id, deleted=True))
