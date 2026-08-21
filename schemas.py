"""Pydantic params models + SDL entity contracts for CircleCI Connector.

All params models are module-scope (V17 federal invariant, same rule as
MuleSoft Connector's / GitLab CI/CD Connector's schemas.py).
"""
from __future__ import annotations

from pydantic import BaseModel, Field
from imperal_sdk import sdl


class NoParams(BaseModel):
    """Explicit empty params model -- V17 disallows untyped handlers."""
    pass


# ──────────────────────────────────────────────────────────────────────────
# Connection
# ──────────────────────────────────────────────────────────────────────────


class ConnectCircleciParams(BaseModel):
    api_token: str = Field(
        "",
        description="Your CircleCI Personal API Token, created at app.circleci.com/settings/user/tokens.",
    )
    label: str = Field("", description="Optional friendly name for this connection (e.g. 'Personal' or 'Acme Org').")


class ProviderConnection(sdl.Entity):
    id: str = ""
    title: str = ""
    connected: bool = False
    detail: str = ""


class ProviderConnectionList(sdl.Entity):
    items: list[ProviderConnection] = []


class DisconnectCircleciParams(BaseModel):
    connection_id: str = Field("", description="Id of the connection to disconnect (from list_connections).")


class DeleteResult(sdl.Entity):
    id: str = ""
    deleted: bool = False


# ──────────────────────────────────────────────────────────────────────────
# Shared scoping params
# ──────────────────────────────────────────────────────────────────────────


class _ProjectScoped(BaseModel):
    project_slug: str = Field(
        "",
        description="Project slug, e.g. 'gh/CircleCI-Public/api-preview-docs' (vcs-slug/org-name/repo-name).",
    )
    connection_id: str = Field("", description="Which connected CircleCI account to use (optional if only one is connected).")


class ListPipelinesParams(_ProjectScoped):
    branch: str = Field("", description="Filter to pipelines on this branch only.")
    page_token: str = Field("", description="Pagination token from a previous response's next_page_token.")


class Pipeline(sdl.Entity):
    id: str = ""
    number: int = 0
    project_slug: str = ""
    state: str = ""
    created_at: str = ""
    updated_at: str = ""
    trigger_type: str = ""
    trigger_actor: str = ""
    vcs_branch: str = ""
    vcs_revision: str = ""
    vcs_subject: str = ""


class PipelineList(sdl.Entity):
    items: list[Pipeline] = []
    next_page_token: str = ""


class GetPipelineParams(BaseModel):
    pipeline_id: str = Field("", description="Pipeline id (UUID), from list_pipelines.")
    connection_id: str = ""


class TriggerPipelineParams(_ProjectScoped):
    branch: str = Field("", description="Branch to run the pipeline on (mutually exclusive with tag).")
    tag: str = Field("", description="Tag to run the pipeline on (mutually exclusive with branch).")
    parameters_json: str = Field("", description="JSON object string of pipeline parameters declared in .circleci/config.yml, e.g. '{\"deploy_env\": \"staging\"}'.")


class ContinuePipelineParams(BaseModel):
    continuation_key: str = Field("", description="The continuation key returned to a setup workflow that called the config/continue API.")
    configuration: str = Field("", description="The actual YAML configuration string to continue the pipeline with.")
    parameters_json: str = Field("", description="Optional JSON object string of additional pipeline parameters.")
    connection_id: str = ""


class GetPipelineConfigParams(BaseModel):
    pipeline_id: str = ""
    connection_id: str = ""


class PipelineConfig(sdl.Entity):
    source: str = ""
    compiled: str = ""


class ListPipelineWorkflowsParams(BaseModel):
    pipeline_id: str = ""
    connection_id: str = ""
    page_token: str = ""


class Workflow(sdl.Entity):
    id: str = ""
    name: str = ""
    status: str = ""
    pipeline_id: str = ""
    pipeline_number: int = 0
    project_slug: str = ""
    created_at: str = ""
    stopped_at: str = ""
    started_by: str = ""
    tag: str = ""


