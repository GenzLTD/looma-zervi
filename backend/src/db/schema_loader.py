"""兼容壳：实现已搬进核（刀 5d，`src/thomas_core/db/schema_loader.py`）。

保留旧路径是因为宿主启动流程（`src/app.py`）与既有脚本/锚都在 `from src.db import schema_loader`。
产品→核 方向允许。

注意 `SCOPE_FILES` 是**同一个 dict 对象**（引用赋值，不是拷贝）—— `scripts/verify_schema_split.py`
的 E 例就地改写这个 dict 再还原，如果在壳里做副本，改写就落不到实现模块上。
"""
from src.thomas_core.db.schema_loader import (  # noqa: F401
    CORE_ANCHOR_TABLES,
    SCOPE_FILES,
    SchemaDriftError,
    core_ready,
    ensure_scope,
    file_version,
    is_empty,
    split_enabled,
    sql_text,
)
