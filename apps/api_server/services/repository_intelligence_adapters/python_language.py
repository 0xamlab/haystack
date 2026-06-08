from __future__ import annotations

import ast
from collections import defaultdict
from collections.abc import Callable, Sequence
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = Callable[[str, Any], str]
ResolveImport = Callable[..., str | None]


def resolve_import(
    *,
    current_file: str,
    module: str | None,
    level: int,
    name: str | None,
    module_index: dict[str, str],
) -> str | None:
    if level > 0:
        parts = ast_to_module_parts(current_file)
        if level > 1:
            parts = parts[: max(0, len(parts) - (level - 1))]
        relative_parts = list(parts)
        if module:
            relative_parts.extend([part for part in module.split(".") if part])
        if name:
            relative_parts.append(name)
        candidate = ".".join(relative_parts)
        return module_index.get(candidate)
    candidates: list[str] = []
    if module:
        candidates.append(module)
    if name:
        candidates.append(name)
        if module:
            candidates.append(f"{module}.{name}")
    for candidate in candidates:
        target = module_index.get(candidate)
        if target is not None:
            return target
    return None


def ast_to_module_parts(current_file: str) -> tuple[str, ...]:
    return tuple(part for part in current_file.removesuffix(".py").split("/")[:-1] if part)


def _extract_imports(
    *,
    file_path: str,
    tree: ast.AST,
    module_index: dict[str, str],
    stable_identifier: StableIdentifier,
    resolve_import: ResolveImport,
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding]]:
    dependencies: list[_Dependency] = []
    import_bindings: dict[str, _ImportedSymbolBinding] = {}

    class Visitor(ast.NodeVisitor):
        def visit_Import(self, node: ast.Import) -> Any:
            for alias in node.names:
                target_file = module_index.get(alias.name)
                dependencies.append(
                    _Dependency(
                        dependency_edge_id=stable_identifier(
                            "dep",
                            {
                                "file_path": file_path,
                                "target": alias.name,
                                "line": node.lineno,
                            },
                        ),
                        source_file=file_path,
                        target_file=target_file,
                        target_symbol=alias.name,
                        dependency_type="imports",
                    )
                )
                alias_name = alias.asname or alias.name.split(".", 1)[0]
                import_bindings[alias_name] = _ImportedSymbolBinding(
                    alias=alias_name,
                    target_file=target_file,
                    target_names=(alias.name.split(".")[-1],),
                )

        def visit_ImportFrom(self, node: ast.ImportFrom) -> Any:
            for alias in node.names:
                target_file = resolve_import(
                    current_file=file_path,
                    module=node.module,
                    level=node.level,
                    name=alias.name if alias.name != "*" else None,
                    module_index=module_index,
                )
                target_symbol = alias.name if alias.name != "*" else node.module
                dependencies.append(
                    _Dependency(
                        dependency_edge_id=stable_identifier(
                            "dep",
                            {
                                "file_path": file_path,
                                "module": node.module,
                                "name": alias.name,
                                "level": node.level,
                                "line": node.lineno,
                            },
                        ),
                        source_file=file_path,
                        target_file=target_file,
                        target_symbol=target_symbol,
                        dependency_type="imports",
                    )
                )
                if alias.name == "*":
                    continue
                alias_name = alias.asname or alias.name
                import_bindings[alias_name] = _ImportedSymbolBinding(
                    alias=alias_name,
                    target_file=target_file,
                    target_names=(alias.name,),
                )

    Visitor().visit(tree)
    return tuple(dependencies), import_bindings


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import: ResolveImport,
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    tree = ast.parse(text, filename=file_path)
    dependencies, import_bindings = _extract_imports(
        file_path=file_path,
        tree=tree,
        module_index=module_index,
        stable_identifier=stable_identifier,
        resolve_import=resolve_import,
    )
    symbols: list[_Symbol] = []
    reference_candidates: dict[str, _SymbolReferenceCandidate] = {}
    symbols_by_name: dict[str, list[_Symbol]] = defaultdict(list)
    class_member_symbols: dict[str, dict[str, _Symbol]] = defaultdict(dict)
    parent_stack: list[str] = []
    class_stack: list[str] = []

    def _add_reference_candidate(
        *,
        source_symbol_id: str,
        target_symbol_id: str | None,
        target_file: str | None,
        target_names: Sequence[str],
    ) -> None:
        normalized_names = tuple(str(value) for value in target_names if str(value).strip())
        if target_symbol_id is None and target_file is None and not normalized_names:
            return
        edge_id = stable_identifier(
            "ref",
            {
                "source_symbol_id": source_symbol_id,
                "target_symbol_id": target_symbol_id,
                "target_file": target_file,
                "target_names": normalized_names,
                "type": "references_symbol",
            },
        )
        reference_candidates.setdefault(
            edge_id,
            _SymbolReferenceCandidate(
                reference_edge_id=edge_id,
                source_symbol_id=source_symbol_id,
                source_file=file_path,
                target_symbol_id=target_symbol_id,
                target_file=target_file,
                target_names=normalized_names,
                reference_type="references_symbol",
            ),
        )

    class Visitor(ast.NodeVisitor):
        def visit(self, node: ast.AST) -> Any:
            current_symbol_id = parent_stack[-1] if parent_stack else None
            if current_symbol_id is not None:
                self._collect_symbol_references(node, current_symbol_id)
            return super().visit(node)

        def visit_ClassDef(self, node: ast.ClassDef) -> Any:
            symbol = _Symbol(
                symbol_id=stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "name": node.name,
                        "line": node.lineno,
                        "kind": "class",
                    },
                ),
                symbol_name=node.name,
                symbol_kind="class",
                start_line=node.lineno,
                end_line=getattr(node, "end_lineno", node.lineno),
                parent_symbol_id=parent_stack[-1] if parent_stack else None,
                signature=node.name,
            )
            symbols.append(symbol)
            symbols_by_name[symbol.symbol_name].append(symbol)
            parent_stack.append(symbol.symbol_id)
            class_stack.append(symbol.symbol_id)
            self.generic_visit(node)
            parent_stack.pop()
            class_stack.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
            self._visit_function(node, "function")

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
            self._visit_function(node, "async_function")

        def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef, kind: str) -> None:
            symbol = _Symbol(
                symbol_id=stable_identifier(
                    "sym",
                    {"file_path": file_path, "name": node.name, "line": node.lineno, "kind": kind},
                ),
                symbol_name=node.name,
                symbol_kind=kind,
                start_line=node.lineno,
                end_line=getattr(node, "end_lineno", node.lineno),
                parent_symbol_id=parent_stack[-1] if parent_stack else None,
                signature=node.name,
            )
            symbols.append(symbol)
            symbols_by_name[symbol.symbol_name].append(symbol)
            if class_stack and symbol.parent_symbol_id == class_stack[-1]:
                class_member_symbols[class_stack[-1]][symbol.symbol_name] = symbol
            parent_stack.append(symbol.symbol_id)
            self.generic_visit(node)
            parent_stack.pop()

        def _collect_symbol_references(self, node: ast.AST, source_symbol_id: str) -> None:
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                binding = import_bindings.get(node.id)
                if binding is not None:
                    _add_reference_candidate(
                        source_symbol_id=source_symbol_id,
                        target_symbol_id=None,
                        target_file=binding.target_file,
                        target_names=binding.target_names,
                    )
                    return
                for target_symbol in symbols_by_name.get(node.id, ()):
                    _add_reference_candidate(
                        source_symbol_id=source_symbol_id,
                        target_symbol_id=target_symbol.symbol_id,
                        target_file=file_path,
                        target_names=(target_symbol.symbol_name,),
                    )
                return
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.ctx, ast.Load)
                and isinstance(node.value, ast.Name)
                and node.value.id in {"self", "cls"}
                and class_stack
            ):
                class_symbol_id = class_stack[-1]
                target_symbol = class_member_symbols.get(class_symbol_id, {}).get(node.attr)
                if target_symbol is not None:
                    _add_reference_candidate(
                        source_symbol_id=source_symbol_id,
                        target_symbol_id=target_symbol.symbol_id,
                        target_file=file_path,
                        target_names=(target_symbol.symbol_name,),
                    )

    Visitor().visit(tree)
    return (
        tuple(symbols),
        dependencies,
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import: ResolveImport,
) -> tuple[_Dependency, ...]:
    tree = ast.parse(text, filename=file_path)
    dependencies, _ = _extract_imports(
        file_path=file_path,
        tree=tree,
        module_index=module_index,
        stable_identifier=stable_identifier,
        resolve_import=resolve_import,
    )
    return dependencies
