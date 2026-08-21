"""Project + env var + checkout key chat functions for CircleCI Connector.
Built on circleci_client.py / schemas.py.
"""
from __future__ import annotations

from imperal_sdk import ActionResult

import circleci_client as cc
from app import ext, chat
from handlers_connection import resolve_or_error
from schemas import (
    GetProjectParams, Project,
    ListProjectEnvVarsParams, ProjectEnvVar, ProjectEnvVarList,
    CreateProjectEnvVarParams, DeleteProjectEnvVarParams, DeleteResult,
    ListCheckoutKeysParams, CheckoutKey, CheckoutKeyList,
    CreateCheckoutKeyParams, DeleteCheckoutKeyParams,
)


@chat.function(
    "get_project",
    "Read one CircleCI project in full by its slug (e.g. 'gh/CircleCI-Public/api-preview-docs') -- "
    "its VCS info, organization, and default branch.",
    action_type="read",
    chain_callable=True,
    data_model=Project,
    event="circleci-connector.get_project",
)
async def get_project(ctx, params: GetProjectParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        p = await cc.get_project(ctx, token, params.project_slug)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_PROJECT_NOT_FOUND")
    vcs_info = p.get("vcs_info") or {}
    return ActionResult.ok(Project(
        id=p.get("id", ""), slug=p.get("slug", params.project_slug),
        name=p.get("name", ""), organization_name=p.get("organization_name", ""),
        organization_slug=p.get("organization_slug", ""),
        vcs_type=vcs_info.get("vcs_url", ""),
        default_branch=vcs_info.get("default_branch", ""),
    ))


@chat.function(
    "list_project_env_vars",
    "List a CircleCI project's environment variables (names only -- values are masked/partial by CircleCI's own API).",
    action_type="read",
    chain_callable=True,
    data_model=ProjectEnvVarList,
    event="circleci-connector.list_project_env_vars",
)
async def list_project_env_vars(ctx, params: ListProjectEnvVarsParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        resp = await cc.list_env_vars(ctx, token, params.project_slug)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_ENVVAR_LIST_FAILED")
    items = resp.get("items", []) if isinstance(resp, dict) else []
    return ActionResult.ok(ProjectEnvVarList(
        items=[ProjectEnvVar(name=i.get("name", ""), value=i.get("value", "")) for i in items],
        next_page_token=resp.get("next_page_token", "") if isinstance(resp, dict) else "",
    ))


@chat.function(
    "create_project_env_var",
    "Create (or overwrite) an environment variable on a CircleCI project. The value is never returned "
    "again by CircleCI once set -- only a masked preview.",
    action_type="write",
    chain_callable=True,
    data_model=ProjectEnvVar,
    event="circleci-connector.create_project_env_var",
    effects=["circleci.project_env_var.created"],
)
async def create_project_env_var(ctx, params: CreateProjectEnvVarParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    if not params.name.strip():
        return ActionResult.error("An environment variable name is required.", code="CIRCLECI_ENVVAR_NAME_REQUIRED")
    try:
        r = await cc.create_env_var(ctx, token, params.project_slug, params.name.strip(), params.value)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_ENVVAR_CREATE_FAILED")
    return ActionResult.ok(ProjectEnvVar(name=r.get("name", params.name), value=r.get("value", "")))


@chat.function(
    "delete_project_env_var",
    "Permanently delete an environment variable from a CircleCI project. Cannot be undone.",
    action_type="destructive",
    chain_callable=True,
    data_model=DeleteResult,
    event="circleci-connector.delete_project_env_var",
    effects=["circleci.project_env_var.deleted"],
)
async def delete_project_env_var(ctx, params: DeleteProjectEnvVarParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        await cc.delete_env_var(ctx, token, params.project_slug, params.name)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_ENVVAR_DELETE_FAILED")
    return ActionResult.ok(DeleteResult(id=params.name, deleted=True))


@chat.function(
    "list_checkout_keys",
    "List the checkout (deploy) keys configured on a CircleCI project.",
    action_type="read",
    chain_callable=True,
    data_model=CheckoutKeyList,
    event="circleci-connector.list_checkout_keys",
)
async def list_checkout_keys(ctx, params: ListCheckoutKeysParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        resp = await cc.list_checkout_keys(ctx, token, params.project_slug)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_CHECKOUT_KEY_LIST_FAILED")
    items = resp.get("items", []) if isinstance(resp, dict) else []
    return ActionResult.ok(CheckoutKeyList(items=[
        CheckoutKey(
            fingerprint=i.get("fingerprint", ""), type=i.get("type", ""),
            preferred=i.get("preferred", False), created_at=i.get("created-at", i.get("created_at", "")),
            public_key=i.get("public-key", i.get("public_key", "")),
        ) for i in items
    ]))


@chat.function(
    "create_checkout_key",
    "Create a new checkout (deploy) key for a CircleCI project -- either a deploy-key (project-scoped) "
    "or a github-user-key (uses the connected VCS user's own permissions).",
    action_type="write",
    chain_callable=True,
    data_model=CheckoutKey,
    event="circleci-connector.create_checkout_key",
    effects=["circleci.checkout_key.created"],
)
async def create_checkout_key(ctx, params: CreateCheckoutKeyParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        r = await cc.create_checkout_key(ctx, token, params.project_slug, params.key_type)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_CHECKOUT_KEY_CREATE_FAILED")
    return ActionResult.ok(CheckoutKey(
        fingerprint=r.get("fingerprint", ""), type=r.get("type", params.key_type),
        preferred=r.get("preferred", False), created_at=r.get("created-at", r.get("created_at", "")),
        public_key=r.get("public-key", r.get("public_key", "")),
    ))


@chat.function(
    "delete_checkout_key",
    "Permanently delete a checkout key from a CircleCI project by its fingerprint. Cannot be undone -- "
    "any builds relying on it will lose repository access.",
    action_type="destructive",
    chain_callable=True,
    data_model=DeleteResult,
    event="circleci-connector.delete_checkout_key",
    effects=["circleci.checkout_key.deleted"],
)
async def delete_checkout_key(ctx, params: DeleteCheckoutKeyParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        await cc.delete_checkout_key(ctx, token, params.project_slug, params.fingerprint)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_CHECKOUT_KEY_DELETE_FAILED")
    return ActionResult.ok(DeleteResult(id=params.fingerprint, deleted=True))
