"""Extension declaration, secrets, lifecycle hooks.

WHY BYOK (bring-your-own-key), SAME REASONING AS n8n Connector / MuleSoft
Connector / GitLab CI/CD Connector. CircleCI lives inside the USER'S OWN
account -- Imperal cannot and should not broker access to someone else's
CircleCI organization centrally.

WHY A SINGLE PERSONAL API TOKEN, NOT AN OAUTH ENTRY OR A MULTI-FIELD
CONNECTED-APP FORM (unlike MuleSoft/Power Automate).

CircleCI does not offer a public OAuth application flow for third-party
"connect your account" integrations the way Slack/HubSpot/Notion do. The
documented, universal way to access the REST API v2 programmatically is a
Personal API Token, created by the user at
`app.circleci.com/settings/user/tokens` (confirmed docs.circleci.com/docs/
api/v2/llms.txt, 2026-08-21, CONNECTOR_DISCOVERY.md). The connect form is
therefore a single-secret shape, closer to n8n Connector's API key than to
MuleSoft's/Power Automate's multi-field Connected App form.

WHY `Circle-Token` HEADER, NOT Bearer/Basic.

CircleCI's API accepts three auth schemes (api_key_header, bearer_auth,
basic_auth per its OpenAPI spec), but `Circle-Token` is the header used in
every single example across CircleCI's own documentation, including the
separate self-hosted Runner API (`runner.circleci.com`). Built exactly as
documented rather than assumed to be a generic Bearer token -- same
principle as GitLab CI/CD Connector's `PRIVATE-TOKEN` header choice.

WHY `base_url` IS FIXED ON `circleci.com`, UNLIKE GitLab CI/CD / n8n /
UiPath / MuleSoft / Automation Anywhere / Blue Prism CONNECTORS.

CircleCI is a pure SaaS product -- there is no self-managed/on-prem variant
of the CircleCI server itself (only self-hosted EXECUTION RUNNERS, which
still register against `runner.circleci.com`, not a customer-controlled
host). Unlike GitLab (`<instance>/api/v4` works identically for gitlab.com
and any self-managed instance), there is no host to parametrize -- the
connect form therefore has no base_url field at all, only the token plus
an optional friendly label. This is a deliberate, discovery-confirmed
difference from every other CI/CD-adjacent connector in this portfolio,
not an oversight.

WHY `write_mode="both"`, SAME REASONING AS EVERY OTHER BYOK CONNECTOR IN
THIS PORTFOLIO.

Declaring `write_mode="user"` would mean only the platform's generic
Secrets screen could write these -- leaving a first-time user with no
in-app screen explaining what a Personal API Token even is or where to
create one. `"both"` keeps the generic Secrets screen as a fallback while
letting `connect_circleci` be the friendly guided path with inline help.

WHY SCOPE IS PER-ACCOUNT, NOT APP-LEVEL, SAME AS n8n/MuleSoft/GitLab
CI/CD CONNECTOR.

A user may hold Personal API Tokens for several distinct CircleCI
accounts/organizations (e.g. personal + client work). Connections are
stored as a JSON array under one secret key, each entry carrying its own
token and an optional friendly label -- identical shape to MuleSoft
Connector's `mulesoft_connections` list / GitLab CI/CD Connector's
`gitlab_connections` list.

WHY DESTRUCTIVE ACTIONS ARE MARKED `action_type="destructive"`, SAME
PRINCIPLE AS EVERY OTHER CONNECTOR IN THIS PORTFOLIO.

Deleting a context, env var, schedule, checkout key, webhook, pipeline
definition or trigger -- or cancelling a running workflow/job, or rolling
back a project -- cannot be undone through this connector. Each such
handler declares `action_type="destructive"` so the platform's own
confirmation card gates the call, rather than trusting the model to ask
first.
"""
from __future__ import annotations

from imperal_sdk import ChatExtension, Extension

ext = Extension(
    "circleci-connector",
    version="0.1.0",
    display_name="CircleCI",
    description=(
        "Connect your own CircleCI account to manage pipelines, workflows, "
        "jobs, insights (success rate/duration/flaky tests), contexts "
        "(secrets), environment variables, schedules, checkout keys, "
        "webhooks, pipeline definitions, triggers, project settings, and "
        "self-hosted runners from Imperal -- trigger/cancel/rerun/approve "
        "pipelines and workflows, read metrics, and run bulk operations and "
        "project health audits. Uses your own Personal API Token -- "
        "nothing is hosted or proxied by Imperal beyond the request "
        "itself. Note: covers the stable REST API v2 CI/CD domain only; "
        "Policy Management (OPA), OIDC custom claims, Deploy Components, "
        "Usage export, and Organization/Groups administration are out of "
        "scope."
    ),
    icon="icon.svg",
    capabilities=[
        "circleci:read",
        "circleci:write",
    ],
    actions_explicit=True,
    system=False,
)

chat = ChatExtension(
    ext,
    tool_name="circleci",
    description=(
        "CircleCI Connector -- connect your own CircleCI account via a "
        "Personal API Token, then list/trigger/cancel/rerun pipelines and "
        "workflows, manage jobs, read Insights metrics (success rate, "
        "duration, flaky tests), manage contexts/env vars/schedules/"
        "checkout keys/webhooks/pipeline definitions/triggers, browse "
        "self-hosted runners, and run bulk operations and project health "
        "audits across many pipelines at once."
    ),
)

ext.secret(
    "circleci_connections",
    (
        "Your connected CircleCI accounts -- stored as a JSON array, one "
        "entry per account, each with its own Personal API Token and an "
        "optional friendly label. Managed through connect_circleci / "
        "disconnect_circleci -- you should not need to edit this directly."
    ),
    required=True,
    write_mode="both",
    max_bytes=65536,
    rotation_hint_days=180,
)(lambda: None)


@ext.health_check
async def health_check(ctx) -> dict:
    """Fast configuration health; no third-party call -- just confirms at
    least one connection is stored, same shape as MuleSoft Connector's /
    GitLab CI/CD Connector's health_check."""
    import json as _json
    raw = await ctx.secrets.get("circleci_connections")
    try:
        count = len(_json.loads(raw)) if raw else 0
    except Exception:
        count = 0
    return {
        "healthy": True,
        "detail": (
            f"{count} CircleCI account(s) connected." if count
            else "Not connected yet -- run connect_circleci."
        ),
    }
