"""Panel UI -- connections list/connect form + recent pipelines list.

SIDEBAR CONTENT -- NO CARDS ANYWHERE, per ~/UI_INTERFACE_STANDARD.md's
"left sidebar, no decorated cards" rule (same convention as MuleSoft
Connector's / Power Automate Connector's panels.py).

Every section (connections, connect form, pipelines) is a plain ui.Stack,
content stacked vertically and left-aligned, sections separated by
ui.Divider() -- no Card border/background/shadow anywhere in this slot.
Disconnect lives only in the "App settings" screen (panels_settings.py).
The one secondary "App settings" button is always the LAST element at the
bottom of the sidebar.

WHY A SINGLE-TOKEN FORM, NOT A MULTI-FIELD CONNECTED-APP FORM (unlike
MuleSoft/Power Automate) -- see app.py's module docstring for the full
architectural reasoning: CircleCI's own documented auth mechanism is one
Personal API Token, no OAuth application, no org/environment ids to
collect.

PER ~/UI_INTERFACE_STANDARD.md (2026-08-21 addendum): every Input carries
its own visible label (never placeholder-only), the placeholder text is
always contextually specific to what's being entered (never a generic
"Enter value"), the form's own container is stretched to the full width
of the left sidebar, and the form's inner content is stretched to fill
that container. The "How do I set this up?" instruction lives ONLY in
the help modal (mulesoft_connect_help-equivalent below) -- it is not
duplicated as static sidebar text.
"""
from __future__ import annotations

from imperal_sdk import ui

import circleci_client as cc
from app import ext
import handlers_connection as h


def _settings_button() -> ui.UINode:
    """The one required secondary entry point into the settings screen --
    always the last element at the bottom of the sidebar."""
    return ui.Button(
        "App settings", variant="secondary", size="sm", full_width=True,
        icon="settings", on_click=ui.Call("__panel__circleci_settings"),
    )


def _connection_row(c: dict) -> ui.UINode:
    label = c.get("label") or "CircleCI account"
    return ui.Stack(direction="v", gap=1, children=[
        ui.Text(label, variant="body"),
        ui.Text("Personal API Token connection", variant="caption"),
    ])


def _connections_section(connections: list[dict]) -> ui.UINode:
    if not connections:
        return ui.Text("No CircleCI accounts connected yet.", variant="caption")
    children: list[ui.UINode] = []
    for i, c in enumerate(connections):
        if i > 0:
            children.append(ui.Divider())
        children.append(_connection_row(c))
    return ui.Stack(direction="v", gap=2, children=children)


def _connect_section() -> ui.UINode:
    """Form container stretched to the FULL WIDTH of the left sidebar, its
    inner content stretched to fill it (align="stretch" on both the outer
    Stack and the Form's own children Stack). No intro heading/description
    text here -- the token walkthrough lives ONLY in circleci_connect_help's
    modal (button below opens it); repeating it here would duplicate that
    instruction."""
    return ui.Stack(direction="v", gap=3, align="stretch", children=[
        ui.Button("How do I set this up?", variant="ghost", size="sm",
                  icon="HelpCircle",
                  on_click=ui.Call("__panel__circleci_connect_help")),
        ui.Form(
            action="connect_circleci",
            submit_label="Verify and connect",
            children=[
                ui.Stack(direction="v", gap=1, align="stretch", children=[
                    ui.Text("Personal API Token", variant="caption"),
                    ui.Password(param_name="api_token",
                                placeholder="Paste your CircleCI Personal API Token"),
                ]),
                ui.Stack(direction="v", gap=1, align="stretch", children=[
                    ui.Text("Label (optional)", variant="caption"),
                    ui.Input(param_name="label", placeholder="e.g. Personal or Acme Org"),
                ]),
            ],
        ),
    ])


@ext.panel("circleci_connect", slot="left", title="CircleCI", icon="🔄",
           default_width=320, min_width=260, max_width=420)
async def circleci_connect_panel(ctx, **kwargs) -> object:
    connections = await h._load_connections(ctx)
    connected = bool(connections)

    header = ui.Header(text="CircleCI", level=2,
                        subtitle="Manage your CircleCI pipelines, workflows and jobs from Imperal")

    if not connected:
        return ui.Stack(direction="v", gap=4, align="stretch", children=[
            header,
            _connect_section(),
            ui.Divider(),
            _settings_button(),
        ])

    return ui.Stack(direction="v", gap=4, align="stretch", children=[
        header,
        ui.Text("Connected accounts", variant="subtitle"),
        _connections_section(connections),
        ui.Divider(),
        _connect_section(),
        ui.Divider(),
        _settings_button(),
    ])


@ext.panel("circleci_connect_help", slot="center",
           title="How to connect CircleCI", center_overlay=True)
async def circleci_connect_help(ctx, **kwargs) -> object:
    content = ui.Stack(direction="v", gap=3, children=[
        ui.Text("1. Go to app.circleci.com/settings/user/tokens (you must be logged into CircleCI)."),
        ui.Text("2. Click \"Create New Token\", give it a name you'll recognize, and create it."),
        ui.Text("3. Copy the token immediately -- CircleCI only shows it once."),
        ui.Text("4. Paste it into the form here and connect."),
        ui.Divider(),
        ui.Alert(
            title="Stable REST API v2 CI/CD domain only",
            message=(
                "This manages pipelines, workflows, jobs, insights, contexts, "
                "env vars, schedules, checkout keys, webhooks, pipeline "
                "definitions, triggers, and self-hosted runners. Policy "
                "Management (OPA), OIDC custom claims, Deploy Components, "
                "Usage export, and Organization/Groups administration are "
                "out of scope."
            ),
            type="warning",
        ),
        ui.Divider(),
        ui.Link(
            label="Open CircleCI's official Personal API Tokens guide",
            href="https://circleci.com/docs/managing-api-tokens/",
        ),
    ])
    return ui.Dialog(
        title="How to connect CircleCI",
        content=content,
        confirm_label="",
        cancel_label="Close",
    )


@ext.panel("circleci_center", slot="center", title="CircleCI", icon="🔄", center_overlay=True)
async def circleci_center_panel(ctx, **kwargs) -> object:
    """Base center panel -- per UI_INTERFACE_STANDARD.md (2026-08-20).
    This app has no list/detail content of its own to show in the center
    by default (everything lives in the sidebar). MUST carry
    center_overlay=True: per docs.imperal.io/en/concepts/panels, a plain
    slot="center" panel is registered but the Panel app never fetches it
    at session-init without that flag. Text is the shared canonical
    wording -- must stay identical across every app in this situation."""
    return ui.Empty(
        message="Nothing to show here -- this app is managed entirely from the sidebar.",
        icon="👈",
    )
