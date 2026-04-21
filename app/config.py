from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict


APP_DATA_DIR_NAME = "RenombradorPDFHospitalario"


def resource_path(*parts: str) -> Path:
    if getattr(sys, "frozen", False):
        base_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    else:
        base_dir = Path(__file__).resolve().parents[1]
    return base_dir.joinpath(*parts)


def user_data_path(*parts: str) -> Path:
    root = Path(os.environ.get("APPDATA", str(Path.home()))) / APP_DATA_DIR_NAME
    root.mkdir(parents=True, exist_ok=True)
    return root.joinpath(*parts)


CONFIG_PATH = resource_path("config", "app_config.json")


def load_config() -> Dict[str, Any]:
    with CONFIG_PATH.open("r", encoding="utf-8") as fh:
        config = json.load(fh)
    config["_resource_base"] = str(resource_path())
    config["_user_data_base"] = str(user_data_path())
    return config