class WorkflowList(sdl.Entity):
    items: list[Workflow] = []
    next_page_token: str = ""


class GetWorkflowParams(BaseModel):
    workflow_id: str = Field("", description="Workflow id (UUID), from list_pipeline_workflows.")
    connection_id: str = ""


class WorkflowActionParams(BaseModel):
    workflow_id: str = ""
    connection_id: str = ""


class WorkflowActionResult(sdl.Entity):
    workflow_id: str = ""
    action: str = ""
    ok: bool = False


class ListWorkflowJobsParams(BaseModel):
    workflow_id: str = ""
    connection_id: str = ""


class Job(sdl.Entity):
    id: str = ""
    number: int = 0
    name: str = ""
    status: str = ""
    type: str = ""
    started_at: str = ""
    stopped_at: str = ""
    approval_request_id: str = ""


class JobList(sdl.Entity):
    items: list[Job] = []


class ApproveJobParams(BaseModel):
    workflow_id: str = ""
    approval_request_id: str = Field("", description="Id of the pending approval job (approval_request_id from list_workflow_jobs).")
    connection_id: str = ""


class GetJobParams(_ProjectScoped):
    job_number: int = Field(0, description="Numeric job number within the project, from list_workflow_jobs.")


class CancelJobParams(_ProjectScoped):
    job_number: int = 0


class JobActionResult(sdl.Entity):
    job_number: int = 0
    action: str = ""
    ok: bool = False


class ListJobArtifactsParams(_ProjectScoped):
    job_number: int = 0
    page_token: str = ""


class JobArtifact(sdl.Entity):
    path: str = ""
    url: str = ""
    node_index: int = 0


class JobArtifactList(sdl.Entity):
    items: list[JobArtifact] = []
    next_page_token: str = ""


class ListJobTestsParams(_ProjectScoped):
    job_number: int = 0
    page_token: str = ""


class JobTestResult(sdl.Entity):
    name: str = ""
    classname: str = ""
    result: str = ""
    message: str = ""
    run_time: float = 0.0
    file: str = ""


class JobTestResultList(sdl.Entity):
    items: list[JobTestResult] = []
    next_page_token: str = ""


# ──────────────────────────────────────────────────────────────────────────
# Insights
# ──────────────────────────────────────────────────────────────────────────


class GetProjectInsightsParams(_ProjectScoped):
    workflow_name: str = Field("", description="Name of the workflow to read insights for, e.g. 'build-test-deploy'.")
    branch: str = Field("", description="Filter to a specific branch.")
    reporting_window: str = Field("last-90-days", description="One of: last-24-hours, last-7-days, last-30-days, last-60-days, last-90-days.")


class InsightsMetricsSummary(sdl.Entity):
    success_rate: float = 0.0
    total_runs: int = 0
    failed_runs: int = 0
    successful_runs: int = 0
    duration_median_secs: int = 0
    duration_p95_secs: int = 0
    credits_used: int = 0


class GetWorkflowJobInsightsParams(_ProjectScoped):
    workflow_name: str = ""
    branch: str = ""


class JobInsightsRow(sdl.Entity):
    name: str = ""
    success_rate: float = 0.0
    total_runs: int = 0
    duration_median_secs: int = 0


class JobInsightsList(sdl.Entity):
    items: list[JobInsightsRow] = []


class GetFlakyTestsParams(_ProjectScoped):
    pass


class FlakyTest(sdl.Entity):
    test_name: str = ""
    job_name: str = ""
    times_flaked: int = 0
    source: str = ""
    file: str = ""


class FlakyTestList(sdl.Entity):
    items: list[FlakyTest] = []


class GetOrgInsightsSummaryParams(BaseModel):
    org_slug: str = Field("", description="Organization slug, e.g. 'gh/CircleCI-Public'.")
    reporting_window: str = "last-90-days"
    connection_id: str = ""


# ──────────────────────────────────────────────────────────────────────────
# Context (secrets)
# ──────────────────────────────────────────────────────────────────────────


