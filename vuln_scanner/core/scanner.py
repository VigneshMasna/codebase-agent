from __future__ import annotations

from pathlib import Path

from vuln_scanner.core.extraction import extract_function_name, extract_functions
from vuln_scanner.core.language import detect_language_from_path
from vuln_scanner.core.models import ScanResult
from vuln_scanner.detectors.graphcodebert import GraphCodeBERTDetector
from vuln_scanner.detectors.llm import LLMBugDetector


# Confidence threshold above which GraphCodeBERT alone can flag a BUG
# (even if LLM disagrees), to catch cases the LLM misses.
_GCBERT_HIGH_CONFIDENCE = 0.80


class CodeScanner:
    def __init__(
        self,
        graph_detector: GraphCodeBERTDetector | None = None,
        llm_detector: LLMBugDetector | None = None,
    ) -> None:
        self.graph_detector = graph_detector or GraphCodeBERTDetector()
        self.llm_detector   = llm_detector   or LLMBugDetector()

    def scan_folder(self, folder: str | Path) -> list[ScanResult]:
        folder_path = Path(folder)
        if not folder_path.exists():
            raise FileNotFoundError(f"Folder not found: {folder_path}")
        if not folder_path.is_dir():
            raise ValueError(f"Path is not a folder: {folder_path}")

        report: list[ScanResult] = []
        for path in sorted(folder_path.rglob("*")):
            if path.is_file() and detect_language_from_path(path):
                try:
                    report.extend(self.scan_file(path))
                except Exception as exc:
                    print(f"  [scanner] Skipping {path.name}: {exc}")
        return report

    def scan_file(self, filepath: str | Path) -> list[ScanResult]:
        file_path = Path(filepath)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        if not file_path.is_file():
            raise ValueError(f"Path is not a file: {file_path}")

        language = detect_language_from_path(file_path)
        if language is None:
            raise ValueError(f"Unsupported file type: {file_path}")

        code = file_path.read_text(encoding="utf-8", errors="ignore")
        return self.scan_code(code, language, source=str(file_path))

    def scan_code(
        self,
        code: str,
        language: str,
        source: str = "<direct-input>",
    ) -> list[ScanResult]:
        functions = extract_functions(code)
        if not functions:
            # Return empty — don't crash; file may have no extractable functions
            return []

        results: list[ScanResult] = []

        for function in functions:
            function = function.strip()
            if not function:
                continue

            try:
                graph_label, confidence = self.graph_detector.detect_bug(function, language)
            except Exception as exc:
                print(f"  [graphcodebert] Error on function: {exc}")
                graph_label, confidence = "SAFE", 0.0

            try:
                llm_label, severity = self.llm_detector.detect_bug(function, language)
            except Exception as exc:
                print(f"  [llm] Error on function: {exc}")
                llm_label, severity = "SAFE", "NONE"

            final_label, severity = _decide(
                graph_label, confidence, llm_label, severity
            )

            results.append(
                ScanResult(
                    source=source,
                    language=language,
                    function_name=extract_function_name(function),
                    function_body=function,
                    graphcodebert_label=graph_label,
                    confidence=confidence,
                    llm_label=llm_label,
                    severity=severity,
                    final_label=final_label,
                )
            )

        return results


# ── Decision logic ────────────────────────────────────────────────────────────

def _decide(
    graph_label: str,
    confidence: float,
    llm_label: str,
    severity: str,
) -> tuple[str, str]:
    """
    Combine GraphCodeBERT and LLM signals into a final verdict.

    Strategy (ordered by priority):
      1. Both agree BUG                    → BUG  (consensus, highest confidence)
      2. LLM says BUG with CRITICAL/HIGH   → BUG  (trust LLM on serious severity)
      3. Otherwise                         → SAFE

    Note: GraphCodeBERT alone is NOT used as a standalone signal because it is
    trained on CVE-style vulnerable code and predicts BUG with high confidence
    for all application code regardless of actual safety. It is used only as a
    corroborating second opinion when the LLM also says BUG.
    """
    if graph_label == "BUG" and llm_label == "BUG":
        # Consensus — keep LLM severity (more semantically reliable)
        return "BUG", severity

    if llm_label == "BUG" and severity in ("CRITICAL", "HIGH"):
        # LLM identifies a serious issue — trust it even without GCB agreement
        return "BUG", severity

    return "SAFE", "NONE"
