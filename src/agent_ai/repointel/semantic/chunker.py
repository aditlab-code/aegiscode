"""Mesin chunking berbasis AST dan struktur kode untuk pencarian semantik.

Mendukung pembagian kode Python via AST stdlib, JavaScript/TypeScript via
brace-matching, dan fallback cerdas LangChain RecursiveCharacterTextSplitter.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class CodeChunk:
    """Representasi satu potongan kode yang terstruktur untuk di-vektorisasi.

    Attributes:
        path: Path relatif berkas sumber terhadap workspace root.
        language: Bahasa pemrograman (python, javascript, typescript, dll).
        symbol: Nama simbol terkait (mis. class atau Class.method), opsional.
        kind: Jenis simbol (class, method, function, module, dll).
        start_line: Nomor baris awal (1-based, inklusif).
        end_line: Nomor baris akhir (1-based, inklusif).
        text: Isi kode dari potongan tersebut (tanpa prefix kontekstual).
    """

    path: str
    language: str
    symbol: Optional[str]
    kind: Optional[str]
    start_line: int
    end_line: int
    text: str

    def contextual_text(self) -> str:
        """Mengembalikan teks dengan header konteks simbolik untuk embedding."""
        parts = [f"# path: {self.path}"]
        if self.symbol:
            parts.append(f"symbol: {self.symbol}")
        if self.kind:
            parts.append(f"kind: {self.kind}")
        header = " | ".join(parts)
        return f"{header}\n{self.text}"


# Batas ukuran potongan sebelum dipecah lebih lanjut: ~450 token (~1.800 karakter).
MAX_CHUNK_CHARS = 1800
CHUNK_OVERLAP_CHARS = 150

# Regex untuk pencarian deklarasi fungsi dan kelas JS/TS
_JS_CLASS_RE = re.compile(
    r"^\s*(?:export\s+|default\s+)*(?:class|interface)\s+([A-Za-z_]\w*)",
    re.MULTILINE,
)
_JS_FUNC_RE = re.compile(
    r"^\s*(?:export\s+|default\s+|async\s+)*function\s*([A-Za-z_]\w*)\s*\([^)]*\)",
    re.MULTILINE,
)
_JS_METHOD_OR_ARROW_RE = re.compile(
    r"^\s*(?:export\s+|default\s+)*(?:(?:const|let|var)\s+)?([A-Za-z_]\w*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>",
    re.MULTILINE,
)



def _line_of(source: str, index: int) -> int:
    """Hitung nomor baris 1-based dari indeks karakter."""
    return source.count("\n", 0, index) + 1


def _match_braces(source: str, start_brace_index: int) -> int:
    """Temukan posisi indeks karakter penutup '}' dari '{' dengan mengabaikan komentar dan string.

    Mengembalikan indeks akhir (inklusif penutup '}') atau -1 bila tidak seimbang.
    """
    length = len(source)
    if start_brace_index >= length or source[start_brace_index] != "{":
        return -1

    depth = 0
    i = start_brace_index

    in_single_quote = False
    in_double_quote = False
    in_backtick = False
    in_line_comment = False
    in_block_comment = False

    while i < length:
        char = source[i]
        next_char = source[i + 1] if i + 1 < length else ""

        # Tangani status komentar
        if in_line_comment:
            if char == "\n":
                in_line_comment = False
            i += 1
            continue

        if in_block_comment:
            if char == "*" and next_char == "/":
                in_block_comment = False
                i += 2
                continue
            i += 1
            continue

        # Tangani status string / escape
        if in_single_quote:
            if char == "\\" and i + 1 < length:
                i += 2
                continue
            if char == "'":
                in_single_quote = False
            i += 1
            continue

        if in_double_quote:
            if char == "\\" and i + 1 < length:
                i += 2
                continue
            if char == '"':
                in_double_quote = False
            i += 1
            continue

        if in_backtick:
            if char == "\\" and i + 1 < length:
                i += 2
                continue
            if char == "`":
                in_backtick = False
            i += 1
            continue

        # Periksa inisiasi komentar
        if char == "/" and next_char == "/":
            in_line_comment = True
            i += 2
            continue
        if char == "/" and next_char == "*":
            in_block_comment = True
            i += 2
            continue

        # Periksa inisiasi string
        if char == "'":
            in_single_quote = True
            i += 1
            continue
        if char == '"':
            in_double_quote = True
            i += 1
            continue
        if char == "`":
            in_backtick = True
            i += 1
            continue

        # Hitung kurung kurawal
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return i + 1

        i += 1

    return -1


def _extract_lines(lines: List[str], start_line: int, end_line: int) -> str:
    """Ambil baris 1-based inklusif dari list baris teks."""
    s = max(0, start_line - 1)
    e = min(len(lines), end_line)
    return "\n".join(lines[s:e])


def _split_oversized_chunk(chunk: CodeChunk) -> List[CodeChunk]:
    """Pecah chunk yang melebihi batas ukuran secara cerdas dengan mempertahankan nomor baris."""
    if len(chunk.text) <= MAX_CHUNK_CHARS:
        return [chunk]

    sub_texts: List[str] = []
    # Coba gunakan LangChain RecursiveCharacterTextSplitter bila tersedia
    try:
        from langchain_text_splitters import Language, RecursiveCharacterTextSplitter

        lang_map = {
            "python": Language.PYTHON,
            "javascript": Language.JS,
            "typescript": Language.TS,
        }
        target_lang = lang_map.get(chunk.language.lower())
        if target_lang is not None:
            splitter = RecursiveCharacterTextSplitter.from_language(
                language=target_lang,
                chunk_size=MAX_CHUNK_CHARS,
                chunk_overlap=CHUNK_OVERLAP_CHARS,
            )
        else:
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=MAX_CHUNK_CHARS,
                chunk_overlap=CHUNK_OVERLAP_CHARS,
            )
        sub_texts = splitter.split_text(chunk.text)
    except Exception:
        # Fallback pemotongan berbasis baris manual tanpa dependensi
        lines = chunk.text.split("\n")
        current: List[str] = []
        current_len = 0
        for line in lines:
            if current and (current_len + len(line) > MAX_CHUNK_CHARS):
                sub_texts.append("\n".join(current))
                # Ambil beberapa baris terakhir sebagai overlap
                current = current[-2:] if len(current) >= 2 else []
                current_len = sum(len(x) + 1 for x in current)
            current.append(line)
            current_len += len(line) + 1
        if current:
            sub_texts.append("\n".join(current))

    if not sub_texts:
        return [chunk]

    # Hitung estimasi nomor baris untuk tiap sub-potongan
    results: List[CodeChunk] = []
    current_line = chunk.start_line
    for i, sub in enumerate(sub_texts):
        sub_lines = max(1, sub.count("\n") + 1)
        sub_end = min(chunk.end_line, current_line + sub_lines - 1)
        sub_symbol = f"{chunk.symbol}[part {i + 1}]" if chunk.symbol else None
        results.append(
            CodeChunk(
                path=chunk.path,
                language=chunk.language,
                symbol=sub_symbol,
                kind=chunk.kind,
                start_line=current_line,
                end_line=sub_end,
                text=sub,
            )
        )
        # Geser baris maju (dengan estimasi overlap)
        step = max(1, sub_lines - 2 if len(sub_texts) > 1 else sub_lines)
        current_line = min(chunk.end_line, current_line + step)

    return results


def _chunk_python(path: str, source: str) -> List[CodeChunk]:
    """Chunking kode Python berbasis AST."""
    chunks: List[CodeChunk] = []
    lines = source.splitlines()

    try:
        tree = ast.parse(source)
    except SyntaxError:
        # Jika file korup / syntax error, gunakan fallback pemotongan teks penuh
        fallback = CodeChunk(
            path=path,
            language="python",
            symbol=None,
            kind="module",
            start_line=1,
            end_line=len(lines) or 1,
            text=source,
        )
        return _split_oversized_chunk(fallback)

    covered_line_ranges: List[Tuple[int, int]] = []

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            class_name = node.name
            methods = [
                c for c in node.body if isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]

            # 1. Chunk header kelas (dari awal class hingga sebelum method pertama)
            first_method_line = (
                methods[0].lineno if methods else (getattr(node, "end_lineno", None) or node.lineno)
            )
            header_end = (
                (first_method_line - 1)
                if (methods and first_method_line > node.lineno)
                else (getattr(node, "end_lineno", None) or node.lineno)
            )
            header_text = _extract_lines(lines, node.lineno, header_end)
            if header_text.strip():
                chunks.append(
                    CodeChunk(
                        path=path,
                        language="python",
                        symbol=class_name,
                        kind="class",
                        start_line=node.lineno,
                        end_line=header_end,
                        text=header_text,
                    )
                )

            # 2. Chunk masing-masing method
            for m in methods:
                # Perhitungkan decorator bila ada
                start = m.decorator_list[0].lineno if m.decorator_list else m.lineno
                end = getattr(m, "end_lineno", None) or m.lineno
                method_text = _extract_lines(lines, start, end)
                chunks.append(
                    CodeChunk(
                        path=path,
                        language="python",
                        symbol=f"{class_name}.{m.name}",
                        kind="method",
                        start_line=start,
                        end_line=end,
                        text=method_text,
                    )
                )

            class_end = getattr(node, "end_lineno", None) or node.lineno
            covered_line_ranges.append((node.lineno, class_end))

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start = node.decorator_list[0].lineno if node.decorator_list else node.lineno
            end = getattr(node, "end_lineno", None) or node.lineno
            func_text = _extract_lines(lines, start, end)
            chunks.append(
                CodeChunk(
                    path=path,
                    language="python",
                    symbol=node.name,
                    kind="function",
                    start_line=start,
                    end_line=end,
                    text=func_text,
                )
            )
            covered_line_ranges.append((start, end))

    # Bila tidak ada class/function yang ditemukan (mis. file konfigurasi atau modul script),
    # kembalikan chunk modul
    if not chunks:
        mod_chunk = CodeChunk(
            path=path,
            language="python",
            symbol=None,
            kind="module",
            start_line=1,
            end_line=len(lines) or 1,
            text=source,
        )
        return _split_oversized_chunk(mod_chunk)

    # Pecah setiap chunk yang melebihi batas token
    refined: List[CodeChunk] = []
    for c in chunks:
        refined.extend(_split_oversized_chunk(c))

    return refined


def _chunk_jsts(path: str, language: str, source: str) -> List[CodeChunk]:
    """Chunking kode JavaScript / TypeScript dengan regex + brace matching."""
    chunks: List[CodeChunk] = []
    lines = source.splitlines()

    # Cari semua kemungkinan kurung buka dari deklarasi class atau function
    candidates: List[Tuple[int, str, str]] = []  # (start_index, symbol_name, kind)

    for m in _JS_CLASS_RE.finditer(source):
        candidates.append((m.start(), m.group(1), "class"))

    for m in _JS_FUNC_RE.finditer(source):
        candidates.append((m.start(), m.group(1), "function"))

    for m in _JS_METHOD_OR_ARROW_RE.finditer(source):
        candidates.append((m.start(), m.group(1), "function"))

    # Urutkan berdasarkan kemunculan indeks
    candidates.sort(key=lambda x: x[0])

    for start_idx, name, kind in candidates:
        brace_pos = source.find("{", start_idx)
        if brace_pos == -1 or brace_pos - start_idx > 300:
            continue
        end_idx = _match_braces(source, brace_pos)
        if end_idx != -1:
            start_line = _line_of(source, start_idx)
            end_line = _line_of(source, end_idx)
            snippet = source[start_idx:end_idx].strip()
            if snippet:
                chunks.append(
                    CodeChunk(
                        path=path,
                        language=language,
                        symbol=name,
                        kind=kind,
                        start_line=start_line,
                        end_line=end_line,
                        text=snippet,
                    )
                )

    if not chunks:
        fallback = CodeChunk(
            path=path,
            language=language,
            symbol=None,
            kind="module",
            start_line=1,
            end_line=len(lines) or 1,
            text=source,
        )
        return _split_oversized_chunk(fallback)

    refined: List[CodeChunk] = []
    for c in chunks:
        refined.extend(_split_oversized_chunk(c))

    return refined


def chunk_file(path: str, language: str, source: str) -> List[CodeChunk]:
    """Potong berkas kode menjadi daftar CodeChunk yang semantik dan terstruktur.

    Args:
        path: Path relatif berkas.
        language: Nama bahasa (mis. 'python', 'javascript', 'typescript').
        source: Isi teks berkas sumber.
    """
    if not source.strip():
        return []

    lang = language.lower().strip()
    if lang == "python":
        return _chunk_python(path, source)
    if lang in ("javascript", "typescript", "js", "ts", "jsx", "tsx"):
        return _chunk_jsts(path, lang, source)

    # Bahasa generic lainnya: langsung potong sesuai batas token
    fallback = CodeChunk(
        path=path,
        language=language,
        symbol=None,
        kind="file",
        start_line=1,
        end_line=source.count("\n") + 1,
        text=source,
    )
    return _split_oversized_chunk(fallback)


__all__ = ["CodeChunk", "chunk_file", "MAX_CHUNK_CHARS", "CHUNK_OVERLAP_CHARS"]
