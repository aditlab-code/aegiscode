"""Universal Linter Runner untuk workspace AegisCode.

Mengeksekusi linter berbasis workspace (ESLint untuk JS/TS/Vue, Ruff/Flake8 untuk Python)
dengan format output JSON terstruktur dan penanganan graceful.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional


_JS_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx", ".vue", ".mjs", ".cjs"}
_PY_EXTENSIONS = {".py"}


def _resolve_executable(project_root: Path, binary_name: str, relative_dirs: List[str]) -> Optional[str]:
    """Cari binary di dalam workspace project, fallback ke sistem PATH."""
    is_win = sys.platform.startswith("win")
    candidates = []

    for rdir in relative_dirs:
        base = project_root / rdir
        candidates.append(base / binary_name)
        if is_win:
            candidates.append(base / f"{binary_name}.cmd")
            candidates.append(base / f"{binary_name}.exe")
            candidates.append(base / f"{binary_name}.bat")

    for cand in candidates:
        if cand.is_file() and (is_win or os.access(cand, os.X_OK)):
            return str(cand)

    found = shutil.which(binary_name)
    if found:
        return found
    if is_win:
        for ext in [".cmd", ".exe", ".bat"]:
            found_win = shutil.which(f"{binary_name}{ext}")
            if found_win:
                return found_win

    return None


def _find_eslint_binary(project_root: Path) -> Optional[str]:
    rel_dirs = [os.path.join("node_modules", ".bin")]
    return _resolve_executable(project_root, "eslint", rel_dirs)


def _find_ruff_binary(project_root: Path) -> Optional[str]:
    bin_dir = "Scripts" if sys.platform.startswith("win") else "bin"
    rel_dirs = [os.path.join(".venv", bin_dir), os.path.join("venv", bin_dir)]
    return _resolve_executable(project_root, "ruff", rel_dirs)


def _find_flake8_binary(project_root: Path) -> Optional[str]:
    bin_dir = "Scripts" if sys.platform.startswith("win") else "bin"
    rel_dirs = [os.path.join(".venv", bin_dir), os.path.join("venv", bin_dir)]
    return _resolve_executable(project_root, "flake8", rel_dirs)


def _run_cmd(cmd: List[str], cwd: Path, timeout: int = 15) -> Optional[subprocess.CompletedProcess]:
    try:
        return subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError, ValueError):
        return None


def _parse_eslint_json(output: str, project_root: Path) -> List[Dict[str, Any]]:
    diagnostics: List[Dict[str, Any]] = []
    if not output or not output.strip():
        return diagnostics

    try:
        data = json.loads(output)
    except ValueError:
        return diagnostics

    if not isinstance(data, list):
        return diagnostics

    for file_entry in data:
        if not isinstance(file_entry, dict):
            continue
        raw_path = file_entry.get("filePath", "")
        try:
            rel_file = str(Path(raw_path).resolve().relative_to(project_root.resolve()))
        except Exception:
            rel_file = Path(raw_path).name or raw_path

        messages = file_entry.get("messages", [])
        if not isinstance(messages, list):
            continue

        for msg in messages:
            if not isinstance(msg, dict):
                continue
            line = int(msg.get("line") or 1)
            col = int(msg.get("column") or 1)
            end_line = int(msg.get("endLine") or line)
            end_col = int(msg.get("endColumn") or col)
            raw_sev = msg.get("severity")
            severity = "error" if raw_sev == 2 else "warning"

            diagnostics.append({
                "file": rel_file,
                "line": max(1, line),
                "col": max(1, col),
                "end_line": max(1, end_line),
                "end_col": max(1, end_col),
                "message": str(msg.get("message") or ""),
                "severity": severity,
                "rule_id": str(msg.get("ruleId") or ""),
                "source": "eslint",
            })

    return diagnostics


def _parse_ruff_json(output: str, project_root: Path) -> List[Dict[str, Any]]:
    diagnostics: List[Dict[str, Any]] = []
    if not output or not output.strip():
        return diagnostics

    try:
        data = json.loads(output)
    except ValueError:
        return diagnostics

    if not isinstance(data, list):
        return diagnostics

    for item in data:
        if not isinstance(item, dict):
            continue
        raw_path = item.get("filename", "")
        try:
            rel_file = str(Path(raw_path).resolve().relative_to(project_root.resolve()))
        except Exception:
            rel_file = Path(raw_path).name or raw_path

        loc = item.get("location") or {}
        end_loc = item.get("end_location") or {}

        line = int(loc.get("row") or 1)
        col = int(loc.get("column") or 1)
        end_line = int(end_loc.get("row") or line)
        end_col = int(end_loc.get("column") or col)

        code = str(item.get("code") or "")
        if code.startswith(("E9", "F82", "Syntax")) or "syntax" in code.lower():
            severity = "error"
        else:
            severity = "warning"

        diagnostics.append({
            "file": rel_file,
            "line": max(1, line),
            "col": max(1, col),
            "end_line": max(1, end_line),
            "end_col": max(1, end_col),
            "message": str(item.get("message") or ""),
            "severity": severity,
            "rule_id": code,
            "source": "ruff",
        })

    return diagnostics


def _parse_flake8_output(output: str, project_root: Path) -> List[Dict[str, Any]]:
    import re
    diagnostics: List[Dict[str, Any]] = []
    if not output or not output.strip():
        return diagnostics

    pattern = re.compile(r"^([^:]+):(\d+):(\d+):\s*([A-Z0-9]+)\s*(.*)$")
    for line in output.splitlines():
        match = pattern.match(line.strip())
        if not match:
            continue
        raw_path, l_str, c_str, code, msg = match.groups()
        try:
            rel_file = str(Path(raw_path).resolve().relative_to(project_root.resolve()))
        except Exception:
            rel_file = Path(raw_path).name or raw_path

        line_num = int(l_str)
        col_num = int(c_str)
        severity = "error" if code.startswith(("E9", "F82")) else "warning"

        diagnostics.append({
            "file": rel_file,
            "line": max(1, line_num),
            "col": max(1, col_num),
            "end_line": max(1, line_num),
            "end_col": max(1, col_num + 5),
            "message": msg.strip(),
            "severity": severity,
            "rule_id": code,
            "source": "flake8",
        })

    return diagnostics


def run_project_lint(
    project_path: str,
    target_file: Optional[str] = None,
    scope: str = "file",
) -> Dict[str, Any]:
    """Jalankan linter untuk workspace atau berkas target."""
    root = Path(project_path).resolve()
    if not root.exists() or not root.is_dir():
        return {"success": True, "diagnostics": []}

    ext = ""
    target_rel = None
    if target_file:
        target_path_obj = Path(target_file)
        if not target_path_obj.is_absolute():
            target_path_obj = (root / target_file).resolve()
        else:
            target_path_obj = target_path_obj.resolve()

        ext = target_path_obj.suffix.lower()
        try:
            target_rel = str(target_path_obj.relative_to(root))
        except Exception:
            target_rel = str(target_path_obj)

    if (scope == "file" and ext in _JS_EXTENSIONS) or (scope == "workspace" and (root / "package.json").exists()):
        eslint_bin = _find_eslint_binary(root)
        if eslint_bin:
            cmd = [eslint_bin, "-f", "json"]
            if scope == "file" and target_rel:
                cmd.append(target_rel)
            else:
                cmd.append(".")
            proc = _run_cmd(cmd, cwd=root)
            if proc is not None:
                diags = _parse_eslint_json(proc.stdout, root)
                return {"success": True, "diagnostics": diags}

    if (scope == "file" and ext in _PY_EXTENSIONS) or (scope == "workspace" and ((root / "pyproject.toml").exists() or (root / "requirements.txt").exists())):
        ruff_bin = _find_ruff_binary(root)
        if ruff_bin:
            cmd = [ruff_bin, "check", "--output-format", "json"]
            if scope == "file" and target_rel:
                cmd.append(target_rel)
            else:
                cmd.append(".")
            proc = _run_cmd(cmd, cwd=root)
            if proc is not None:
                diags = _parse_ruff_json(proc.stdout, root)
                return {"success": True, "diagnostics": diags}

        flake8_bin = _find_flake8_binary(root)
        if flake8_bin:
            cmd = [flake8_bin]
            if scope == "file" and target_rel:
                cmd.append(target_rel)
            else:
                cmd.append(".")
            proc = _run_cmd(cmd, cwd=root)
            if proc is not None:
                diags = _parse_flake8_output(proc.stdout, root)
                return {"success": True, "diagnostics": diags}

    return {"success": True, "diagnostics": []}
