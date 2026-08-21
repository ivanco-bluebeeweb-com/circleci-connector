# CircleCI Connector — Preparation

**Статус:** Фаза 1 (Discovery + архитектурные решения) завершена. Объём
релиза заявлен пользователем явно в исходном запросе задачи #2218 —
"делай это приложение в максимальной комплектации с максимальным
функционалом" — трактуется как "максимум" (Ярус 1+2+3), по прецеденту
GitLab CI/CD/Power Automate/MuleSoft/Automation Anywhere/UiPath/Blue
Prism, где такая же явная формулировка в задаче уже освобождала от
повторного вопроса.

**Владелец продукта:** vlad@bluebeeweb.com
**Дата подготовки:** 2026-08-21, v0.1
**Vikunja task:** #2218 (BBW Imperal Apps), [App Development].

**Почему сейчас:** CircleCI — один из старейших и наиболее устоявшихся
SaaS-first CI/CD-провайдеров, сильные позиции в стартап/scale-up
сегменте и developer-first аудитории; закрывает нишу клиентов Imperal,
использующих CircleCI вместо/наряду с GitHub Actions/GitLab CI
(последний уже в портфеле).

---

## 1. Паспорт приложения

**Название в Marketplace (display_name): «CircleCI»**. Внутренний
app_id/папка: `circleci-connector`.

**CircleCI Connector** — коннектор к CircleCI REST API v2
(`circleci.com/api/v2`), покрывающий весь CI/CD-домен: pipelines,
workflows, jobs, insights (метрики успешности/длительности/flaky
tests), contexts (секреты), env vars, schedules, checkout keys,
webhooks, pipeline definitions, triggers, project settings,
self-hosted runners. BYOK: пользователь подключает свой собственный
Personal API Token к своему собственному CircleCI-аккаунту/организации.
Imperal ничего не хостит и не проксирует помимо самого запроса.

**Сознательно вне охвата:** API v3 (см. CONNECTOR_DISCOVERY.md §2 —
незрелая, billing/analysis-ориентированная поверхность на момент
discovery, НЕ полноценная замена v2 для управления пайплайнами);
Policy Management API (OPA-политики для enterprise self-hosted
установок — узкая enterprise-компилянс ниша, не Ярус 1-3); OIDC Token
Management (управление custom claims для OIDC — узкий security-домен);
Deploy Components/Environments (CircleCI Deploy — отдельный продукт для
deployment orchestration, не CI/CD ядро); Usage export jobs
(billing/FinOps отчётность); Organization/Groups CRUD (административное
управление организацией/RBAC-группами — не CI/CD-функционал, риск
случайного создания/удаления целой организации).

## 2. Архитектурное решение: BYOK, единый Personal API Token

**WHY BYOK**, та же логика, что n8n/MuleSoft/Power Automate/GitLab
CI/CD Connector. CircleCI-аккаунт живёт в аккаунте ПОЛЬЗОВАТЕЛЯ —
Imperal не может и не должен централизованно брокерить доступ к чужому
CircleCI.

**WHY ОДИН ТОКЕН (Personal API Token), НЕ OAuth-приложение.**

CircleCI не предоставляет публичного OAuth-приложения для
сторонних интеграций уровня "connect your account" (в отличие от
Slack/HubSpot/Notion) — стандартный путь для программного доступа это
Personal API Token, создаваемый пользователем на
`app.circleci.com/settings/user/tokens` (подтверждено
CONNECTOR_DISCOVERY.md §1, `docs/api/v2/llms.txt`). Форма подключения
поэтому проще, чем у MuleSoft/Power Automate (не нужен
client_id/client_secret/org_id/env_id) — только сам токен плюс
опциональный label. Это ближе по форме к n8n Connector (единый
API-ключ).

**WHY `Circle-Token` HEADER, НЕ Bearer/Basic.**

Три схемы поддерживаются одновременно (CONNECTOR_DISCOVERY.md §3), но
`Circle-Token` используется во АБСОЛЮТНО ВСЕХ примерах официальной
документации CircleCI, включая отдельный Runner API — минимизирует
риск разойтись с реальным поведением сервиса. Реализовано как
константа в HTTP-клиенте, не настраиваемая пользователем.

**WHY `base_url` ФИКСИРОВАН НА `circleci.com`, В ОТЛИЧИЕ ОТ GitLab
CI/CD/n8n/UiPath/MuleSoft/Automation Anywhere/Blue Prism.**

В отличие от всех self-hosted-совместимых коннекторов портфеля,
CircleCI НЕ предлагает self-hosted вариант основной платформы — только
self-hosted EXECUTION RUNNERS (агенты, поднимаемые в инфраструктуре
пользователя, но управляемые через `runner.circleci.com`, тот же
центральный SaaS). Поэтому `base_url` НЕ параметризуется — коннектор
всегда обращается к `https://circleci.com/api/v2` (+ отдельно
`https://runner.circleci.com/api/v3` для Runner API), в отличие от
GitLab CI/CD, где хост обязателен как поле подключения.

**WHY `write_mode="both"`**, та же логика, что все остальные BYOK-
коннекторы портфеля: `connect_circleci` даёт дружелюбный guided-путь
с объяснением, что такое Personal API Token, при этом generic Secrets
screen остаётся как fallback.

