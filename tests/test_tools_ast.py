from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_memory_tool_module_is_valid_python_and_uses_plugin_imports():
    source = (ROOT / "tools" / "memory.py").read_text()
    tree = ast.parse(source)
    imports = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    froms = [
        node.module
        for node in imports
        if isinstance(node, ast.ImportFrom)
    ]
    assert "helpers.tool" in froms
    assert "usr.plugins.pixeltable_memory.helpers.runtime" in froms
    assert "usr.plugins.pixeltable_memory.helpers.store" in froms
    class_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
    assert "MemoryTool" in class_names
