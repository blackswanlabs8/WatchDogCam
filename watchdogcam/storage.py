import json
import logging
import shutil
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)

Camera = Dict[str, object]


def _ensure_file(path: Path) -> None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("[]", encoding="utf-8")


def read_cameras(path: Path) -> List[Camera]:
    _ensure_file(path)
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
            if isinstance(data, list):
                return data
            logger.warning("Camera file does not contain a list, resetting")
            return []
    except json.JSONDecodeError:
        logger.exception("Invalid JSON in camera file; resetting to empty list")
        return []


def write_cameras(path: Path, cameras: List[Camera]) -> None:
    temp_path = path.with_suffix(".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    with temp_path.open("w", encoding="utf-8") as fh:
        json.dump(cameras, fh, ensure_ascii=False, indent=2)
    shutil.move(str(temp_path), path)


def find_camera(cameras: List[Camera], target: str) -> Camera | None:
    for camera in cameras:
        if camera.get("id") == target or camera.get("ip") == target:
            return camera
    return None
