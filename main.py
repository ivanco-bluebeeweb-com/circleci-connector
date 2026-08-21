"""Entrypoint for the web-kernel and CLI tools (imperal validate/build).

Sets up sys.path, purges stale module cache, then imports ext/chat and all
handler modules so their decorators register on the same Extension instance
-- same pattern as MuleSoft Connector's / Power Automate Connector's main.py.
"""

import os
import sys

_EXT_DIR = os.path.dirname(os.path.abspath(__file__))
if _EXT_DIR not in sys.path:
    sys.path.insert(0, _EXT_DIR)

_LOCAL = (
    "app", "schemas", "circleci_client",
    "handlers_connection", "handlers_project", "handlers_pipeline",
    "handlers_workflow_job", "handlers_insights", "handlers_context",
    "handlers_schedule_webhook", "handlers_trigger_user", "handlers_runner",
    "handlers_bulk_audit",
    "panels", "panels_settings",
)
for _mod in _LOCAL:
    sys.modules.pop(_mod, None)

from app import ext, chat  # noqa: E402,F401
import handlers_connection  # noqa: E402,F401
import handlers_project  # noqa: E402,F401
import handlers_pipeline  # noqa: E402,F401
import handlers_workflow_job  # noqa: E402,F401
import handlers_insights  # noqa: E402,F401
import handlers_context  # noqa: E402,F401
import handlers_schedule_webhook  # noqa: E402,F401
import handlers_trigger_user  # noqa: E402,F401
import handlers_runner  # noqa: E402,F401
import handlers_bulk_audit  # noqa: E402,F401
import panels  # noqa: E402,F401
import panels_settings  # noqa: E402,F401
