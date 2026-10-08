"""AST and lightweight regex extractors for CodeGraph (stdlib only, workspace-agnostic)."""

from __future__ import annotations

import ast
import hashlib
import logging
import re
from pathlib import Path
from typing import Any, List, Optional, Tuple, Union

from agent_ai.codegraph.models import CodeSymbol, RelationType, SymbolRelation

logger = logging.getLogger(__name__)


def compute_content_hash(text: str) -> str:
    """Deterministic SHA-256 hash helper."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class PythonASTExtractor:
    """Extractor for Python source code using stdlib `ast`."""

    def extract(self, code: str, rel_path: str) -> Tuple[List[CodeSymbol], List[SymbolRelation]]:
        symbols: List[CodeSymbol] = []
        relations: List[SymbolRelation] = []

        try:
            tree = ast.parse(code, filename=rel_path)
        except SyntaxError as exc:
            logger.warning("SyntaxError parsing %s: %s (skipped)", rel_path, exc)
            return symbols, relations

        lines = code.splitlines()

        # Root module symbol (satisfies foreign key for module-level imports)
        symbols.append(
            CodeSymbol(
                id=f"{rel_path}::__module__",
                name=Path(rel_path).stem,
                type="module",
                file_path=rel_path,
                language="python",
                start_line=1,
                end_line=len(lines) if lines else 1,
                docstring=ast.get_docstring(tree),
                body_hash=compute_content_hash(code),
            )
        )

        # 1. Module-level imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    relations.append(
                        SymbolRelation(
                            source_id=f"{rel_path}::__module__",
                            target_name=alias.name,
                            relation_type=RelationType.IMPORTS,
                            file_path=rel_path,
                            line_number=node.lineno,
                        )
                    )
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                for alias in node.names:
                    target = f"{mod}.{alias.name}" if mod else alias.name
                    relations.append(
                        SymbolRelation(
                            source_id=f"{rel_path}::__module__",
                            target_name=target,
                            relation_type=RelationType.IMPORTS,
                            file_path=rel_path,
                            line_number=node.lineno,
                        )
                    )

        # 2. Top-level and nested classes / functions
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                cls_symbols, cls_relations = self._extract_class(node, rel_path, lines)
                symbols.extend(cls_symbols)
                relations.extend(cls_relations)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fn_sym, fn_rels = self._extract_function(node, rel_path, lines, parent_class=None)
                symbols.append(fn_sym)
                relations.extend(fn_rels)

        return symbols, relations

    def _extract_class(
        self, node: ast.ClassDef, rel_path: str, lines: List[str]
    ) -> Tuple[List[CodeSymbol], List[SymbolRelation]]:
        symbols: List[CodeSymbol] = []
        relations: List[SymbolRelation] = []

        class_id = f"{rel_path}::{node.name}"
        start_line = node.lineno
        end_line = getattr(node, "end_lineno", node.lineno)
        body_text = "\n".join(lines[start_line - 1 : end_line])
        docstring = ast.get_docstring(node)

        # Class symbol
        symbols.append(
            CodeSymbol(
                id=class_id,
                name=node.name,
                type="class",
                file_path=rel_path,
                language="python",
                start_line=start_line,
                end_line=end_line,
                body_hash=compute_content_hash(body_text),
                docstring=docstring,
            )
        )

        # Base inheritance
        for base in node.bases:
            base_name = self._node_to_name(base)
            if base_name:
                relations.append(
                    SymbolRelation(
                        source_id=class_id,
                        target_name=base_name,
                        relation_type=RelationType.EXTENDS,
                        file_path=rel_path,
                        line_number=base.lineno,
                    )
                )

        # Methods inside class
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                m_sym, m_rels = self._extract_function(item, rel_path, lines, parent_class=node.name)
                symbols.append(m_sym)
                relations.extend(m_rels)
                # Relation: Class DEFINES Method
                relations.append(
                    SymbolRelation(
                        source_id=class_id,
                        target_name=m_sym.name,
                        relation_type=RelationType.DEFINES,
                        file_path=rel_path,
                        line_number=item.lineno,
                    )
                )

        return symbols, relations

    def _extract_function(
        self,
        node: Union[ast.FunctionDef, ast.AsyncFunctionDef],
        rel_path: str,
        lines: List[str],
        parent_class: Optional[str] = None,
    ) -> Tuple[CodeSymbol, List[SymbolRelation]]:
        relations: List[SymbolRelation] = []

        name = node.name
        full_name = f"{parent_class}.{name}" if parent_class else name
        sym_type = "method" if parent_class else "function"
        fn_id = f"{rel_path}::{full_name}"

        start_line = node.lineno
        end_line = getattr(node, "end_lineno", node.lineno)
        body_text = "\n".join(lines[start_line - 1 : end_line])
        docstring = ast.get_docstring(node)
        signature = self._extract_signature(node)

        # Detect API Endpoint Decorator
        is_endpoint = False
        for dec in node.decorator_list:
            dec_str = self._node_to_name(dec) or ""
            if any(k in dec_str.lower() for k in ("get", "post", "put", "delete", "route", "api_view")):
                is_endpoint = True
                endpoint_target = dec_str
                if isinstance(dec, ast.Call) and dec.args:
                    arg_name = self._node_to_name(dec.args[0])
                    if arg_name:
                        endpoint_target = f"{dec_str}:{arg_name}"
                relations.append(
                    SymbolRelation(
                        source_id=fn_id,
                        target_name=endpoint_target,
                        relation_type=RelationType.API_ENDPOINT,
                        file_path=rel_path,
                        line_number=dec.lineno,
                    )
                )

        sym = CodeSymbol(
            id=fn_id,
            name=name,
            type="endpoint" if is_endpoint else sym_type,
            file_path=rel_path,
            language="python",
            start_line=start_line,
            end_line=end_line,
            signature=signature,
            docstring=docstring,
            body_hash=compute_content_hash(body_text),
        )

        # Detect Function Calls inside function body
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call) and sub is not node:
                called_name = self._node_to_name(sub.func)
                if called_name:
                    relations.append(
                        SymbolRelation(
                            source_id=fn_id,
                            target_name=called_name,
                            relation_type=RelationType.CALLS,
                            file_path=rel_path,
                            line_number=sub.lineno,
                        )
                    )

        return sym, relations

    def _extract_signature(self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> str:
        args_parts = []
        for a in node.args.args:
            arg_str = a.arg
            if a.annotation:
                ann = self._node_to_name(a.annotation)
                if ann:
                    arg_str += f": {ann}"
            args_parts.append(arg_str)
        ret_part = ""
        if node.returns:
            ret_name = self._node_to_name(node.returns)
            if ret_name:
                ret_part = f" -> {ret_name}"
        return f"({', '.join(args_parts)}){ret_part}"

    def _node_to_name(self, node: ast.AST) -> Optional[str]:
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            val = self._node_to_name(node.value)
            return f"{val}.{node.attr}" if val else node.attr
        elif isinstance(node, ast.Call):
            return self._node_to_name(node.func)
        elif isinstance(node, ast.Constant):
            return str(node.value)
        return None


class LightweightRegexExtractor:
    """Fast regex scanner for JavaScript, TypeScript, and Vue components."""

    FN_PATTERN = re.compile(
        r"(?:export\s+)?(?:async\s+)?function\s+([A-Za-z0-9_$]+)\s*\((.*?)\)|"
        r"(?:export\s+)?(?:const|let|var)\s+([A-Za-z0-9_$]+)\s*=\s*(?:async\s*)?\((.*?)\)\s*=>",
        re.MULTILINE,
    )
    CLASS_PATTERN = re.compile(
        r"(?:export\s+)?class\s+([A-Za-z0-9_$]+)(?:\s+extends\s+([A-Za-z0-9_$]+))?",
        re.MULTILINE,
    )
    IMPORT_PATTERN = re.compile(
        r"import\s+(?:\{([^}]+)\}|([A-Za-z0-9_$*]+))\s+from\s+['\"]([^'\"]+)['\"]|"
        r"(?:const|let|var)\s+(?:\{([^}]+)\}|([A-Za-z0-9_$]+))\s*=\s*require\(['\"]([^'\"]+)['\"]\)",
        re.MULTILINE,
    )
    API_CALL_PATTERN = re.compile(
        r"(?:fetch|axios\.(?:get|post|put|delete)|apiClient\.(?:get|post|put|delete))\s*\(\s*['\"`]([^'\"`]+)['\"`]",
        re.MULTILINE,
    )

    def extract(self, code: str, rel_path: str) -> Tuple[List[CodeSymbol], List[SymbolRelation]]:
        symbols: List[CodeSymbol] = []
        relations: List[SymbolRelation] = []
        lang = "vue" if rel_path.endswith(".vue") else ("typescript" if rel_path.endswith(".ts") else "javascript")
        lines = code.splitlines()

        # Root module symbol (satisfies foreign key for module-level relations)
        symbols.append(
            CodeSymbol(
                id=f"{rel_path}::__module__",
                name=Path(rel_path).stem,
                type="module",
                file_path=rel_path,
                language=lang,
                start_line=1,
                end_line=len(lines) if lines else 1,
                body_hash=compute_content_hash(code),
            )
        )

        # Classes
        for m in self.CLASS_PATTERN.finditer(code):
            name = m.group(1)
            parent = m.group(2)
            line = code.count("\n", 0, m.start()) + 1
            cls_id = f"{rel_path}::{name}"
            symbols.append(
                CodeSymbol(
                    id=cls_id,
                    name=name,
                    type="class",
                    file_path=rel_path,
                    language=lang,
                    start_line=line,
                    end_line=line,
                    body_hash=compute_content_hash(m.group(0)),
                )
            )
            if parent:
                relations.append(
                    SymbolRelation(
                        source_id=cls_id,
                        target_name=parent,
                        relation_type=RelationType.EXTENDS,
                        file_path=rel_path,
                        line_number=line,
                    )
                )

        # Functions
        for m in self.FN_PATTERN.finditer(code):
            name = m.group(1) or m.group(3)
            sig_args = m.group(2) or m.group(4) or ""
            line = code.count("\n", 0, m.start()) + 1
            fn_id = f"{rel_path}::{name}"
            symbols.append(
                CodeSymbol(
                    id=fn_id,
                    name=name,
                    type="function",
                    file_path=rel_path,
                    language=lang,
                    start_line=line,
                    end_line=line,
                    signature=f"({sig_args.strip()})",
                    body_hash=compute_content_hash(m.group(0)),
                )
            )

        # Imports
        for m in self.IMPORT_PATTERN.finditer(code):
            mod = m.group(3) or m.group(6) or ""
            names = m.group(1) or m.group(2) or m.group(4) or m.group(5) or mod
            line = code.count("\n", 0, m.start()) + 1
            for raw_n in names.split(","):
                n = raw_n.strip().split(" as ")[-1].strip()
                if n:
                    relations.append(
                        SymbolRelation(
                            source_id=f"{rel_path}::__module__",
                            target_name=n,
                            relation_type=RelationType.IMPORTS,
                            file_path=rel_path,
                            line_number=line,
                        )
                    )

        # API Calls
        for m in self.API_CALL_PATTERN.finditer(code):
            endpoint = m.group(1)
            line = code.count("\n", 0, m.start()) + 1
            relations.append(
                SymbolRelation(
                    source_id=f"{rel_path}::__module__",
                    target_name=endpoint,
                    relation_type=RelationType.API_CALL,
                    file_path=rel_path,
                    line_number=line,
                )
            )

        return symbols, relations


def extract_file(
    file_path: Union[str, Path],
    project_root: Optional[Union[str, Path]] = None,
) -> Tuple[List[CodeSymbol], List[SymbolRelation]]:
    """Extract symbols and relations from a file in a workspace-agnostic manner."""
    p = Path(file_path).resolve()
    if not p.is_file():
        return [], []

    if project_root:
        root = Path(project_root).resolve()
        try:
            rel_path = str(p.relative_to(root))
        except ValueError:
            rel_path = p.name
    else:
        rel_path = p.name

    try:
        content = p.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        logger.warning("Failed to read %s: %s", p, exc)
        return [], []

    if p.suffix == ".py":
        extractor = PythonASTExtractor()
        return extractor.extract(content, rel_path)
    elif p.suffix in (".js", ".jsx", ".ts", ".tsx", ".vue"):
        extractor = LightweightRegexExtractor()
        return extractor.extract(content, rel_path)

    return [], []
