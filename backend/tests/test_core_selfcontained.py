"""刀 5 总门禁：核的模块级 import 不许跨出 `src.thomas_core`（核自足性）。

口径：只看**模块级**（顶层）import —— 函数内的惰性 import 是刻意保留的逃生口，
且只允许出现在两个桥文件里（`hooks.py` / `brain.py`）。这条测试就是把 RFC §3 的
「core→产品面禁止」变成可执行断言，避免以后谁再顺手 `from src.agents... import` 把
独立发版 split 打回去。
"""
from __future__ import annotations

import ast
from pathlib import Path

CORE_DIR = Path(__file__).resolve().parents[1] / "src" / "thomas_core"

# 允许在**函数内**惰性 import 宿主实现的桥文件
LAZY_BRIDGES = {"hooks.py", "brain.py"}


def _module_imports(path: Path) -> list[tuple[int, str]]:
    # utf-8-sig：有核文件带 BOM（compliance_routes.py），utf-8 会让 ast.parse 报 U+FEFF
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    hits = []
    for node in tree.body:  # 只扫顶层
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name == "src" or a.name.startswith("src."):
                    hits.append((node.lineno, a.name))
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            mod = node.module or ""
            if mod == "src" or mod.startswith("src."):
                hits.append((node.lineno, mod))
    return hits


def _is_inside_core(mod: str) -> bool:
    return mod in ("src.thomas_core",) or mod.startswith("src.thomas_core.")


def test_core_has_no_module_level_host_imports():
    offenders = []
    for path in sorted(CORE_DIR.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        for lineno, mod in _module_imports(path):
            if not _is_inside_core(mod):
                offenders.append(f"{path.relative_to(CORE_DIR.parents[2])}:{lineno} → {mod}")
    assert offenders == [], "核出现模块级宿主 import（会让独立发版 split 后 import 失败）:\n" + "\n".join(offenders)


def test_lazy_host_imports_only_in_bridge_files():
    offenders = []
    for path in sorted(CORE_DIR.rglob("*.py")):
        if "__pycache__" in path.parts or path.name in LAZY_BRIDGES:
            continue
        # utf-8-sig：有核文件带 BOM（compliance_routes.py），utf-8 会让 ast.parse 报 U+FEFF
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 0:
                mod = node.module or ""
                if (mod == "src" or mod.startswith("src.")) and not _is_inside_core(mod):
                    offenders.append(f"{path.name}:{node.lineno} → {mod}")
            elif isinstance(node, ast.Import):
                for a in node.names:
                    if (a.name == "src" or a.name.startswith("src.")) and not _is_inside_core(a.name):
                        offenders.append(f"{path.name}:{node.lineno} → {a.name}")
    assert offenders == [], "宿主 import 只允许出现在 hooks.py / brain.py:\n" + "\n".join(offenders)
