from __future__ import annotations

import json
from pathlib import Path

from vuln_scanner.core.models import ScanResult


def write_json_report(results: list[ScanResult], output_path: str | Path) -> Path:
    path = Path(output_path)
    payload = [result.to_dict() for result in results]
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path
