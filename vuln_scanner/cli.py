from __future__ import annotations

import argparse
from pathlib import Path

from vuln_scanner.config.settings import get_settings
from vuln_scanner.core.language import SUPPORTED_LANGUAGES
from vuln_scanner.core.scanner import CodeScanner
from vuln_scanner.reporting.json_report import write_json_report
from vuln_scanner.reporting.text import format_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AI vulnerability scanner CLI.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--folder", help="Scan a folder of source files.")
    group.add_argument("--file", help="Scan a single source file.")
    group.add_argument("--code", help="Scan a direct code snippet.")
    parser.add_argument(
        "--language",
        choices=sorted(SUPPORTED_LANGUAGES),
        help="Required when using --code.",
    )
    parser.add_argument(
        "--json-out",
        help="Optional path to export the structured report as JSON.",
    )
    return parser


def run_cli(args: argparse.Namespace | None = None) -> int:
    parser = build_parser()
    parsed = parser.parse_args(args=args)

    if parsed.code and not parsed.language:
        parser.error("--language is required when using --code.")

    scanner = CodeScanner()

    if parsed.folder:
        results = scanner.scan_folder(parsed.folder)
    elif parsed.file:
        results = scanner.scan_file(parsed.file)
    else:
        results = scanner.scan_code(parsed.code, parsed.language, source="<direct-input>")

    report_text = format_report(results)
    print(report_text)

    if parsed.json_out:
        output_path = write_json_report(results, parsed.json_out)
        print(f"\nJSON report written to: {output_path}")

    return 0


def run_default_scan() -> int:
    settings = get_settings()
    scanner = CodeScanner()
    results = scanner.scan_folder(Path(settings.default_scan_folder))
    print(format_report(results))
    return 0
