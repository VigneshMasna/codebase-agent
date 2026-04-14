from __future__ import annotations

import os
import re
import time

from google import genai

from vuln_scanner.config.settings import get_settings


_SEVERITY_MAP = {
    "CRITICAL": "CRITICAL",
    "HIGH":     "HIGH",
    "MEDIUM":   "MEDIUM",
    "MED":      "MEDIUM",
    "LOW":      "LOW",
    "NONE":     "NONE",
}

_LANGUAGE_DISPLAY = {
    "c":    "C",
    "cpp":  "C++",
    "java": "Java",
}


class LLMBugDetector:
    def __init__(self) -> None:
        settings = get_settings()
        settings.validate_for_llm()

        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(
            settings.google_application_credentials
        )

        self.client = genai.Client(
            vertexai=True,
            project=settings.gcp_project_id,
            location=settings.gcp_location,
        )
        self.model = settings.gemini_model

    def detect_bug(self, code: str, language: str = "unknown") -> tuple[str, str, str | None]:
        """
        Analyze a function for bugs.

        Args:
            code:     Function source code.
            language: 'c', 'cpp', or 'java' — used for language-aware analysis.

        Returns:
            (label, severity, reason): label is 'BUG' or 'SAFE';
            severity is 'CRITICAL'/'HIGH'/'MEDIUM'/'LOW'/'NONE';
            reason is a one-sentence explanation (None for SAFE).
        """
        lang_display = _LANGUAGE_DISPLAY.get(language.lower(), language.upper())
        prompt = self._build_prompt(code, lang_display)

        for attempt in range(3):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                )
                label, severity, reason = _parse_response(response.text)
                print(f"LLM detected: {label} | Severity: {severity}")
                return label, severity, reason
            except Exception as exc:
                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
                else:
                    print(f"LLM detector failed after 3 attempts: {exc}")
                    return "SAFE", "NONE", None

        return "SAFE", "NONE", None

    @staticmethod
    def _build_prompt(code: str, lang_display: str) -> str:
        return f"""You are a static code security analysis tool specialized in {lang_display}.

Analyze the following {lang_display} function for security vulnerabilities and bugs.

Severity rules:
  CRITICAL — memory corruption, buffer overflow, use-after-free, format string attacks,
             unsafe functions (gets, strcpy/strcat without bounds, sprintf without size),
             command injection, SQL injection, remote code execution risk
  HIGH     — null/nullptr dereference, out-of-bounds array access, integer overflow,
             resource leaks (memory, file handles, sockets), race conditions,
             unvalidated external input used in sensitive operations
  MEDIUM   — divide by zero, logic errors causing incorrect behavior,
             missing error checks on critical operations, insecure randomness,
             uninitialized variable use
  LOW      — bad practices, minor issues, dead code, deprecated API usage

For a BUG, respond with EXACTLY two lines:
VERDICT: BUG <SEVERITY>
REASON: <one concise sentence describing the specific vulnerability>

For a safe function, respond with EXACTLY one line:
VERDICT: SAFE NONE

{lang_display} function to analyze:
{code}
"""


def _parse_response(text: str) -> tuple[str, str, str | None]:
    """
    Robustly parse the LLM response.

    Handles both new structured format:
        VERDICT: BUG CRITICAL
        REASON: <explanation>
    and legacy flat format:
        BUG CRITICAL
    """
    raw   = text.strip()
    lines = raw.splitlines()

    reason: str | None = None

    # Extract REASON line if present
    for line in lines:
        stripped = line.strip()
        if stripped.upper().startswith("REASON:"):
            reason = stripped[len("REASON:"):].strip() or None
            break

    # Find the verdict line
    for line in lines:
        stripped = line.strip()
        upper = stripped.upper()
        # Strip "VERDICT:" prefix if present
        if upper.startswith("VERDICT:"):
            upper = upper[len("VERDICT:"):].strip()

        cleaned = re.sub(r"[:\-_,]", " ", upper)
        tokens  = cleaned.split()

        for i, tok in enumerate(tokens):
            if tok == "BUG":
                for j in range(i + 1, min(i + 3, len(tokens))):
                    if tokens[j] in _SEVERITY_MAP:
                        return "BUG", _SEVERITY_MAP[tokens[j]], reason
                return "BUG", "MEDIUM", reason
            if tok == "SAFE":
                return "SAFE", "NONE", None

    return "SAFE", "NONE", None