**WHY SCOPE ПЕР-АККАУНТ, А НЕ ПЕР-ПРОЕКТ.**

Личный API Token в CircleCI даёт доступ ко ВСЕМ организациям/проектам,
видимым этому пользователю (подтверждено `GET /me/collaborations`) —
значит подключение делается один раз на аккаунт, а конкретный
`project-slug` (формат `{vcs}/{org}/{project}`, например
`gh/circleci/my-app`) передаётся как параметр в КАЖДОМ вызове,
аналогично тому, как MuleSoft-коннектор передаёт `org_id`/`env_id`
per-call, а не хранит их в подключении.

## 3. HTTP-клиент — общая механика

- Base URL: `https://circleci.com/api/v2` (Runner API отдельно:
  `https://runner.circleci.com/api/v3`).
- Auth header: `Circle-Token: <token>` на каждый запрос.
- Пагинация: courser-based (`page-token` query param + `next_page_token`
  в ответе) — тот же паттерн реализован как `_paginate` helper,
  аналогичный существующим клиентам (MuleSoft/n8n).
- Rate limit: 5000 запросов/час на токен — не требует специальной
  обработки сверх стандартного различения 401 (неверный токен) / 403
  (валидный токен, но нет прав) / 429 (rate limit, поверхностно
  прокидывается пользователю через `ClientFail`).
- `project-slug` вместо project_id UUID используется везде, где
  документация API v2 предлагает выбор (человекочитаемый, не требует
  отдельного resolve-запроса) — за исключением Pipeline Definition/
  Trigger/Rollback API, которые СПЕЦИФИЧНО требуют UUID `project_id`
  (получаемого через `getProjectBySlug`) — это задокументированная
  архитектурная особенность API v2, не ошибка.

## 4. Ярусы функционала (полный список — см. CONNECTOR_DISCOVERY.md §7)

**Ярус 1 — ключевые функции CI/CD-цикла (~18):**
connect_circleci, disconnect_circleci, list_connections, get_project,
list_pipelines, get_pipeline, trigger_pipeline, get_pipeline_config,
list_pipeline_workflows, get_workflow, list_workflow_jobs,
cancel_workflow, rerun_workflow, approve_workflow_job, get_job,
cancel_job, list_env_vars, create_env_var, delete_env_var.

**Ярус 2 — полнота CI/CD-домена (~22):**
list_contexts, create_context, delete_context, list_context_env_vars,
set_context_env_var, delete_context_env_var, list_schedules,
create_schedule, update_schedule, delete_schedule, list_checkout_keys,
create_checkout_key, delete_checkout_key, list_webhooks, create_webhook,
update_webhook, delete_webhook, get_project_settings,
update_project_settings, get_current_user, list_pipeline_definitions,
create_pipeline_definition, get_pipeline_definition,
update_pipeline_definition, delete_pipeline_definition, list_triggers,
create_trigger, get_trigger, update_trigger, delete_trigger,
rollback_project.

**Ярус 3 — Insights + value-add + Runner + bulk (~17):**
get_project_insights_summary, get_org_insights_summary,
list_insights_branches, get_flaky_tests, get_workflow_metrics,
get_workflow_runs, get_job_metrics, get_workflow_summary,
get_test_metrics, get_job_timeseries, list_self_hosted_runners,
audit_project_health (value-add, тот же паттерн, что
audit_cloudhub_environment/audit_org/audit_folder/audit_estate),
bulk_cancel_workflows, bulk_rerun_workflows.

Итого ~57 chat-функций.

## 5. Деструктивные операции — требуют явного подтверждения

Per стандартной архитектуре портфеля (`action_type="destructive"`):
delete_context, delete_env_var, delete_context_env_var,
delete_schedule, delete_checkout_key, delete_webhook,
delete_pipeline_definition, delete_trigger, rollback_project,
cancel_workflow, cancel_job, bulk_cancel_workflows. `rerun_workflow` и
`bulk_rerun_workflows` помечены как обычные write (не destructive) —
повторный запуск пайплайна не разрушает состояние, в отличие от отмены
или удаления ресурса.

## 6. UI (panels.py / panels_settings.py) — per UI_INTERFACE_STANDARD.md

Левый сайдбар: список подключений + форма подключения (единственное
поле — Personal API Token, плейсхолдер контекстно-подходящий, с
лейблом "Personal API Token"; опциональный label с лейблом "Label
(optional)"). Форма растянута на всю ширину сайдбара, содержимое —
на всю ширину формы. Никаких инструкций, дублирующих модалку — кнопка
"?" рядом с полем открывает модалку с инструкцией, где взять токен
(`app.circleci.com/settings/user/tokens`), сайдбар инструкций не
содержит. Единственная secondary-кнопка "App settings" — последний
элемент сайдбара, ведёт в центр-слот с disconnect per-connection.

## 7. Решение по объёму — уже принято пользователем

Задача #2218 прямо содержит "максимальная комплектация,
максимальный функционал" — трактуется как явное решение строить Ярус
1+2+3 без дополнительного вопроса, по прецеденту GitLab CI/CD/Power
Automate/MuleSoft/UiPath/Blue Prism/Automation Anywhere.
