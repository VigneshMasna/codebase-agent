from __future__ import annotations

import re


# Matches function/method headers up to and including the opening brace.
# Handles: Java (public/private/...), C/C++ (void/int/static/...), modifiers, generics, pointers.
# Does NOT use [^{}]* so nested braces are handled separately via _find_matching_brace().
_FUNC_HEADER_RE = re.compile(
    r"""
    (?:                                         # optional modifiers (Java + C/C++)
        (?:public|private|protected|static|final
          |synchronized|abstract|native|inline
          |virtual|override|const|extern|explicit)\s+
    )*
    (?:[\w:<>\[\]*&,\s]+?\s+)?                  # return type (non-greedy)
    ([A-Za-z_]\w*)                              # function name — capture group 1
    \s*\([^)]*\)                                # parameter list (no nested parens)
    (?:\s*(?:const|noexcept|override|throws\s+[\w,\s]+))? # optional qualifiers
    \s*\{                                       # opening brace
    """,
    re.VERBOSE,
)

# Keywords that look like function calls but are control-flow statements
_SKIP_NAMES = frozenset({
    "if", "else", "for", "while", "do", "switch", "catch",
    "try", "return", "new", "delete", "sizeof", "typeof",
})


def extract_functions(code: str) -> list[str]:
    """
    Extract all function/method bodies from source code.

    Uses a two-phase approach:
      1. Regex to find function headers (signature + opening brace)
      2. Balanced-brace traversal to find the matching closing brace

    This correctly handles functions with nested if/for/while/switch blocks.
    """
    functions: list[str] = []
    # Remove single-line comments to avoid brace confusion
    code_clean = re.sub(r"//[^\n]*", "", code)
    # Remove multi-line comments
    code_clean = re.sub(r"/\*.*?\*/", "", code_clean, flags=re.DOTALL)

    for match in _FUNC_HEADER_RE.finditer(code_clean):
        func_name = match.group(1)
        if func_name in _SKIP_NAMES:
            continue

        # The opening brace is the last character of the match
        open_brace_pos = match.end() - 1
        close_brace_pos = _find_matching_brace(code_clean, open_brace_pos)
        if close_brace_pos is None:
            continue

        full_func = code_clean[match.start(): close_brace_pos + 1].strip()
        if full_func:
            functions.append(full_func)

    return functions


def extract_function_name(function_code: str) -> str | None:
    """Extract the function name from a function code string."""
    match = _FUNC_HEADER_RE.search(function_code)
    if match and match.group(1) not in _SKIP_NAMES:
        return match.group(1)
    return None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _find_matching_brace(code: str, open_pos: int) -> int | None:
    """
    Given the index of an opening brace in `code`, return the index of
    the matching closing brace, accounting for nesting and string literals.
    Returns None if no matching brace is found.
    """
    depth = 0
    in_string: str | None = None   # None, '"', or "'"
    i = open_pos

    while i < len(code):
        ch = code[i]

        # Handle string/char literals — don't count braces inside strings
        if in_string:
            if ch == "\\" and i + 1 < len(code):
                i += 2  # skip escaped character
                continue
            if ch == in_string:
                in_string = None
        else:
            if ch in ('"', "'"):
                in_string = ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return i

        i += 1

    return None
