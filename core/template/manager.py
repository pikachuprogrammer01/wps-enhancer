from pathlib import Path
from typing import Dict, List, Optional

from core.exceptions import TemplateError
from core.logger import log_call
from core.template import store
from core.template.config import BuiltinColumn, Template, TemplateColumn


class TemplateManager:
    """模板管理器：模板 CRUD 编排与命名规则（依赖通过参数注入）。"""

    def __init__(self, templates_dir: Path, builtin_columns: List[BuiltinColumn]) -> None:
        self._templates_dir = templates_dir
        self._builtin_columns = builtin_columns

    @log_call("core.template.manager")
    def list_templates(self) -> List[Template]:
        """返回全部模板（按名称排序）。"""
        return store.list_templates(self._templates_dir)

    @log_call("core.template.manager")
    def create(
        self, name: str, columns: List[TemplateColumn],
        mappings: Optional[Dict[str, str]] = None,
    ) -> Template:
        """创建新模板（名称校验 + 重名自动加序号，可带建议映射）。"""
        cleaned = self._validate_name(name)
        final_name = self._unique_name(cleaned)
        template = Template(
            name=final_name, columns=columns,
            mappings=dict(mappings) if mappings else {},
        )
        store.save_template(template, self._template_path(final_name))
        return template

    @log_call("core.template.manager")
    def create_from_headers(self, name: str, headers: List[str]) -> Template:
        """从表头列表创建模板（自动识别内置列语义 key）。"""
        columns: List[TemplateColumn] = []
        custom_index = 1
        for header in headers:
            stripped = header.strip()
            if not stripped:
                continue
            key = self._detect_key(stripped)
            if key is None:
                key = f"custom_{custom_index}"
                custom_index += 1
            columns.append(TemplateColumn(key=key, name=stripped))
        if not columns:
            raise TemplateError("表头为空，无法创建模板")
        return self.create(name, columns)

    @log_call("core.template.manager")
    def rename(self, old_name: str, new_name: str) -> Template:
        """重命名模板（新名唯一化后保存新文件并删除旧文件）。"""
        cleaned = self._validate_name(new_name)
        old_path = self._template_path(old_name)
        if not old_path.exists():
            raise TemplateError(f"模板 '{old_name}' 不存在")
        template = store.load_template(old_path)
        if cleaned == old_name:
            return template  # 名称未变化，无操作
        final_name = self._unique_name(cleaned, exclude=old_name)
        template.name = final_name
        store.save_template(template, self._template_path(final_name))
        store.delete_template(old_path)
        return template

    @log_call("core.template.manager")
    def delete(self, name: str) -> None:
        """删除模板（文件不存在时抛 TemplateError）。"""
        path = self._template_path(name)
        if not path.exists():
            raise TemplateError(f"模板 '{name}' 不存在")
        store.delete_template(path)

    @log_call("core.template.manager")
    def update_columns(self, name: str, columns: List[TemplateColumn]) -> Template:
        """更新模板列定义（保持模板名与建议映射不变）。"""
        path = self._template_path(name)
        if not path.exists():
            raise TemplateError(f"模板 '{name}' 不存在")
        template = store.load_template(path)
        template.columns = columns
        store.save_template(template, path)
        return template

    def _template_path(self, name: str) -> Path:
        """返回模板名对应的文件路径。"""
        return self._templates_dir / f"{store.sanitize_filename(name)}.json"

    def _validate_name(self, name: str) -> str:
        """校验并清洗模板名（去除首尾空白，空名抛 TemplateError）。"""
        cleaned = name.strip()
        if not cleaned:
            raise TemplateError("模板名不能为空")
        return cleaned

    def _unique_name(self, base: str, exclude: Optional[str] = None) -> str:
        """生成不冲突的模板名（重名自动追加 _2、_3...，exclude 名视为可用）。"""
        if self._template_path(base).exists() and base != exclude:
            index = 2
            while self._template_path(f"{base}_{index}").exists():
                index += 1
            return f"{base}_{index}"
        return base

    def _detect_key(self, header: str) -> Optional[str]:
        """根据内置列 label 与别名识别表头的语义 key。"""
        for col in self._builtin_columns:
            if header == col.label or header in col.aliases:
                return col.key
        return None