class ListContextsParams(BaseModel):
    owner_slug: str = Field("", description="Owner (organization) slug, e.g. 'gh/CircleCI-Public'.")
    connection_id: str = ""
    page_token: str = ""


class Context(sdl.Entity):
    id: str = ""
    name: str = ""
    created_at: str = ""


class ContextList(sdl.Entity):
    items: list[Context] = []
    next_page_token: str = ""


class CreateContextParams(BaseModel):
    name: str = Field("", description="Name for the new context.")
    owner_slug: str = Field("", description="Owner (organization) slug this context belongs to.")
    connection_id: str = ""


class GetContextParams(BaseModel):
    context_id: str = ""
    connection_id: str = ""


class DeleteContextParams(BaseModel):
    context_id: str = ""
    connection_id: str = ""


class ListContextEnvVarsParams(BaseModel):
    context_id: str = ""
    connection_id: str = ""
    page_token: str = ""


class ContextEnvVar(sdl.Entity):
    variable: str = ""
    created_at: str = ""
    context_id: str = ""


class ContextEnvVarList(sdl.Entity):
    items: list[ContextEnvVar] = []
    next_page_token: str = ""


class SetContextEnvVarParams(BaseModel):
    context_id: str = ""
    variable_name: str = Field("", description="Name of the environment variable, e.g. 'DEPLOY_TOKEN'.")
    value: str = Field("", description="Secret value to store. Never echoed back by CircleCI once set.")
    connection_id: str = ""


class RemoveContextEnvVarParams(BaseModel):
    context_id: str = ""
    variable_name: str = ""
    connection_id: str = ""


# ──────────────────────────────────────────────────────────────────────────
# Project env vars + checkout keys
# ──────────────────────────────────────────────────────────────────────────


class ListProjectEnvVarsParams(_ProjectScoped):
    page_token: str = ""


class ProjectEnvVar(sdl.Entity):
    name: str = ""
    value: str = ""  # CircleCI masks this itself (returns partially redacted)


class ProjectEnvVarList(sdl.Entity):
    items: list[ProjectEnvVar] = []
    next_page_token: str = ""


class CreateProjectEnvVarParams(_ProjectScoped):
    name: str = Field("", description="Environment variable name, e.g. 'API_KEY'.")
    value: str = Field("", description="Value to store.")


class DeleteProjectEnvVarParams(_ProjectScoped):
    name: str = ""


class ListCheckoutKeysParams(_ProjectScoped):
    pass


class CheckoutKey(sdl.Entity):
    fingerprint: str = ""
    type: str = ""
    preferred: bool = False
    created_at: str = ""
    public_key: str = ""


class CheckoutKeyList(sdl.Entity):
    items: list[CheckoutKey] = []


class CreateCheckoutKeyParams(_ProjectScoped):
    key_type: str = Field("deploy-key", description="One of: deploy-key, github-user-key.")


class DeleteCheckoutKeyParams(_ProjectScoped):
    fingerprint: str = Field("", description="Fingerprint of the checkout key to delete, from list_checkout_keys.")


# ──────────────────────────────────────────────────────────────────────────
# Project / schedules / webhooks / pipeline definitions / triggers
# ──────────────────────────────────────────────────────────────────────────


class GetProjectParams(_ProjectScoped):
    pass


class Project(sdl.Entity):
    slug: str = ""
    name: str = ""
    id: str = ""
    organization_name: str = ""
    organization_slug: str = ""
    vcs_type: str = ""
    default_branch: str = ""


class ListSchedulesParams(_ProjectScoped):
    page_token: str = ""


class Schedule(sdl.Entity):
    id: str = ""
    name: str = ""
    description: str = ""
    timetable_per_hour: int = 0
    timetable_hours_of_day: str = ""
    timetable_days_of_week: str = ""
    actor_name: str = ""
    updated_at: str = ""


class ScheduleList(sdl.Entity):
    items: list[Schedule] = []
    next_page_token: str = ""


