"""Write the interactive dashboard from warehouse query results."""

from __future__ import annotations

import json
from pathlib import Path

from pipeline.config import DASHBOARD_PATH


def write_dashboard(payload: dict) -> None:
    template_path = Path(__file__).resolve().parent / "templates" / "dashboard.html"
    template = template_path.read_text()
    blob = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")
    if "__DATA_JSON__" not in template:
        raise RuntimeError("Dashboard template is missing the data token.")
    DASHBOARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    DASHBOARD_PATH.write_text(template.replace("__DATA_JSON__", blob))
