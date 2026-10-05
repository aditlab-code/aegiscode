"""Unit tests untuk semantic chunker kode (Phase 2.1)."""

from pathlib import Path

from agent_ai.repointel.semantic.chunker import (
    MAX_CHUNK_CHARS,
    CodeChunk,
    _match_braces,
    chunk_file,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "mock_repo"


def test_chunk_empty_source():
    assert chunk_file("empty.py", "python", "") == []
    assert chunk_file("empty.py", "python", "   \n\t  ") == []


def test_chunk_python_billing():
    source = (FIXTURES_DIR / "billing.py").read_text(encoding="utf-8")
    chunks = chunk_file("billing.py", "python", source)

    symbols = [c.symbol for c in chunks]
    assert "InvoiceService" in symbols
    assert "InvoiceService.calculate_total" in symbols
    assert "InvoiceService.validate_invoice" in symbols

    # Periksa chunk header kelas
    class_header = next(c for c in chunks if c.symbol == "InvoiceService")
    assert class_header.kind == "class"
    assert "class InvoiceService:" in class_header.text
    # Header tidak memuat body dari calculate_total
    assert "subtotal = sum(" not in class_header.text

    # Periksa method calculate_total
    calc_method = next(c for c in chunks if c.symbol == "InvoiceService.calculate_total")
    assert calc_method.kind == "method"
    assert "def calculate_total(" in calc_method.text
    assert "return round(total, 2)" in calc_method.text
    assert calc_method.start_line < calc_method.end_line

    # Periksa pemotongan fungsi raksasa generate_extended_audit_log
    audit_parts = [c for c in chunks if c.symbol and "generate_extended_audit_log" in c.symbol]
    assert len(audit_parts) >= 2
    for part in audit_parts:
        assert len(part.text) <= MAX_CHUNK_CHARS
        assert part.start_line <= part.end_line


def test_chunk_jsts_utils_and_api():
    js_source = (FIXTURES_DIR / "utils.js").read_text(encoding="utf-8")
    js_chunks = chunk_file("utils.js", "javascript", js_source)

    symbols = [c.symbol for c in js_chunks]
    assert "formatCurrency" in symbols
    assert "parseToken" in symbols

    fmt_chunk = next(c for c in js_chunks if c.symbol == "formatCurrency")
    assert "function formatCurrency" in fmt_chunk.text
    assert "return `${prefix}" in fmt_chunk.text

    # TypeScript test
    ts_source = (FIXTURES_DIR / "api.ts").read_text(encoding="utf-8")
    ts_chunks = chunk_file("api.ts", "typescript", ts_source)
    ts_symbols = [c.symbol for c in ts_chunks]
    assert "ApiClient" in ts_symbols or "fetchData" in ts_symbols


def test_match_braces_handles_strings_and_comments():
    code = '{\n    // comment with }\n    /* block with } */\n    const s = "string with }";\n    const t = `template with }`;\n    return 42;\n}'
    end_idx = _match_braces(code, 0)
    assert end_idx == len(code)
    assert code[end_idx - 1] == "}"


def test_chunk_broken_python_syntax_fallback():
    source = (FIXTURES_DIR / "broken.py").read_text(encoding="utf-8")
    # File dengan syntax error tidak boleh melempar exception, melainkan jatuh ke fallback chunk
    chunks = chunk_file("broken.py", "python", source)
    assert len(chunks) >= 1
    assert chunks[0].kind == "module"
    assert "unclosed_function" in chunks[0].text


def test_code_chunk_contextual_text():
    chunk = CodeChunk(
        path="src/service.py",
        language="python",
        symbol="Service.run",
        kind="method",
        start_line=10,
        end_line=25,
        text="def run(): pass",
    )
    contextual = chunk.contextual_text()
    assert contextual.startswith("# path: src/service.py | symbol: Service.run | kind: method\n")
    assert "def run(): pass" in contextual