class CreateScheduleParams(_ProjectScoped):
    name: str = Field("", description="Name for the new schedule.")
    description: str = Field("", description="Description of the schedule.")
    per_hour: int = Field(1, description="How many times per hour the schedule should trigger (1-59).")
    hours_of_day_json: str = Field("[0]", description="JSON array of hours (0-23) the schedule may trigger in, e.g. '[0, 12]'.")
    days_of_week_json: str = Field(
        '["MON","TUE","WED","THU","FRI"]',
        description="JSON array of days, from MON/TUE/WED/THU/FRI/SAT/SUN.",
    )
    branch: str = Field("main", description="Branch the scheduled pipeline should run on.")
    parameters_json: str = Field("{}", description="JSON object string of pipeline parameters to pass on each scheduled run.")


class UpdateScheduleParams(BaseModel):
    schedule_id: str = ""
    connection_id: str = ""
    name: str = Field("", description="New name (leave empty to keep unchanged).")
    description: str = Field("", description="New description (leave empty to keep unchanged).")
    per_hour: int = Field(0, description="New per-hour trigger count (0 = keep unchanged).")
    hours_of_day_json: str = Field("", description="New JSON array of hours (empty = keep unchanged).")
    days_of_week_json: str = Field("", description="New JSON array of days (empty = keep unchanged).")


class DeleteScheduleParams(BaseModel):
    schedule_id: str = ""
    connection_id: str = ""


class ListWebhooksParams(BaseModel):
    scope_id: str = Field("", description="Id of the project or organization this webhook is scoped to.")
    scope_type: str = Field("project", description="One of: project, organization.")
    connection_id: str = ""


class Webhook(sdl.Entity):
    id: str = ""
    name: str = ""
    url: str = ""
    events: list[str] = []
    verify_tls: bool = True
    signing_secret_set: bool = False


class WebhookList(sdl.Entity):
    items: list[Webhook] = []


class CreateWebhookParams(BaseModel):
    name: str = Field("", description="Friendly name for the webhook.")
    url: str = Field("", description="HTTPS endpoint CircleCI will POST events to.")
    events_json: str = Field(
        '["workflow-completed"]',
        description="JSON array of events to subscribe to: workflow-completed, job-completed.",
    )
    scope_id: str = Field("", description="Id of the project or organization this webhook is scoped to.")
    scope_type: str = Field("project", description="One of: project, organization.")
    signing_secret: str = Field("", description="Optional secret used to sign the X-CircleCI-Signature header on deliveries.")
    connection_id: str = ""


class UpdateWebhookParams(BaseModel):
    webhook_id: str = ""
    connection_id: str = ""
    name: str = Field("", description="New name (leave empty to keep unchanged).")
    url: str = Field("", description="New delivery URL (leave empty to keep unchanged).")
    events_json: str = Field("", description="New JSON array of events (empty = keep unchanged).")
    signing_secret: str = Field("", description="New signing secret (leave empty to keep unchanged).")


class DeleteWebhookParams(BaseModel):
    webhook_id: str = ""
    connection_id: str = ""


class ListPipelineDefinitionsParams(_ProjectScoped):
    page_token: str = ""


class PipelineDefinition(sdl.Entity):
    id: str = ""
    name: str = ""
    config_source_provider: str = ""
    config_source_file_path: str = ""
    checkout_source_provider: str = ""


class PipelineDefinitionList(sdl.Entity):
    items: list[PipelineDefinition] = []
    next_page_token: str = ""


class ListTriggersParams(BaseModel):
    project_id: str = Field("", description="Project id (UUID) -- distinct from project_slug, from get_project.")
    connection_id: str = ""
    page_token: str = ""


class Trigger(sdl.Entity):
    id: str = ""
    name: str = ""
    event_source_type: str = ""
    event_source_webhook_url: str = ""
    config_source_provider: str = ""


class TriggerList(sdl.Entity):
    items: list[Trigger] = []
    next_page_token: str = ""


class DeleteTriggerParams(BaseModel):
    project_id: str = ""
    trigger_id: str = ""
    connection_id: str = ""


