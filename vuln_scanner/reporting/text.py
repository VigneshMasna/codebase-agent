from __future__ import annotations

from vuln_scanner.core.models import ScanResult


def format_report(results: list[ScanResult]) -> str:
    lines = [
        "==============================",
        "BUG REPORT",
        "==============================",
        "",
    ]

    if not results:
        lines.append("No supported files or functions were found.")
        return "\n".join(lines)

    for result in results:
        lines.append(f"File: {result.source}")
        lines.append(f"Function: {result.function_name or 'UNKNOWN'}()")
        lines.append("")
        lines.append(f"Bug: {'YES' if result.final_label == 'BUG' else 'NO'}")
        lines.append(f"Severity: {result.severity}")
        lines.append(f"Confidence: {result.confidence:.2f}")
        lines.append(f"GraphCodeBERT: {result.graphcodebert_label}")
        lines.append(f"LLM: {result.llm_label} {result.severity}")
        lines.append("Function Body:")
        lines.append(result.function_body)
        lines.append("")

    return "\n".join(lines).rstrip()
