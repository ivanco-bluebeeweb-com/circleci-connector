# Pricing History — CircleCI Connector

Обязательный журнал: каждое выставление или изменение цен на функции этого
приложения фиксируется здесь — что изменилось, почему, и на основании
чего. Не переписывать прошлые записи — только дописывать новые сверху.

---

## 2026-08-21 — первичный прайсинг, ДО подачи на ревью

**Контекст:** после инцидента с MuleSoft Connector (прайсинг выставлен
постфактум, уже после `submit_for_review`) действует правило: прайсинг —
обязательная часть дефолтного поведения при разработке ЛЮБОГО приложения,
ВСЕГДА выставляется до `submit_for_review`, в той же сессии, что и
`deploy_app`. Для CircleCI Connector это применено с первого же деплоя —
`developer.update_pricing` вызван сразу после успешного `deploy_app`
(21/22 проверок), до какой-либо попытки отправить на ревью.

**Метод применения — `developer.update_pricing` (подтверждённо рабочий
метод, см. канонический `PRICING_POLICY.md` §3, прецедент n8n Connector /
MuleSoft Connector). `save_pricing` НЕ использовался.**

`pricing_config` передан как настоящий JSON-объект (не экранированная
строка) с полями `model`, `currency`, `monthly_price`, `free_tools`,
`tool_prices`, `notes`. `revenue_split_dev=95` передан явным параметром
(partner-тир этого разработчика), не только внутри `pricing_config`.

**Цены — фиксированная платформенная шкала {0, 8, 16, 20, 40, 60}, без
исключений и без x1.8-маркапа (CircleCI не Google-backed API):**

| Цена | Функции |
|---|---|
| 0 | `connect_circleci`, `disconnect_circleci`, `list_connections` (настройка доступа, не операция с CircleCI API) |
| 8 | Все `list_*`/`get_*` чтения: проекты, env vars, checkout keys, pipelines, workflows, jobs, artifacts, tests, insights, flaky tests, contexts, schedules, webhooks, pipeline definitions, triggers, current user, collaborations, runners, resource classes, runner tokens (простое чтение состояния) |
| 16 | Стандартные одиночные write/destructive-действия: create/delete env var, checkout key, context, context env var, schedule, webhook, runner resource class, runner token; delete trigger; approve_job; cancel_job |
| 20 | `trigger_pipeline`, `continue_pipeline`, `cancel_workflow`, `rerun_workflow` — действия, реально запускающие/останавливающие работу в проде пользователя прямо сейчас |
| 40 | `audit_project_health` — агрегированный value-add отчёт по пайплайнам/воркфлоу/insights/flaky tests |
| 60 | `bulk_cancel_pipelines` — bulk-операция сразу по многим пайплайнам |

`pricing_model = "per_action"`, `monthly_price = 0`, `revenue_split_dev = 95`
(partner-тир).

**Источник истины продублирован в `imperal.json["pricing"]`** этого
приложения (сгенерирован из `tool-prices.json` через build-time скрипт,
удалён после использования) — так цена видна прямо в манифесте независимо
от состояния платформенного API, по тому же правилу, что и у
MuleSoft/n8n/Make.com Connector.
