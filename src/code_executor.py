"""Sandboxed pandas code execution.

Runs LLM-generated Python code in a restricted subprocess with a timeout and strict allowlist.
Only safe pandas, numpy, and DataFrame analytical operations are permitted.
All file/network I/O, dunder attribute introspection, and code execution facilities are stripped.
"""

import ast
import contextlib
import io
import json
import logging
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 30
_MAX_OUTPUT_CHARS = 50_000

_RUNNER_TEMPLATE = textwrap.dedent("""\
    import contextlib, json, sys, io
    import pandas as pd
    import numpy as np

    df = pd.read_json(sys.stdin, orient="split")

    # Strip dangerous I/O and execution methods from pandas and DataFrames at runtime
    for _name in list(dir(pd)):
        if _name.startswith("read_") or _name in ("eval", "read_pickle", "read_csv"):
            try:
                delattr(pd, _name)
            except Exception:
                pass

    _dangerous_methods = (
        "to_csv", "to_pickle", "to_sql", "to_excel", "to_parquet",
        "to_feather", "to_hdf", "to_stata", "to_clipboard", "eval", "query",
    )
    for _cls in (pd.DataFrame, pd.Series):
        for _m in _dangerous_methods:
            if hasattr(_cls, _m):
                try:
                    delattr(_cls, _m)
                except Exception:
                    pass

    _capture = io.StringIO()
    _safe_builtins = {
        "abs": abs, "all": all, "any": any, "bool": bool,
        "dict": dict, "enumerate": enumerate, "filter": filter,
        "float": float, "int": int, "len": len, "list": list,
        "max": max, "min": min, "range": range, "round": round,
        "set": set, "sorted": sorted, "str": str, "sum": sum,
        "tuple": tuple, "zip": zip,
    }

    try:
        _globals = {"__builtins__": _safe_builtins, "df": df, "pd": pd, "np": np}
        with contextlib.redirect_stdout(_capture):
            exec(CODE_PLACEHOLDER, _globals)

        _result = _globals.get("result")
        if _result is None:
            # If user code printed something, grab it
            _result = _capture.getvalue() or "Kode dieksekusi, tapi tidak ada variabel `result`."

        if isinstance(_result, pd.DataFrame):
            out = {
                "type": "dataframe",
                "message": "Ini hasil eksekusi kode.",
                "rows": _result.head(50).astype(str).to_dict(orient="records"),
            }
        elif isinstance(_result, pd.Series):
            out = {
                "type": "series",
                "message": "Ini hasil eksekusi kode.",
                "rows": _result.reset_index().head(50).astype(str).to_dict(orient="records"),
            }
        elif isinstance(_result, dict):
            out = {"type": "dict", "message": "Ini hasil eksekusi kode.", "table": {str(k): str(v) for k, v in _result.items()}}
        elif isinstance(_result, (int, float, np.integer, np.floating)):
            out = {"type": "scalar", "message": f"Hasil: {_result}"}
        else:
            out = {"type": "text", "message": str(_result)[:5000]}

        json.dump({"ok": True, **out}, sys.stdout)
    except Exception as exc:
        json.dump({"ok": False, "message": f"Error: {type(exc).__name__}: {exc}"}, sys.stdout)
""")

# Deny list — forbidden module imports or dangerous keywords
_DENY_PATTERNS = [
    "import os", "import sys", "import subprocess", "import shutil",
    "import socket", "import http", "import urllib", "import requests",
    "__import__", "eval(", "exec(", "compile(", "open(",
    "os.system", "os.popen", "os.remove", "os.unlink",
    "shutil.", "subprocess.", "socket.",
    "globals(", "locals(", "breakpoint(",
]

_DENY_NAMES = {
    "__builtins__", "__import__", "eval", "exec", "compile", "open",
    "globals", "locals", "vars", "getattr", "setattr", "delattr", "hasattr",
    "input", "breakpoint", "help",
}

_DANGEROUS_IO_ATTRS = {
    "to_csv", "to_pickle", "to_sql", "to_excel", "to_parquet",
    "to_feather", "to_hdf", "to_stata", "to_clipboard", "to_json",
    "read_pickle", "read_csv", "read_sql", "read_excel", "read_parquet",
    "read_feather", "read_hdf", "read_stata", "read_clipboard", "read_json",
    "eval", "query",
}
_DENY_EXPLICIT_ATTRS = {
    "__class__", "__base__", "__subclasses__", "__globals__", "__code__",
    "__dict__", "__closure__", "__builtins__",
}


def validate_code(code: str) -> str | None:
    """Validate python code using an AST allowlist and forbidden pattern filter."""
    code_lower = code.lower()
    for pattern in _DENY_PATTERNS:
        if pattern.lower() in code_lower:
            return f"Kode ditolak: `{pattern}` tidak diperbolehkan demi keamanan."

    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as exc:
        return f"Kode ditolak: sintaks tidak valid ({exc.msg})."

    for node in ast.walk(tree):
        # Disallow all imports
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            modules = [alias.name for alias in node.names]
            return f"Kode ditolak: import {', '.join(modules)} tidak diperbolehkan."

        # Disallow dangerous names / builtins
        if isinstance(node, ast.Name):
            if node.id in _DENY_NAMES or node.id.startswith("__"):
                return f"Kode ditolak: pemanggilan `{node.id}` tidak diperbolehkan demi keamanan."

        # Disallow attribute traversal to dunders or file/network I/O
        if isinstance(node, ast.Attribute):
            attr = node.attr
            if attr in _DENY_EXPLICIT_ATTRS or attr in _DANGEROUS_IO_ATTRS or attr.startswith("__"):
                return f"Kode ditolak: atribut/metode `{attr}` tidak diperbolehkan demi keamanan."
            if attr.startswith("read_"):
                return f"Kode ditolak: metode I/O `{attr}` tidak diperbolehkan demi keamanan."

    return None


def execute_code(code: str, df) -> dict:
    """Execute pandas code against the given DataFrame in a sandboxed subprocess."""
    import pandas as pd

    violation = validate_code(code)
    if violation:
        return {"ok": False, "message": violation}

    # Build runner script with the code inlined
    escaped_code = repr(code)
    runner = _RUNNER_TEMPLATE.replace("CODE_PLACEHOLDER", escaped_code)

    # Serialize df to JSON (split orientation keeps dtypes best)
    try:
        df_json = df.to_json(orient="split", date_format="iso")
    except Exception as exc:
        return {"ok": False, "message": f"Gagal serialisasi dataset: {exc}"}

    try:
        proc = subprocess.run(
            [sys.executable, "-c", runner],
            input=df_json,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
            cwd=tempfile.gettempdir(),
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "message": f"Eksekusi timeout ({_TIMEOUT_SECONDS} detik). Coba kode yang lebih efisien."}
    except Exception as exc:
        logger.exception("Code execution subprocess failed")
        return {"ok": False, "message": f"Gagal menjalankan kode: {exc}"}

    output = proc.stdout[:_MAX_OUTPUT_CHARS]
    if proc.returncode != 0:
        stderr = (proc.stderr or "")[:2000]
        return {"ok": False, "message": f"Kode error:\n{stderr}"}

    try:
        result = json.loads(output)
        return result
    except json.JSONDecodeError:
        return {"ok": False, "message": f"Output tidak valid: {output[:500]}"}

