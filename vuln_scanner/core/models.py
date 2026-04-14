from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class ScanResult:
    source: str
    language: str
    function_name: str | None
    function_body: str
    graphcodebert_label: str
    confidence: float
    llm_label: str
    severity: str
    final_label: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
