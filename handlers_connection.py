"""Connection management for CircleCI Connector: connect/disconnect/list,
storing Personal API Token connections as a JSON array under one secret,
same shape as MuleSoft Connector's / GitLab CI/CD Connector's handlers.
"""
from __future__ import annotations

import json
import uuid

from imperal_sdk import ActionResult

import circleci_client as cc
from app import ext, chat
from schemas import (
    NoParams,
    ConnectCircleciParams, ProviderConnection, ProviderConnectionList,
    DisconnectCircleciParams, DeleteResult,
)

_SECRET_NAME = "circleci_connections"


async def _load_connections(ctx) -> list[dict]:
    raw = await ctx.secrets.get(_SECRET_NAME)
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return data if isinstance(data, list) else []


async def _save_connections(ctx, connections: list[dict]) -> None:
    await ctx.secrets.set(_SECRET_NAME, json.dumps(connections))


async def resolve_connection(ctx, connection_id: str = "") -> dict | None:
    connections = await _load_connections(ctx)
    if not connections:
        return None
    if connection_id:
        for c in connections:
            if c.get("id") == connection_id:
                return c
        return None
    return connections[0]


def _connection_to_entity(c: dict) -> ProviderConnection:
    return ProviderConnection(
        id=c.get("id", ""),
        title=c.get("label") or "CircleCI account",
        connected=True,
        detail="Personal API Token connection",
    )


async def resolve_or_error(ctx, connection_id: str = ""):
    """Shared guard: resolve a connection or return the standard 'not
    connected' ActionResult.error. Returns (conn, token, error_or_None)."""
    conn = await resolve_connection(ctx, connection_id)
    if conn is None:
        return None, None, ActionResult.error(
            "No CircleCI account is connected yet. Use connect_circleci first.",
            code="CIRCLECI_ACCOUNT_MISSING",
        )
    return conn, conn.get("api_token", ""), None


@chat.function(
    "connect_circleci",
    "Connect your CircleCI account by saving your Personal API Token, after checking "
    "it actually works. Create one at app.circleci.com/settings/user/tokens. This "
    "manages pipelines, workflows, jobs, insights, contexts, schedules, webhooks, and "
    "self-hosted runners in your own CircleCI account/organizations.",
    action_type="write",
    chain_callable=True,
    data_model=ProviderConnection,
    event="circleci-connector.connect_circleci",
    effects=["circleci.provider.connected"],
)
async def connect_circleci(ctx, params: ConnectCircleciParams) -> ActionResult:
    """Connect a CircleCI account via Personal API Token."""
    token = params.api_token.strip()
    if not token:
        return ActionResult.error("Please provide your CircleCI Personal API Token.", code="CIRCLECI_MISSING_FIELD")
    check = await cc.check_connection(ctx, token)
    if not check.get("ok"):
        return ActionResult.error(check.get("error", "Could not verify this token."), code=check.get("error_code", "CIRCLECI_CONNECT_FAILED"))

    connections = await _load_connections(ctx)
    existing = next((c for c in connections if c.get("api_token") == token), None)
    if existing:
        existing.update({"label": params.label.strip() or existing.get("label", "")})
        record = existing
    else:
        record = {
            "id": str(uuid.uuid4()),
            "api_token": token,
            "label": params.label.strip(),
        }
        connections.append(record)
    await _save_connections(ctx, connections)
    return ActionResult.ok(_connection_to_entity(record))


@chat.function(
    "disconnect_circleci",
    "Disconnect a CircleCI account. Nothing in CircleCI is changed; the saved "
    "Personal API Token is deleted here.",
    action_type="write",
    chain_callable=True,
    data_model=DeleteResult,
    event="circleci-connector.disconnect_circleci",
    effects=["circleci.provider.disconnected"],
)
async def disconnect_circleci(ctx, params: DisconnectCircleciParams) -> ActionResult:
    """Disconnect one CircleCI account."""
    connections = await _load_connections(ctx)
    remaining = [c for c in connections if c.get("id") != params.connection_id]
    if len(remaining) == len(connections):
        return ActionResult.error("No such connection.", code="CIRCLECI_NOT_FOUND")
    await _save_connections(ctx, remaining)
    return ActionResult.ok(DeleteResult(id=params.connection_id, title="disconnected", deleted=True))


@chat.function(
    "list_connections",
    "List the connected CircleCI accounts.",
    action_type="read",
    chain_callable=True,
    data_model=ProviderConnectionList,
    event="circleci-connector.list_connections",
)
async def list_connections(ctx, params: NoParams) -> ActionResult:
    """List the connected CircleCI accounts."""
    connections = await _load_connections(ctx)
    return ActionResult.ok(ProviderConnectionList(
        title="CircleCI connections",
        items=[_connection_to_entity(c) for c in connections],
    ))
