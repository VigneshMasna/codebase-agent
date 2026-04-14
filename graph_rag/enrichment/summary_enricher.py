"""
Summary Enricher — uses Gemini to add semantic intelligence to every Function and Class node.

For each Function / Class / Struct node that has source code (body), this enricher:

  1. Generates a natural-language `summary`   (2-3 sentences, full description)
  2. Generates `core_functionality`           (1 sentence, the single core purpose)
  3. Extracts semantic `tags`                 (3-6 lowercase keywords/phrases)
  4. Classifies the architectural `layer`     (service / repository / utility / ...)

After generating the summary, the node's embedding is updated to use
  "{name}: {core_functionality} [{tags joined}]"
instead of the raw source body — this gives semantically much richer vectors
for the hybrid retrieval system to work with.

This answers:
  "What does X do?"            → summary, core_functionality
  "Find authentication code"   → tags + TAGGED_WITH graph edges
  "Show me service layer"      → layer property
  "Explain this class"         → summary on Class nodes
"""
from __future__ import annotations

import json
import os
import re
import time

from extraction.symbol_models import CodeGraph, Node


# ── Gemini prompt ─────────────────────────────────────────────────────────────

_PROMPT_TEMPLATE = """\
You are an expert code analyst. Analyze the following {language} code and respond with ONLY a JSON object.

```
{body}
```

JSON format (no markdown, no extra text):
{{
  "summary": "2-3 sentence description of what this code does and why it exists",
  "core_functionality": "One precise sentence describing the single core purpose",
  "tags": ["tag1", "tag2", "tag3"],
  "layer": "LAYER"
}}

Rules for tags (3-6 items):
- Lowercase, single words or short hyphenated phrases
- Choose from these categories when relevant:
  authentication, authorization, validation, database, caching, networking,
  file-io, error-handling, logging, security, encryption, parsing, serialization,
  business-logic, data-transformation, utility, configuration, initialization,
  memory-management, concurrency, api, user-interface, algorithm

Rules for layer (pick exactly one):
  controller   → handles user input / HTTP requests / CLI commands
  service      → core business logic, orchestrates other functions
  repository   → direct database / storage access
  utility      → reusable helpers with no business context
  model        → data structures, DTOs, entities
  security     → authentication, authorization, cryptography
  networking   → HTTP clients, sockets, protocols
  io           → file system, streams
  algorithm    → pure computation, sorting, searching, mathematical
  unknown      → when none of the above fits
"""


class SummaryEnricher:
    """
    Enriches Function, Class, and Struct nodes with LLM-generated semantic metadata.
    Optionally re-embeds nodes using their summary (better semantic signal).
    """

    def __init__(self, embedder=None) -> None:
        from google import genai

        project  = os.getenv("GCP_PROJECT_ID", "")
        location = os.getenv("GCP_LOCATION", "global")

        if not project:
            raise ValueError(
                "GCP_PROJECT_ID is not set. Add it to .env before running enrichment."
            )

        try:
            self._client = genai.Client(vertexai=True, project=project, location=location)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to initialise Gemini client: {exc}. "
                "Check GCP_PROJECT_ID, GCP_LOCATION, and GOOGLE_APPLICATION_CREDENTIALS in .env."
            ) from exc

        self._model    = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
        self._embedder = embedder

    def enrich(self, graph: CodeGraph, delay_secs: float = 0.3) -> int:
        """
        Enrich all enrichable nodes in `graph` in-place.
        Returns number of nodes successfully enriched.

        delay_secs: pause between Gemini calls to avoid rate-limiting.
        """
        candidates = [
            n for n in graph.get_nodes()
            if n.label in ("Function", "Class", "Struct", "Enum")
            and n.body.strip()
            and not n.uid.startswith("external::")
        ]

        print(f"  Enriching {len(candidates)} nodes with Gemini...")
        enriched = 0

        for node in candidates:
            try:
                result = self._call_gemini(node)
                if result:
                    self._apply(node, result)
                    enriched += 1
                    print(f"    ✓ {node.uid[:70]}")
                if delay_secs > 0:
                    time.sleep(delay_secs)
            except Exception as exc:
                print(f"    ✗ {node.uid[:70]} — {exc}")
                # Don't abort; continue with remaining nodes

        print(f"  Enriched {enriched}/{len(candidates)} nodes")
        return enriched

    # ── Internal ──────────────────────────────────────────────────────────────

    def _call_gemini(self, node: Node) -> dict | None:
        lang = node.language or "unknown"
        body = node.body[:3000]  # cap to avoid token limits

        prompt = _PROMPT_TEMPLATE.format(language=lang, body=body)

        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
            )
        except Exception as exc:
            raise RuntimeError(f"Gemini API call failed: {exc}") from exc

        raw = response.text.strip()

        # Strip markdown code fences if Gemini wraps the response
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
        raw = re.sub(r"```\s*$", "", raw, flags=re.MULTILINE).strip()

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Second attempt: extract first {...} block
            match = re.search(r"\{[\s\S]*\}", raw)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
        return None

    def _apply(self, node: Node, result: dict) -> None:
        node.summary            = result.get("summary", "").strip()
        node.core_functionality = result.get("core_functionality", "").strip()
        node.tags               = [t.lower().strip() for t in result.get("tags", []) if t]
        node.layer              = result.get("layer", "unknown").lower().strip()

        # Re-embed using semantic summary text for better retrieval quality
        if self._embedder and node.core_functionality:
            tag_str = " ".join(node.tags)
            embed_text = f"{node.name}: {node.core_functionality} [{tag_str}]"
            try:
                node.embedding = self._embedder.generate(embed_text)
            except Exception:
                pass  # keep original embedding if re-embedding fails
