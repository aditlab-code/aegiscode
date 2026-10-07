"""Pengujian Universal Linter Runner (tests/test_linter_service.py)."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from api.linter import (
    _parse_eslint_json,
    _parse_ruff_json,
    _parse_flake8_output,
    run_project_lint,
)


def test_parse_eslint_json(tmp_path: Path):
    eslint_payload = [
        {
            "filePath": str(tmp_path / "src" / "app.js"),
            "messages": [
                {
                    "ruleId": "no-unused-vars",
                    "severity": 2,
                    "message": "'x' is defined but never used.",
                    "line": 10,
                    "column": 5,
                    "endLine": 10,
                    "endColumn": 6,
                },
                {
                    "ruleId": "prefer-const",
                    "severity": 1,
                    "message": "'y' is never reassigned. Use 'const' instead.",
                    "line": 12,
                    "column": 3,
                },
            ],
        }
    ]
    raw_json = json.dumps(eslint_payload)
    diags = _parse_eslint_json(raw_json, tmp_path)

    assert len(diags) == 2
    assert diags[0]["rule_id"] == "no-unused-vars"
    assert diags[0]["severity"] == "error"
    assert diags[0]["line"] == 10
    assert diags[0]["col"] == 5
    assert diags[0]["source"] == "eslint"
    assert diags[1]["severity"] == "warning"


def test_parse_ruff_json(tmp_path: Path):
    ruff_payload = [
        {
            "code": "F401",
            "message": "`os` imported but unused",
            "location": {"row": 1, "column": 8},
            "end_location": {"row": 1, "column": 10},
            "filename": str(tmp_path / "server.py"),
        },
        {
            "code": "E999",
            "message": "SyntaxError: invalid syntax",
            "location": {"row": 5, "column": 1},
            "end_location": {"row": 5, "column": 2},
            "filename": str(tmp_path / "server.py"),
        },
    ]
    raw_json = json.dumps(ruff_payload)
    diags = _parse_ruff_json(raw_json, tmp_path)

    assert len(diags) == 2
    assert diags[0]["rule_id"] == "F401"
    assert diags[0]["severity"] == "warning"
    assert diags[0]["line"] == 1
    assert diags[0]["source"] == "ruff"
    assert diags[1]["rule_id"] == "E999"
    assert diags[1]["severity"] == "error"


def test_parse_flake8_output(tmp_path: Path):
    output = f"{tmp_path}/app.py:14:5: E999 SyntaxError: invalid syntax\n{tmp_path}/app.py:20:1: W293 blank line contains whitespace"
    diags = _parse_flake8_output(output, tmp_path)

    assert len(diags) == 2
    assert diags[0]["rule_id"] == "E999"
    assert diags[0]["severity"] == "error"
    assert diags[0]["line"] == 14
    assert diags[1]["rule_id"] == "W293"
    assert diags[1]["severity"] == "warning"


def test_run_project_lint_unsupported_file(tmp_path: Path):
    res = run_project_lint(str(tmp_path), target_file="notes.txt", scope="file")
    assert res == {"success": True, "diagnostics": []}


def test_run_project_lint_missing_binary(tmp_path: Path):
    py_file = tmp_path / "test.py"
    py_file.write_text("x = 1\n", encoding="utf-8")
    with patch("api.linter._find_ruff_binary", return_value=None), \
         patch("api.linter._find_flake8_binary", return_value=None):
        res = run_project_lint(str(tmp_path), target_file=str(py_file), scope="file")
        assert res == {"success": True, "diagnostics": []}
