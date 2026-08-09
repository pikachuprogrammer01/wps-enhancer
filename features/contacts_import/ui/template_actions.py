"""模板管理流程（拆分自 panel.py：TemplateActionsMixin）。

新建/编辑/重命名/删除/从表头导入模板等对话框流程。
"""

from typing import Optional


from features.contacts_import.ui import base as _dlg
from core.settings import get_app_settings
from core.template import Template
from features.contacts_import.ui.base import _DEFAULT_MAPPING_NAME
from features.contacts_import.ui.base import _safe_slot
from ui.components.template_edit_dialog import TemplateEditDialog


class TemplateActionsMixin:
    """模板管理对话框流程（依赖 TemplateTableMixin 的渲染与选中方法）。"""

    @_safe_slot
    def _on_new_template(self) -> None:
        """打开新建模板对话框。"""
        self._open_template_editor(None)

    def _require_saved_template(self) -> bool:
        """检查当前是否为已保存的模板，默认映射时提示先创建并返回 False。"""
        if self._template is None or self._template.name == _DEFAULT_MAPPING_NAME:
            _dlg.QMessageBox.information(self, "提示", "当前为默认映射，请先创建模板")
            return False
        return True

    @_safe_slot
    def _on_edit_template(self) -> None:
        """打开编辑当前选中模板列对话框（兼容选中路径）。"""
        if not self._require_saved_template():
            return
        self._edit_template_by_name(self._template.name)

    def _edit_template_by_name(self, name: str) -> None:
        """按模板名打开编辑列对话框。"""
        manager = self._get_manager()
        template = next(
            (t for t in manager.list_templates() if t.name == name), None,
        )
        if template is None:
            return
        self._open_template_editor(template)

    @_safe_slot
    def _open_template_editor(self, template: Optional[Template]) -> None:
        """通用模板新建/编辑对话框流程。"""
        settings = get_app_settings()
        dialog = TemplateEditDialog(settings.builtin_columns, template, self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        edited = dialog.get_template()
        manager = self._get_manager()
        if template is None:
            manager.create(
                edited.name, edited.columns,
                source_format=self._source_format_family(self._file_path),
            )
        else:
            manager.update_columns(template.name, edited.columns)
        self._reload_templates()
        self._status_bar.show_success(
            f"模板 '{edited.name}' 已保存",
        )

    @_safe_slot
    def _on_import_template(self) -> None:
        """从当前源表表头一键创建模板。"""
        if self._sheet_data is None:
            _dlg.QMessageBox.information(self, "提示", "请先选择源文件")
            return
        name, ok = _dlg.QInputDialog.getText(self, "从表头创建模板", "模板名称：")
        if not ok or not name.strip():
            return
        template = self._get_manager().create_from_headers(
            name.strip(), self._sheet_data.headers,
            source_format=self._source_format_family(self._file_path),
        )
        self._reload_templates()
        self._select_template_by_name(template.name)
        self._status_bar.show_success(f"模板 '{template.name}' 已创建并应用")

    @_safe_slot
    def _on_rename_template(self) -> None:
        """重命名当前选中模板（兼容选中路径）。"""
        if not self._require_saved_template():
            return
        self._rename_template_by_name(self._template.name)

    def _rename_template_by_name(self, name: str) -> None:
        """按模板名重命名。"""
        name, ok = _dlg.QInputDialog.getText(
            self, "重命名模板", "新名称：", text=name,
        )
        if not ok or not name.strip():
            return
        renamed = self._get_manager().rename(name, name.strip())
        self._reload_templates()
        self._select_template_by_name(renamed.name)
        self._status_bar.show_success(f"模板已重命名为 '{renamed.name}'")

    @_safe_slot
    def _on_delete_template(self) -> None:
        """删除当前选中模板（兼容选中路径，需确认）。"""
        if not self._require_saved_template():
            return
        self._delete_template_by_name(self._template.name)

    def _delete_template_by_name(self, name: str) -> None:
        """按模板名删除（需确认）。"""
        answer = _dlg.QMessageBox.question(
            self, "删除模板", f"确定删除模板 '{name}' 吗？",
        )
        if answer != _dlg.QMessageBox.StandardButton.Yes:
            return
        self._get_manager().delete(name)
        if self._template is not None and self._template.name == name:
            self._template = None
        self._reload_templates()
        self._status_bar.show_success(f"模板「{name}」已删除")
