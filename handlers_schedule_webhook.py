"""Schedule + Webhook chat functions for CircleCI Connector.
Built on circleci_client.py / schemas.py.
"""
from __future__ import annotations

import json

from imperal_sdk import ActionResult

import circleci_client as cc
from app import ext, chat
from handlers_connection import resolve_or_error
from schemas import (
    ListSchedulesParams, Schedule, ScheduleList,
    CreateScheduleParams, UpdateScheduleParams, DeleteScheduleParams, DeleteResult,
    ListWebhooksParams, Webhook, WebhookList,
    CreateWebhookParams, UpdateWebhookParams, DeleteWebhookParams,
)


def _schedule_from(s: dict) -> Schedule:
    timetable = s.get("timetable") or {}
    return Schedule(
        id=s.get("id", ""), name=s.get("name", ""), description=s.get("description", ""),
        timetable_per_hour=timetable.get("per-hour", 0),
        timetable_hours_of_day=json.dumps(timetable.get("hours-of-day", [])),
        timetable_days_of_week=json.dumps(timetable.get("days-of-week", [])),
        actor_name=(s.get("actor") or {}).get("name", ""),
        updated_at=s.get("updated-at", ""),
    )


@chat.function(
    "list_schedules",
    "List scheduled pipeline triggers configured on a CircleCI project.",
    action_type="read",
    chain_callable=True,
    data_model=ScheduleList,
    event="circleci-connector.list_schedules",
)
async def list_schedules(ctx, params: ListSchedulesParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        resp = await cc.list_project_schedules(ctx, token, params.project_slug, params.page_token)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_SCHEDULES_LIST_FAILED")
    items = resp.get("items", []) if isinstance(resp, dict) else []
    return ActionResult.ok(ScheduleList(
        items=[_schedule_from(s) for s in items],
        next_page_token=resp.get("next_page_token", "") if isinstance(resp, dict) else "",
    ))


@chat.function(
    "create_schedule",
    "Create a new scheduled pipeline trigger on a CircleCI project -- runs automatically on the given "
    "days/hours/frequency.",
    action_type="write",
    chain_callable=True,
    data_model=Schedule,
    event="circleci-connector.create_schedule",
    effects=["circleci.schedule.created"],
)
async def create_schedule(ctx, params: CreateScheduleParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    if not params.name.strip():
        return ActionResult.error("name is required.", code="CIRCLECI_MISSING_NAME")
    try:
        hours = json.loads(params.hours_of_day_json or "[0]")
        days = json.loads(params.days_of_week_json or '["MON","TUE","WED","THU","FRI"]')
        parameters = json.loads(params.parameters_json or "{}")
    except (TypeError, ValueError):
        return ActionResult.error("hours_of_day_json/days_of_week_json/parameters_json must be valid JSON.", code="CIRCLECI_INVALID_JSON")
    parameters.setdefault("branch", params.branch or "main")
    timetable = {"per-hour": params.per_hour, "hours-of-day": hours, "days-of-week": days}
    try:
        s = await cc.create_schedule(ctx, token, params.project_slug, params.name.strip(), params.description, timetable, "current", parameters)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_SCHEDULE_CREATE_FAILED")
    return ActionResult.ok(_schedule_from(s))


@chat.function(
    "update_schedule",
    "Update an existing CircleCI schedule's name, description, or timetable. Only given fields change.",
    action_type="write",
    chain_callable=True,
    data_model=Schedule,
    event="circleci-connector.update_schedule",
    effects=["circleci.schedule.updated"],
)
async def update_schedule(ctx, params: UpdateScheduleParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    fields: dict = {}
    if params.name.strip():
        fields["name"] = params.name.strip()
    if params.description.strip():
        fields["description"] = params.description.strip()
    timetable: dict = {}
    if params.per_hour:
        timetable["per-hour"] = params.per_hour
    if params.hours_of_day_json.strip():
        try:
            timetable["hours-of-day"] = json.loads(params.hours_of_day_json)
        except (TypeError, ValueError):
            return ActionResult.error("hours_of_day_json must be valid JSON.", code="CIRCLECI_INVALID_JSON")
    if params.days_of_week_json.strip():
        try:
            timetable["days-of-week"] = json.loads(params.days_of_week_json)
        except (TypeError, ValueError):
            return ActionResult.error("days_of_week_json must be valid JSON.", code="CIRCLECI_INVALID_JSON")
    if timetable:
        fields["timetable"] = timetable
    try:
        s = await cc.update_schedule(ctx, token, params.schedule_id, **fields)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_SCHEDULE_UPDATE_FAILED")
    return ActionResult.ok(_schedule_from(s))


@chat.function(
    "delete_schedule",
    "Permanently delete a CircleCI scheduled pipeline trigger. Cannot be undone.",
    action_type="destructive",
    chain_callable=True,
    data_model=DeleteResult,
    event="circleci-connector.delete_schedule",
    effects=["circleci.schedule.deleted"],
)
async def delete_schedule(ctx, params: DeleteScheduleParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        await cc.delete_schedule(ctx, token, params.schedule_id)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_SCHEDULE_DELETE_FAILED")
    return ActionResult.ok(DeleteResult(id=params.schedule_id, deleted=True))


def _webhook_from(w: dict) -> Webhook:
    return Webhook(
        id=w.get("id", ""), name=w.get("name", ""), url=w.get("url", ""),
        events=w.get("events", []), verify_tls=w.get("verify-tls", True),
        signing_secret_set=bool(w.get("signing-secret")),
    )


@chat.function(
    "list_webhooks",
    "List webhook subscriptions configured on a CircleCI project or organization.",
    action_type="read",
    chain_callable=True,
    data_model=WebhookList,
    event="circleci-connector.list_webhooks",
)
async def list_webhooks(ctx, params: ListWebhooksParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    if not params.scope_id.strip():
        return ActionResult.error("scope_id is required.", code="CIRCLECI_MISSING_SCOPE_ID")
    try:
        resp = await cc.list_webhooks(ctx, token, params.scope_id.strip(), params.scope_type)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_WEBHOOKS_LIST_FAILED")
    items = resp.get("items", []) if isinstance(resp, dict) else []
    return ActionResult.ok(WebhookList(items=[_webhook_from(w) for w in items]))


@chat.function(
    "create_webhook",
    "Subscribe to a CircleCI event (workflow-completed, job-completed) -- CircleCI will POST to your URL "
    "as things happen.",
    action_type="write",
    chain_callable=True,
    data_model=Webhook,
    event="circleci-connector.create_webhook",
    effects=["circleci.webhook.created"],
)
async def create_webhook(ctx, params: CreateWebhookParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    if not params.name.strip() or not params.url.strip() or not params.scope_id.strip():
        return ActionResult.error("name, url and scope_id are all required.", code="CIRCLECI_MISSING_FIELDS")
    try:
        events = json.loads(params.events_json or '["workflow-completed"]')
    except (TypeError, ValueError):
        return ActionResult.error("events_json must be a valid JSON array.", code="CIRCLECI_INVALID_JSON")
    try:
        w = await cc.create_webhook(
            ctx, token, params.name.strip(), events, params.url.strip(), True,
            params.signing_secret, params.scope_id.strip(), params.scope_type,
        )
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_WEBHOOK_CREATE_FAILED")
    return ActionResult.ok(_webhook_from(w))


@chat.function(
    "update_webhook",
    "Update an existing CircleCI webhook's name, URL, events, or signing secret. Only given fields change.",
    action_type="write",
    chain_callable=True,
    data_model=Webhook,
    event="circleci-connector.update_webhook",
    effects=["circleci.webhook.updated"],
)
async def update_webhook(ctx, params: UpdateWebhookParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    fields: dict = {}
    if params.name.strip():
        fields["name"] = params.name.strip()
    if params.url.strip():
        fields["url"] = params.url.strip()
    if params.events_json.strip():
        try:
            fields["events"] = json.loads(params.events_json)
        except (TypeError, ValueError):
            return ActionResult.error("events_json must be valid JSON.", code="CIRCLECI_INVALID_JSON")
    if params.signing_secret.strip():
        fields["signing_secret"] = params.signing_secret.strip()
    try:
        w = await cc.update_webhook(ctx, token, params.webhook_id, **fields)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_WEBHOOK_UPDATE_FAILED")
    return ActionResult.ok(_webhook_from(w))


@chat.function(
    "delete_webhook",
    "Permanently remove a CircleCI webhook subscription. Cannot be undone.",
    action_type="destructive",
    chain_callable=True,
    data_model=DeleteResult,
    event="circleci-connector.delete_webhook",
    effects=["circleci.webhook.deleted"],
)
async def delete_webhook(ctx, params: DeleteWebhookParams) -> ActionResult:
    conn, token, err = await resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        await cc.delete_webhook(ctx, token, params.webhook_id)
    except cc.ClientFail as e:
        return ActionResult.error(e.message, code="CIRCLECI_WEBHOOK_DELETE_FAILED")
    return ActionResult.ok(DeleteResult(id=params.webhook_id, deleted=True))
