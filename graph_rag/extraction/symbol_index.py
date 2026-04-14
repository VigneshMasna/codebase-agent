"""
Global symbol index — maps simple names to fully-qualified UIDs.

Used in the two-pass extraction pipeline:
  Pass 1: all extractors populate the index as they create nodes
  Pass 2: CallResolver uses the index to convert callee names → target UIDs
"""
from __future__ import annotations


class SymbolIndex:

    def __init__(self) -> None:
        # name → [uid, ...] (one name can map to multiple files / overloads)
        self._functions: dict[str, list[str]] = {}
        self._classes: dict[str, list[str]] = {}
        self._structs: dict[str, list[str]] = {}

    # ── Registration ──────────────────────────────────────────────────────────

    def add_function(self, name: str, uid: str) -> None:
        self._functions.setdefault(name, []).append(uid)

    def add_class(self, name: str, uid: str) -> None:
        self._classes.setdefault(name, []).append(uid)

    def add_struct(self, name: str, uid: str) -> None:
        self._structs.setdefault(name, []).append(uid)

    # ── Resolution ────────────────────────────────────────────────────────────

    def resolve_function(self, name: str, caller_file: str = "") -> str | None:
        """
        Return the uid of the best matching function for the given name.

        Resolution priority:
          1. Exact match in the same file as the caller
          2. Single match anywhere in the repo
          3. First match (ambiguous — pick arbitrarily)
          Returns None if the name is not in the index (external / stdlib).
        """
        matches = self._functions.get(name, [])
        if not matches:
            return None

        # Prefer same-file match
        if caller_file:
            for uid in matches:
                if uid.startswith(caller_file + "::"):
                    return uid

        # Unique match anywhere
        if len(matches) == 1:
            return matches[0]

        # Ambiguous — return first (could be improved with call-context heuristics)
        return matches[0]

    def resolve_class(self, name: str) -> str | None:
        matches = self._classes.get(name, [])
        return matches[0] if matches else None

    def resolve_struct(self, name: str) -> str | None:
        matches = self._structs.get(name, [])
        return matches[0] if matches else None

    # ── Diagnostics ───────────────────────────────────────────────────────────

    def stats(self) -> str:
        return (
            f"SymbolIndex: {len(self._functions)} functions, "
            f"{len(self._classes)} classes, "
            f"{len(self._structs)} structs"
        )
