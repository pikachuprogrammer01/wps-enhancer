import json
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List

from core.exceptions import FileReadError, TemplateError
from core.logger import log_call
from core.template.config import Template, TemplateColumn

TEMPLATE_FILE_VERSION = 2
_ILLEGAL_CHARS = '\\/:*?"<>|'


def sanitize_filename(name: str) -> str:
    """将模板名转换为安全文件名（非法字符替换为 _，空名返回 _）。"""
    for ch in _ILLEGAL_CHARS:
        name = name.replace(ch, "_")
    return name.strip() or "_"


def _columns_from_dict(raw_columns: object) -> List[TemplateColumn]:
    """从 JSON 原始数据构建 TemplateColumn 列表（未知键忽略，缺键用默认值）。"""
    columns: List[TemplateColumn] = []
    if not isinstance(raw_columns, list):
        return columns
    for raw in raw_columns:
        if not isinstance(raw, dict):
            continue
        columns.append(TemplateColumn(
            key=str(raw.get("key", "")),
            name=str(raw.get("name", "")),
            enabled=bool(raw.get("enabled", True)),
        ))
    return columns


@log_call("core.template.store", log_args=True, log_result=False)
def save_template(template: Template, path: Path) -> None:
    """将模板写入 JSON 文件（原子写入，先写临时文件再替换）。"""
    data = {
        "name": template.name,
        "version": TEMPLATE_FILE_VERSION,
        "columns": [asdict(col) for col in template.columns],
        "mappings": dict(template.mappings),
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8",
        )
        tmp_path.replace(path)
    except OSError as e:
        raise TemplateError(f"无法写入模板文件 '{path}'：{e}") from e


@log_call("core.template.store", log_args=True, log_result=False)
def load_template(path: Path) -> Template:
    """从 JSON 文件读取模板（损坏或缺失抛 FileReadError）。"""
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as e:
        raise FileReadError(f"无法读取模板文件 '{path}'：{e}") from e
    try:
        raw = json.loads(raw_text)
        name = str(raw.get("name", path.stem))
        columns = _columns_from_dict(raw.get("columns"))
        mappings_raw = raw.get("mappings")
        mappings = {
            str(k): str(v) for k, v in mappings_raw.items()
        } if isinstance(mappings_raw, dict) else {}
    except (json.JSONDecodeError, AttributeError) as e:
        raise FileReadError(f"模板文件 '{path}' 格式损坏：{e}") from e
    return Template(name=name, columns=columns, mappings=mappings)


@log_call("core.template.store")
def list_templates(templates_dir: Path) -> List[Template]:
    """扫描模板目录，返回全部模板（按名称排序；目录不存在返回空列表）。"""
    if not templates_dir.is_dir():
        return []
    templates: List[Template] = []
    for entry in sorted(templates_dir.glob("*.json")):
        try:
            templates.append(load_template(entry))
        except FileReadError:
            continue  # 单个模板损坏不影响其他模板加载
    templates.sort(key=lambda t: t.name)
    return templates


@log_call("core.template.store")
def delete_template(path: Path) -> None:
    """删除模板文件（文件不存在时幂等成功）。"""
    if not path.exists():
        return
    try:
        path.unlink()
    except OSError as e:
        raise TemplateError(f"无法删除模板文件 '{path}'：{e}") from e
