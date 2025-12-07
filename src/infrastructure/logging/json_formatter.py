import json
import logging
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import tomli


class JSONFormatter(logging.Formatter):
    def __init__(self, version: str):
        super().__init__()
        self.version = version

    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "version": self.version,
            "message": record.getMessage(),
            "logger": record.name,
        }

        if hasattr(record, "module"):
            log_data["module"] = record.module
        else:
            log_data["module"] = record.name

        if hasattr(record, "funcName"):
            log_data["function"] = record.funcName

        if hasattr(record, "lineno"):
            log_data["line"] = record.lineno

        if hasattr(record, "threadName"):
            log_data["thread"] = record.threadName

        if hasattr(record, "process"):
            log_data["process"] = record.process

        context = getattr(record, "context", None)
        if context and isinstance(context, dict):
            log_data["context"] = context

        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": traceback.format_exception(*record.exc_info),
            }

        return json.dumps(log_data, ensure_ascii=False)


def get_version(project_root: Path) -> str:
    pyproject_path = project_root / "pyproject.toml"
    if pyproject_path.exists():
        try:
            with open(pyproject_path, "rb") as f:
                data = tomli.load(f)
                return data.get("tool", {}).get("poetry", {}).get("version", "0.1.0")
        except Exception:
            return "0.1.0"
    return "0.1.0"

