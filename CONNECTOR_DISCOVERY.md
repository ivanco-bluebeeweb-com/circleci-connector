# CircleCI Connector — Connector Discovery

**Дата discovery:** 2026-08-21
**Статус:** Ярусы 1-3 пройдены (свежее чтение официальной документации
circleci.com/docs, 2026-08-21). Задача #2218 явно заявляла "делай это
приложение в максимальной комплектации с максимальным функционалом" —
это ЯВНОЕ заранее заявленное решение объёма ("максимум"), поэтому §7
(решение по объёму) не требует повторного вопроса Владу — тот же
прецедент, что GitLab CI/CD/MuleSoft/Power Automate/UiPath/Blue
Prism/Automation Anywhere коннекторы.

---

## 1. Целевой сервис и источники

CircleCI REST API v2 (`circleci.com/api/v2`) — стабильная, полностью
документированная поверхность. Прочитаны 2026-08-21:

- `circleci.com/docs/api/v2/llms.txt` — машиночитаемый полный индекс всех
  операций API v2 (использован как основной источник структуры ниже)
- `circleci.com/docs/api/v2/openapi.json` — полный OpenAPI 3.0.3 spec
- `circleci.com/docs/guides/toolkit/api-developers-guide/` — developer's guide
- `circleci.com/docs/guides/toolkit/api-intro/` — API v2 introduction
- `circleci.com/docs/guides/execution-runner/runner-api/` — self-hosted
  Runner API (отдельный хост `runner.circleci.com`)
- `circleci.com/docs/api/v3/` — существование и природа API v3 (см. п.2)
- `support.circleci.com/.../Using-Basic-Authentication-in-CircleCI-API-Calls`
  — авторизационные схемы

## 2. КРИТИЧНО: ДВЕ живые версии API — сознательный выбор v2, не v3

CircleCI одновременно обслуживает:

- **API v2** (`circleci.com/api/v2`) — зрелый, стабильный, с полным
  developer's guide, per-operation markdown-документацией на каждый
  endpoint и полным OpenAPI-spec. Официально помечен как "not
  recommended for new projects", НО это единственная версия с реальной,
  завершённой документацией на каждый ресурс.
- **API v3** (`circleci.com/api/v3`) — официально продвигается как
  "recommended" в машиночитаемом `llms.txt`, но при живом чтении
  `circleci.com/docs/api/v3/` обнаруживается: (а) собственная, НЕ
  JSON:API / НЕ HAL / НЕ problem+json схема (документация прямо
  предупреждает "do not use a standard-conformant client library"), (б)
  другая модель ресурсов — вместо связки Pipeline→Workflow→Job работает
  через "analysis" (`/api/v3/analysis/charges|jobs|tests`), "catalog",
  "deploy config suggestions", "deploy diff summaries" — это выглядит
  как ориентированный на billing/analysis/AI-config-suggestions слой, а
  НЕ полноценная замена v2 для управления пайплайнами; ресурс "Jobs"
  присутствует, но полного покрытия Pipeline/Workflow/Insights/Context/
  Project в v3 на момент discovery не обнаружено.

**Решение:** строить коннектор на **API v2** как основной, зрелой,
полностью документированной поверхности (тот же паттерн, что мы бы
выбрали для любого сервиса, где "recommended new" версия ещё не
покрывает весь функционал старой). v3 зафиксировать как "изучено,
сознательно не используется на этом заходе" — задокументировано здесь,
чтобы не путать в будущих правках.

## 3. Авторизация

Три схемы одновременно поддерживаются API v2 (`security` в OpenAPI:
`api_key_header`, `bearer_auth`, `basic_auth`, `api_key_query`):

- **`Circle-Token` header** — исторический, CircleCI-специфичный,
  используемый во ВСЕХ примерах официальной документации и в Runner API
  тоже. Personal API token создаётся на
  `app.circleci.com/settings/user/tokens`.
- **`Authorization: Bearer <token>`** — тот же токен, RFC 6750-совместимая
  подача.
- **HTTP Basic** (`support.circleci.com/.../Using-Basic-Authentication`) —
  legacy: токен как username, пустой password.

**Решение:** использовать `Circle-Token` header как основной механизм —
он используется абсолютно во всех примерах CircleCI-документации
(включая отдельный Runner API), минимизирует риск путаницы между
разными эндпоинтами. BYOK: пользователь создаёт собственный Personal
API Token в своём аккаунте (Project/Org-scoped токены существуют, но
Personal token — самый простой и универсальный путь для Яруса 1).

