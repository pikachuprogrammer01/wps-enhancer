"""导出流程与结果处理（拆分自 panel.py：ExportActionsMixin）。"""

from datetime import datetime
from pathlib import Path


from features.contacts_import.ui import base as _dlg
from core.exceptions import WpsEnhancerError
from core.file_io.base import get_writer
from core.logger import get_logger, log_call
from core.settings import get_app_settings
from features.contacts_import.ui.base import (
    _DEFAULT_MAPPING_NAME, _FORMAT_FILTERS,
)
from features.contacts_import.ui.base import _safe_slot
from features.contacts_import.processor import build_write_request


class ExportActionsMixin:
    """导出：保存对话框/格式校验/文件写入/成功与失败处理。"""

    @log_call("contacts_import.panel")
    @_safe_slot
    def _on_export_clicked(self) -> None:
        """弹出保存对话框（按所选格式传 filter），确认后执行导出。"""
        try:
            if self._preview is None or self._sheet_data is None:
                return
            fmt = self._format_combo.currentText()
            src_path = Path(self._file_path)
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            default_name = f"{src_path.stem}_{timestamp}.{fmt}"

            output_path, _ = _dlg.QFileDialog.getSaveFileName(
                self, "保存文件", str(src_path.parent / default_name),
                ";;".join(_FORMAT_FILTERS.values()),  # filter 必须以 ;; 分隔
                _FORMAT_FILTERS[fmt],  # 选中格式对应的 filter（macOS 据此补后缀）
            )
            if not output_path:
                return
            suffix = Path(output_path).suffix.lower().lstrip(".")
            if suffix != fmt:
                # 格式不符：提示并中断，等用户输入正确后缀
                _dlg.QMessageBox.warning(
                    self, "格式错误",
                    f"文件后缀与所选格式不符（需要 .{fmt} 后缀），"
                    "请重新输入正确的文件名",
                )
                self._status_bar.show_error(
                    f"格式不符：需要 .{fmt} 后缀，已中断导出",
                )
                return
            self._write_file(output_path)
        except Exception as e:  # 槽内任何异常不得让 app 退出（PyQt6 默认 qFatal）
            get_logger("contacts_import.panel").exception(f"导出流程异常：{e}")
            self._status_bar.show_error(f"导出失败：{e}")
            _dlg.QMessageBox.critical(self, "导出失败", f"发生错误：{e}\n详情见日志")

    @log_call("contacts_import.panel")
    def _write_file(self, output_path: str) -> None:
        """执行文件写入（任何异常都不得让 app 崩溃，统一提示）。"""
        try:
            settings = get_app_settings()
            request = build_write_request(
                self._preview, self._template, self._matches,
                settings, output_path,
            )
            get_writer(output_path).write_export(request)
            self._handle_success(output_path)
        except WpsEnhancerError as e:
            self._handle_error(e)
        except Exception as e:  # 兜底：Qt 槽内未捕获异常会直接退出 app
            get_logger("contacts_import.panel").exception(
                f"导出失败（未知错误）：{e}",
            )
            self._status_bar.show_error(f"导出失败：{e}")
            _dlg.QMessageBox.critical(self, "导出失败", f"发生未知错误：{e}\n详情见日志")

    # ========== 错误与成功处理 ==========

    def _handle_error(self, error: WpsEnhancerError) -> None:
        """统一的错误处理：日志 + 状态栏 + 弹窗。"""
        get_logger("contacts_import.panel").error(str(error))
        self._status_bar.show_error(str(error))
        _dlg.QMessageBox.critical(self, "错误", str(error))

    def _handle_success(self, output_path: str) -> None:
        """统一的成功处理：日志 + 状态栏 + vcf 导入指南 + 保存模板 + 去向询问。"""
        logger = get_logger("contacts_import.panel")
        msg = f"导出成功，共 {len(self._preview.rows)} 行，文件已保存至：{output_path}"
        logger.info(msg)
        self._status_bar.show_success(msg)
        if self._format_combo.currentText() == "vcf":
            self._show_vcf_import_guide()
        if self._template is not None and self._template.name == _DEFAULT_MAPPING_NAME:
            self._prompt_save_template()  # 默认映射时可顺手保存为模板（可取消）
        self._prompt_destination()  # 总是询问下一步去向

    def _prompt_destination(self) -> None:
        """流程完成后询问去向：首页 / 第一步 / 留在当前页。"""
        box = _dlg.QMessageBox(self)
        box.setWindowTitle("导出完成")
        box.setText("导出完成，接下来要去哪里？")
        home_btn = box.addButton("回到首页", _dlg.QMessageBox.ButtonRole.AcceptRole)
        step_btn = box.addButton("回到第一步", _dlg.QMessageBox.ButtonRole.AcceptRole)
        stay_btn = box.addButton("留在当前页", _dlg.QMessageBox.ButtonRole.AcceptRole)
        box.setDefaultButton(step_btn)
        box.exec()
        clicked = box.clickedButton()
        if clicked == home_btn:
            self.back_home_requested.emit()
        elif clicked == step_btn:
            self._goto_step(0)
        # 留在当前页：不做任何跳转

    def _show_vcf_import_guide(self) -> None:
        """vcf 导出成功后告知各平台导入通讯录的方法。"""
        _dlg.QMessageBox.information(
            self, "vCard 导入指南",
            "vCard 文件已导出，导入通讯录的方法：\n\n"
            "【iPhone】用「文件」App 找到导出的 .vcf 文件 → 点按打开 → "
            "选择「添加到通讯录」；或通过邮件发送给自己后，用「邮件」打开导入。\n\n"
            "【安卓】用文件管理器找到 .vcf 文件 → 使用系统「联系人/通讯录」应用打开 → "
            "按提示确认导入。\n\n"
            "【批量管理】导入后可在通讯录中按姓名前缀（如「客户-」）搜索联系人，"
            "批量编辑分组或删除。",
        )

    def _prompt_save_template(self) -> None:
        """导出成功后弹模板名称输入框；已应用保存模板时不再询问。"""
        if self._template is None or self._matches is None:
            return
        if self._template.name != _DEFAULT_MAPPING_NAME:
            return  # 已应用保存的模板，无需再次保存
        default = ""
        name, ok = _dlg.QInputDialog.getText(
            self, "保存为模板", "模板名称（保存后可一键应用）：", text=default,
        )
        if not ok or not name.strip():
            return
        self._save_current_as_template(name.strip())

    def _save_current_as_template(self, name: str) -> None:
        """将当前目标列与映射保存为新模板（映射作为建议保存）。"""
        mappings = {
            m.template_col.key: m.source_col
            for m in self._matches if m.source_col
        }
        saved = self._get_manager().create(
            name, self._template.columns, mappings,
        )
        self._reload_templates()
        self._select_template_by_name(saved.name)
        self._status_bar.show_success(
            f"模板「{saved.name}」已保存并应用，可点击模板列表切换",
        )