# ──────────────────────────────────────────────────────────────────────────
# User / Collaborations
# ──────────────────────────────────────────────────────────────────────────


class CircleciUser(sdl.Entity):
    id: str = ""
    login: str = ""
    name: str = ""


class Collaboration(sdl.Entity):
    id: str = ""
    slug: str = ""
    name: str = ""
    vcs_type: str = ""


class CollaborationList(sdl.Entity):
    items: list[Collaboration] = []


# ──────────────────────────────────────────────────────────────────────────
# Self-hosted Runners (runner.circleci.com/api/v3)
# ──────────────────────────────────────────────────────────────────────────


class ListRunnersParams(BaseModel):
    resource_class: str = Field("", description="Filter runners by resource class, e.g. 'my-namespace/my-resource-class'.")
    namespace: str = Field("", description="Filter runners by namespace (mutually exclusive with resource_class).")
    connection_id: str = ""


class Runner(sdl.Entity):
    id: str = ""
    hostname: str = ""
    name: str = ""
    version: str = ""
    first_connected: str = ""
    last_connected: str = ""
    last_used: str = ""


class RunnerList(sdl.Entity):
    items: list[Runner] = []


class ListRunnerResourceClassesParams(BaseModel):
    namespace: str = Field("", description="Namespace to list resource classes for, e.g. 'my-namespace'.")
    connection_id: str = ""


class RunnerResourceClass(sdl.Entity):
    id: str = ""
    resource_class: str = ""
    description: str = ""


class RunnerResourceClassList(sdl.Entity):
    items: list[RunnerResourceClass] = []


class CreateRunnerResourceClassParams(BaseModel):
    resource_class: str = Field("", description="Full resource class name, e.g. 'my-namespace/my-resource-class'.")
    description: str = Field("", description="Human-readable description of this resource class.")
    connection_id: str = ""


class DeleteRunnerResourceClassParams(BaseModel):
    resource_class_id: str = ""
    connection_id: str = ""


class CreateRunnerTokenParams(BaseModel):
    resource_class: str = Field("", description="Resource class this auth token grants runners access to.")
    nickname: str = Field("", description="Friendly name for this token.")
    connection_id: str = ""


class RunnerToken(sdl.Entity):
    id: str = ""
    token: str = ""  # only ever returned once, at creation
    nickname: str = ""
    resource_class: str = ""


class ListRunnerTokensParams(BaseModel):
    resource_class: str = Field("", description="Resource class to list tokens for.")
    connection_id: str = ""


class RunnerTokenSummary(sdl.Entity):
    id: str = ""
    nickname: str = ""
    resource_class: str = ""
    created_at: str = ""


class RunnerTokenList(sdl.Entity):
    items: list[RunnerTokenSummary] = []


class DeleteRunnerTokenParams(BaseModel):
    token_id: str = ""
    connection_id: str = ""


# ──────────────────────────────────────────────────────────────────────────
# Bulk operations + audit (Ярус 3 value-add)
# ──────────────────────────────────────────────────────────────────────────


class BulkPipelinesParams(BaseModel):
    pipeline_ids_json: str = Field("[]", description="JSON array of pipeline ids to act on.")
    connection_id: str = ""


class BulkResultItem(sdl.Entity):
    id: str = ""
    ok: bool = False
    detail: str = ""


class BulkResult(sdl.Entity):
    items: list[BulkResultItem] = []
    succeeded: int = 0
    failed: int = 0


class AuditProjectHealthParams(_ProjectScoped):
    workflow_name: str = Field("", description="Workflow to audit, e.g. 'build-test-deploy'.")


class ProjectHealthReport(sdl.Entity):
    project_slug: str = ""
    workflow_name: str = ""
    success_rate: float = 0.0
    recent_failed_runs: int = 0
    flaky_test_count: int = 0
    median_duration_secs: int = 0
    p95_duration_secs: int = 0
    stale_pipeline_definitions: int = 0
    notes: list[str] = []
