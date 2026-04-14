"""
BugAnnotator — runs the vulnerability scanner on every Function node
already stored in Neo4j and writes bug detection results back as node properties.

Properties written to each Function node:
  is_buggy        : bool   — true if the scanner flagged this function
  severity        : str    — CRITICAL / HIGH / MEDIUM / LOW / NONE
  bug_confidence  : float  — GraphCodeBERT confidence score (0.0–1.0)

This runs AFTER the graph is fully built (post Neo4j push) so it has
access to the enriched function bodies stored in the database.
Uses Tree-Sitter-extracted bodies from Neo4j — more accurate than
the standalone scanner's regex extraction.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

# Allow import from repo root (for vuln_scanner package)
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from graph.neo4j_client import Neo4jClient


class BugAnnotator:
    """
    Annotates Function nodes in Neo4j with vulnerability scan results.

    Lazy-loads the scanner on first use so the embedding pipeline
    doesn't pay the model-load cost unless bug annotation is requested.
    """

    def __init__(self, client: Neo4jClient) -> None:
        self._client  = client
        self._scanner = None   # loaded on first annotate() call

    def annotate(self) -> dict:
        """
        Scan every Function node that has a body stored in Neo4j.
        Write is_buggy, severity, bug_confidence back to each node.

        Returns a summary dict with counts by severity.
        """
        self._load_scanner()

        rows = self._client.run_query("""
            MATCH (f:Function)
            WHERE f.body IS NOT NULL AND f.body <> ''
            RETURN f.uid AS uid, f.body AS body, f.language AS language,
                   f.name AS name
        """)

        if not rows:
            print("  No Function nodes with body found — skipping bug annotation.")
            return {"total": 0, "bugs": 0}

        print(f"  Scanning {len(rows)} functions for vulnerabilities...")

        counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "NONE": 0}
        bug_count = 0

        for i, row in enumerate(rows, 1):
            uid      = row["uid"]
            body     = row["body"]
            language = row.get("language") or "unknown"
            name     = row.get("name") or uid

            try:
                graph_label, confidence = self._scanner.graph_detector.detect_bug(
                    body, language
                )
                llm_label, severity, reason = self._scanner.llm_detector.detect_bug(
                    body, language
                )

                from vuln_scanner.core.scanner import _decide
                final_label, final_severity = _decide(
                    graph_label, confidence, llm_label, severity
                )

            except Exception as exc:
                print(f"    [warn] {name}: scan error — {exc}")
                final_label    = "SAFE"
                final_severity = "NONE"
                confidence     = 0.0
                reason         = None

            is_buggy = final_label == "BUG"
            if is_buggy:
                bug_count += 1

            counts[final_severity] = counts.get(final_severity, 0) + 1

            # Write results back to the node
            try:
                self._client.run_query(
                    """
                    MATCH (f:Function {uid: $uid})
                    SET f.is_buggy       = $is_buggy,
                        f.severity       = $severity,
                        f.bug_confidence = $confidence,
                        f.bug_reason     = $bug_reason
                    """,
                    {
                        "uid":        uid,
                        "is_buggy":   is_buggy,
                        "severity":   final_severity,
                        "confidence": round(confidence, 4),
                        "bug_reason": reason if is_buggy else None,
                    },
                )
            except Exception as exc:
                print(f"    [warn] {name}: failed to write results to Neo4j — {exc}")

            # Progress indicator every 10 functions
            if i % 10 == 0 or i == len(rows):
                print(f"    [{i}/{len(rows)}] done")

            # Small delay to avoid LLM rate limiting
            time.sleep(0.2)

        return {
            "total":    len(rows),
            "bugs":     bug_count,
            "CRITICAL": counts.get("CRITICAL", 0),
            "HIGH":     counts.get("HIGH", 0),
            "MEDIUM":   counts.get("MEDIUM", 0),
            "LOW":      counts.get("LOW", 0),
        }

    def _load_scanner(self) -> None:
        if self._scanner is not None:
            return
        # Ensure GOOGLE_APPLICATION_CREDENTIALS is an absolute path before
        # vuln_scanner/config/settings.py resolves it (it re-resolves relative paths
        # from its own ROOT_DIR, which would produce a wrong absolute path).
        import os
        repo_root = Path(__file__).parent.parent.parent
        gac = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
        if gac and not Path(gac).is_absolute():
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(
                (repo_root / gac).resolve()
            )

        print("  Loading vulnerability scanner (GraphCodeBERT + LLM)...")
        try:
            from vuln_scanner.core.scanner import CodeScanner
            self._scanner = CodeScanner()
        except Exception as exc:
            raise RuntimeError(
                f"Failed to load vulnerability scanner: {exc}. "
                "Check that model files exist and GCP credentials are configured in .env."
            ) from exc
        print("  Scanner ready.")
