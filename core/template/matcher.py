from dataclasses import dataclass
from typing import Dict, List, Optional

from core.logger import log_call
from core.template.config import BuiltinColumn, Template, TemplateColumn


@dataclass
class ColumnMatch:
    """单个模板列的匹配结果。"""
    template_col: TemplateColumn
    source_col: Optional[str]   # 匹配到的源表列名；未匹配为 None
    status: str                 # "manual" | "exact" | "alias" | "none"


def _find_source(
    headers: List[str], stripped_headers: List[str], used: set, predicate,
) -> Optional[str]:
    """在未占用的源列中查找首个满足条件的列，返回原始列名。"""
    for orig, stripped in zip(headers, stripped_headers):
        if stripped in used:
            continue
        if predicate(stripped):
            return orig
    return None


@log_call("core.template.matcher", log_args=True, log_result=False)
def match_columns(
    headers: List[str],
    template: Template,
    builtin_columns: List[BuiltinColumn],
    manual_map: Optional[Dict[str, str]] = None,
) -> List[ColumnMatch]:
    """按优先级匹配模板列与源表列（纯函数）：manual > exact > alias > none。"""
    manual_map = manual_map or {}
    alias_map = {col.key: col.aliases for col in builtin_columns}
    stripped_headers = [h.strip() for h in headers]
    used: set = set()
    matches: List[ColumnMatch] = []

    for tcol in template.columns:
        if tcol.key in manual_map:
            # 手动指定：采用指定值（可为空字符串表示不映射）
            src = manual_map[tcol.key]
            if src:
                used.add(src.strip())
            matches.append(ColumnMatch(tcol, src or None, "manual"))
            continue

        target = _find_source(
            headers, stripped_headers, used,
            lambda s: s == tcol.name,
        )
        if target is not None:
            used.add(target.strip())
            matches.append(ColumnMatch(tcol, target, "exact"))
            continue

        aliases = alias_map.get(tcol.key, [])
        target = _find_source(
            headers, stripped_headers, used,
            lambda s: s in aliases,
        )
        if target is not None:
            used.add(target.strip())
            matches.append(ColumnMatch(tcol, target, "alias"))
            continue

        matches.append(ColumnMatch(tcol, None, "none"))
    return matches