**НЕ self-hosted для основной платформы.** В отличие от GitLab CI/CD
(SaaS ИЛИ self-managed, единая `/api/v4`), CircleCI сам сервис — ТОЛЬКО
SaaS, хост фиксирован `https://circleci.com`. Единственная
"self-hosted" часть экосистемы — **Execution Runners** (агенты,
выполняющие job'ы на инфраструктуре клиента), у которых СВОЙ отдельный
API на хосте `runner.circleci.com` (тот же `Circle-Token`, другой base
URL). Оба хоста — фиксированные константы, не параметризуемое поле
подключения (в отличие от n8n/UiPath/MuleSoft/GitLab).

## 4. Модель ресурсов (project-slug vs project-id)

Важное отличие от других коннекторов: почти все ресурсы CircleCI v2
адресуются через **project-slug** (`{provider}/{organization}/{project}`,
например `gh/circleci/mongoose`), а НЕ через непрозрачный UUID.
Некоторые новые endpoints (`Pipeline Definition`, `Trigger`, `Rollback`,
`OIDC project-level claims`) используют **project_id** (UUID),
получаемый через `getProjectBySlug`. Insights-эндпоинты используют ещё
третий вариант адресации — `{org-slug}` для org-level summary. Коннектор
должен принимать project_slug как основной пользовательский ввод
(человекочитаемый), и внутренне резолвить project_id там, где API его
требует (`get_project` уже возвращает оба поля).

## 5. Полная карта ресурсов API v2 (по данным llms.txt/openapi.json)

### Context — секреты, шарящиеся между проектами
`GET/POST /context`, `GET/DELETE /context/{id}`,
`GET /context/{id}/environment-variable`,
`PUT/DELETE /context/{id}/environment-variable/{name}`,
`GET/POST /context/{id}/restrictions`, `DELETE .../restrictions/{id}`

### Insights — метрики успешности/длительности/flaky tests
`GET /insights/pages/{project-slug}/summary` (workflows+branches summary),
`GET /insights/time-series/{project-slug}/workflows/{name}/jobs`,
`GET /insights/{org-slug}/summary` (org-wide),
`GET /insights/{project-slug}/branches`,
`GET /insights/{project-slug}/flaky-tests`,
`GET /insights/{project-slug}/workflows`,
`GET /insights/{project-slug}/workflows/{name}` (recent runs),
`GET /insights/{project-slug}/workflows/{name}/jobs` (job metrics),
`GET /insights/{project-slug}/workflows/{name}/summary`,
`GET /insights/{project-slug}/workflows/{name}/test-metrics`

### User
`GET /me`, `GET /me/collaborations`, `GET /user/{id}`

### Pipeline — CRUD-центр домена
`GET /pipeline` (all pipelines for auth'd user, mine=false),
`POST /pipeline/continue` (continue a setup-workflow pipeline),
`GET /pipeline/{id}`, `GET /pipeline/{id}/config`,
`GET /pipeline/{id}/workflow`, `GET /pipeline/{id}/values`,
`GET /project/{slug}/pipeline`, `POST /project/{slug}/pipeline` (trigger),
`GET /project/{slug}/pipeline/mine`,
`GET /project/{slug}/pipeline/{number}`,
`POST /project/{provider}/{org}/{project}/pipeline/run` (recommended new
trigger endpoint, poддерживает pipeline definitions)

### Job
`POST /jobs/{job-id}/cancel`, `GET /jobs/{job_id}`,
`POST /project/{slug}/job/{number}/cancel`

### Workflow
`GET /workflow/{id}`, `POST /workflow/{id}/approve/{approval_request_id}`,
`POST /workflow/{id}/cancel`, `GET /workflow/{id}/job`,
`POST /workflow/{id}/rerun`

### OIDC Token Management (org/project custom claims)
`GET/PATCH/DELETE /org/{orgID}/oidc-custom-claims`,
`GET/PATCH/DELETE /org/{orgID}/project/{projectID}/oidc-custom-claims`

### Policy Management (Open Policy Agent decisions/bundles — Scale plan)
`GET/POST /owner/{id}/context/{ctx}/decision`,
`GET/PATCH /owner/{id}/context/{ctx}/decision/settings`,
`GET /owner/{id}/context/{ctx}/decision/{decisionID}`,
`GET .../decision/{decisionID}/policy-bundle`,
`GET/POST /owner/{id}/context/{ctx}/policy-bundle`,
`GET /owner/{id}/context/{ctx}/policy-bundle/{policyName}`

### Deploy (Components/Environments — Deploys feature, читающая часть)
`GET /deploy/components`, `GET /deploy/components/{id}`,
`GET /deploy/components/{id}/versions`,
`GET /deploy/environments`, `GET /deploy/environments/{id}`

### OTel (экспериментальное — помечено 🧪 в самой документации)
`GET/POST /otel/exporters`, `DELETE /otel/exporters/{id}`

### Pipeline Definition (новая модель, project_id-based)
`GET/POST /projects/{project_id}/pipeline-definitions`,
`GET/PATCH/DELETE .../pipeline-definitions/{id}`

### Project
`POST /organization/{org-slug-or-id}/project` (create),
`GET/DELETE /project/{slug}`,
`GET/POST /project/{slug}/checkout-key`,
`GET/DELETE /project/{slug}/checkout-key/{fingerprint}`,
`GET/POST /project/{slug}/envvar`,
`GET/DELETE /project/{slug}/envvar/{name}`,
`GET/PATCH /project/{provider}/{org}/{project}/settings`

### Rollback
`POST /projects/{project_id}/rollback`

### Trigger (Pipeline Definition triggers — webhook/schedule triggers v2)
`GET/POST /projects/{project_id}/pipeline-definitions/{id}/triggers`,
`GET/PATCH/DELETE /projects/{project_id}/triggers/{trigger_id}`

### Usage (org-wide usage exports — billing/FinOps)
`POST /organizations/{org_id}/usage_export_job`,
`GET .../usage_export_job/{id}`

### Webhook (outbound webhooks)
`GET/POST /webhook`, `GET/PUT/DELETE /webhook/{id}`

### Groups (org RBAC groups — Scale plan)
`GET/POST /organizations/{org_id}/groups`,
`GET/DELETE /organizations/{org_id}/groups/{id}`

### Organization
`POST /organization`, `GET/DELETE /organization/{org-slug-or-id}`,
`GET/POST /organization/{id}/url-orb-allow-list`,
`DELETE .../url-orb-allow-list/{entry-id}`

### Schedule (legacy cron schedules — pre-Pipeline-Definition-Trigger model)
`GET/POST /project/{slug}/schedule`,
`GET/PATCH/DELETE /schedule/{id}`

### Self-hosted Runner API (отдельный хост `runner.circleci.com`, тот же
`Circle-Token`, СВОЙ namespace ресурсов: resource classes, runner
tokens, individual runners) — читается через `/api/v3/runner*` на этом
отдельном хосте (не путать с основным API v2/v3 на circleci.com).

## 6. Осознанно вне охвата (Ярус 4 / не строим)

- **Policy Management** (Open Policy Agent decisions/bundles) — Scale
  plan-only feature, узкая enterprise-compliance ниша, низкая ожидаемая
  частота использования relative к сложности моделирования decision
  logs/policy bundles.
- **OTel Exporters** — сам API помечен экспериментальным (🧪) в
  официальной документации на момент discovery — не строим на
  нестабильной поверхности.
- **Deploy (Components/Environments)** — узкофункциональная,
  дополнительная feature (CircleCI Deploys), не входит в CI/CD-ядро
  (pipelines/workflows/jobs), пересекается с областью, для которой уже
  есть UiPath/Automation Anywhere/Blue Prism (RPA deploy) и
  Power Automate/n8n/Make (workflow deploy) — низкий инкрементальный ROI.
- **Groups / Organization create-delete / URL Orb allow-list** — org-level
  administration, тот же класс, что мы сознательно исключали у
  GitLab (project/group administration вне охвата) — не CI/CD-ядро.
- **Usage export jobs** — billing/FinOps отчётность, ближе к домену
  billing-приложений, не CI/CD-ядро.

## 7. Ярусы для реализации ("максимум" по прямому запросу задачи)

**Ярус 1 (ключевые функции CI/CD-цикла):**
connect/disconnect/list connections; get_project; list_pipelines,
get_pipeline, trigger_pipeline, get_pipeline_config,
list_pipeline_workflows; get_workflow, list_workflow_jobs,
cancel_workflow, rerun_workflow, approve_workflow_job; get_job,
cancel_job; list_env_vars, create_env_var, delete_env_var.

**Ярус 2 (полнота CI/CD-домена):**
list_contexts, create_context, delete_context,
list_context_env_vars, set_context_env_var, delete_context_env_var;
list_schedules, create_schedule, update_schedule, delete_schedule;
list_checkout_keys, create_checkout_key, delete_checkout_key;
list_webhooks, create_webhook, update_webhook, delete_webhook;
get_project_settings, update_project_settings; get_current_user;
list_pipeline_definitions, create/get/update/delete_pipeline_definition;
list/create/get/update/delete_trigger; rollback_project.

**Ярус 3 (Insights + value-add + Runner API + bulk):**
get_project_insights_summary, get_org_insights_summary,
list_insights_branches, get_flaky_tests, get_workflow_metrics,
get_workflow_runs, get_job_metrics, get_workflow_summary,
get_test_metrics, get_job_timeseries; list_self_hosted_runners
(runner.circleci.com); audit_project_health (value-add: агрегирует
последние N pipeline-статусов + flaky tests + insights summary в один
отчёт, тот же паттерн, что `audit_cloudhub_environment`/
`audit_org`/`audit_folder`/`audit_estate` в существующем портфеле);
bulk_cancel_workflows, bulk_rerun_workflows (bulk-операции по explicit
id-списку, тот же паттерн, что bulk_stop_cloudhub_applications и др.).

Итого ожидаемое покрытие: ~55-60 chat-функций (Ярус 1: ~18, Ярус 2:
~22, Ярус 3: ~15-18) — сопоставимо по масштабу с MuleSoft (35) и
GitLab CI/CD, с поправкой на большее число мелких ресурсов
(Context/Schedule/Checkout Key/Webhook/Pipeline Definition/Trigger).
