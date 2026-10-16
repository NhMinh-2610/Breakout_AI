"""Non-secret scheduling metadata shared with the Windows installer."""

import hashlib
import json
import sys

from breakout_ai.config import ROOT, Settings


def description() -> dict:
    settings = Settings.from_env()
    identity = hashlib.sha256((str(ROOT.resolve()).casefold() + "|" + settings.workspace_id).encode()).hexdigest()[:12]
    return {"task_name": f"BreakoutAI-Morning-{identity}", "marker": f"BreakoutAI daily review {identity}",
            "root": str(ROOT), "database": str(settings.database_path), "workspace": settings.workspace_id,
            "python": sys.executable, "time": "07:30", "timezone": "Asia/Ho_Chi_Minh"}


if __name__ == "__main__":
    print(json.dumps(description()))
