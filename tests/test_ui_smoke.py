import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtWidgets import QApplication


class UiSmokeTest(unittest.TestCase):
    """UI 冒烟测试：面板/设置对话框/主窗口可实例化（offscreen）。"""

    def setUp(self):
        """注入默认设置缓存：隔离用户真实 settings.json（字段数/值可能不同）。"""
        import core.settings as cs
        from core.settings import AppSettings
        self._orig_cache = cs._cache
        cs._cache = AppSettings()

    def tearDown(self):
        import core.settings as cs
        cs._cache = self._orig_cache

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_panel_instantiates(self):
        from features.contacts_import.panel import ContactsImportPanel
        panel = ContactsImportPanel()
        self.assertIsNotNone(panel)
        self.assertFalse(panel._export_btn.isEnabled())
        panel.close()

    def test_export_btn_gated_on_preview_failure(self):
        """预览生成异常时导出按钮禁用并提示（异常兜底）。"""
        from unittest import mock
        from features.contacts_import.panel import ContactsImportPanel
        from features.contacts_import.ui import preview as preview_mod
        panel = ContactsImportPanel()
        try:
            # 构造最小预览前置状态
            panel._template = mock.MagicMock()
            panel._sheet_data = mock.MagicMock()
            panel._matches = []
            with mock.patch.object(
                preview_mod, "build_preview_data",
                side_effect=RuntimeError("boom"),
            ):
                panel._refresh_preview()
            self.assertFalse(panel._export_btn.isEnabled())
        finally:
            panel.close()

    def test_export_btn_disabled_on_empty_preview(self):
        """预览无数据时导出按钮禁用并提示。"""
        from unittest import mock
        from features.contacts_import.panel import ContactsImportPanel
        from features.contacts_import.ui import preview as preview_mod
        panel = ContactsImportPanel()
        try:
            panel._template = mock.MagicMock()
            panel._sheet_data = mock.MagicMock()
            panel._matches = []
            empty_preview = mock.MagicMock()
            empty_preview.rows = []
            with mock.patch.object(
                preview_mod, "build_preview_data", return_value=empty_preview,
            ):
                panel._refresh_preview()
            self.assertFalse(panel._export_btn.isEnabled())
        finally:
            panel.close()

    def test_settings_dialog_instantiates(self):
        from ui.components.settings_dialog import SettingsDialog
        dlg = SettingsDialog()
        self.assertIsNotNone(dlg)
        self.assertEqual(dlg.windowTitle(), "设置")
        dlg.close()

    def test_template_edit_dialog_instantiates(self):
        from ui.components.template_edit_dialog import TemplateEditDialog
        from core.template.config import default_builtin_columns
        dlg = TemplateEditDialog(default_builtin_columns())
        self.assertIsNotNone(dlg)
        dlg.close()

    def test_main_window_instantiates_with_feature(self):
        from ui.main_window import MainWindow
        win = MainWindow()
        self.assertEqual(win.windowTitle(), "WPS Enhancer")
        # 自动发现机制应加载 contacts_import 面板
        self.assertEqual(len(win._features), 1)
        self.assertEqual(win._features[0][0], "Excel 批量导入通讯录")
        win.close()

    def test_feature_module_exposes_names(self):
        import features.contacts_import as mod
        self.assertEqual(mod.FEATURE_NAME, "Excel 批量导入通讯录")
        self.assertIsNotNone(mod.Panel)

    def test_default_template_from_builtins(self):
        from unittest import mock
        from core.settings import AppSettings
        from features.contacts_import.panel import ContactsImportPanel
        with mock.patch(
            "features.contacts_import.panel.get_app_settings",
            return_value=AppSettings(),
        ):
            panel = ContactsImportPanel()
            t = panel._get_default_template()
        self.assertEqual(
            [c.key for c in t.columns],
            ["name", "phone", "company", "website"],
        )
        self.assertEqual([c.name for c in t.columns], ["姓名", "手机", "公司名", "网址"])
        panel.close()

    def test_default_mapping_applied_without_templates(self):
        import tempfile
        from unittest import mock
        from core.file_io.base import SheetData
        from core.settings import AppSettings
        from features.contacts_import.panel import ContactsImportPanel

        empty_dir = Path(tempfile.mkdtemp(prefix="wps_empty_tpl_"))
        with mock.patch(
            "features.contacts_import.panel.get_templates_dir",
            return_value=empty_dir,
        ), mock.patch(
            "features.contacts_import.panel.get_app_settings",
            return_value=AppSettings(),
        ):
            panel = ContactsImportPanel()
            panel._sheet_data = SheetData(
                sheet_name="s", headers=["姓名", "手机号"],
                rows=[{"姓名": "张三", "手机号": "138"}],
            )
            panel._reload_templates()
            panel._auto_template_decision(panel._sheet_data.headers)
        # 无模板不阻断：显示「暂无模板」提示，自动应用默认映射
        self.assertFalse(panel._no_template_label.isHidden())
        self.assertEqual(panel._template_table.rowCount(), 2)  # 仅默认映射行 + 占位行
        self.assertIsNotNone(panel._template)
        self.assertEqual(panel._template.name, "（默认映射：内置列）")
        self.assertEqual(len(panel._matches), 4)
        self.assertFalse(panel._preview_group.isHidden())
        self.assertTrue(panel._export_btn.isEnabled())
        panel.close()

    def test_mapping_table_has_example_column(self):
        import tempfile
        from unittest import mock
        from core.file_io.base import SheetData
        from features.contacts_import.panel import ContactsImportPanel

        panel = ContactsImportPanel()
        panel._sheet_data = SheetData(
            sheet_name="s", headers=["姓名", "手机号"],
            rows=[{"姓名": "张三", "手机号": "138"}, {"姓名": "李四", "手机号": "139"}],
        )
        panel._fill_source_table()
        empty_dir = Path(tempfile.mkdtemp(prefix="wps_example_tpl_"))
        with mock.patch(
            "features.contacts_import.panel.get_templates_dir",
            return_value=empty_dir,
        ):
            panel._reload_templates()
            panel._auto_template_decision(panel._sheet_data.headers)
        # 映射表 5 列（+操作列），示例值列显示源列前 3 行内容
        self.assertEqual(panel._mapping_table.columnCount(), 5)
        name_example = panel._mapping_table.item(0, 3).text()
        self.assertIn("张三", name_example)
        self.assertIn("李四", name_example)
        # 源表内容表格已填充（表头 + 数据行）
        self.assertEqual(panel._source_table.rowCount(), 2)
        self.assertEqual(
            panel._source_table.horizontalHeaderItem(0).text(), "姓名",
        )
        panel.close()

    def test_mapping_change_links_source_column(self):
        import tempfile
        from unittest import mock
        from core.file_io.base import SheetData
        from features.contacts_import.panel import ContactsImportPanel

        panel = ContactsImportPanel()
        panel._sheet_data = SheetData(
            sheet_name="s",
            headers=["姓名", "手机号", "公司"],
            rows=[{"姓名": "张三", "手机号": "138", "公司": "A公司"}],
        )
        panel._fill_source_table()
        empty_dir = Path(tempfile.mkdtemp(prefix="wps_link_tpl_"))
        with mock.patch(
            "features.contacts_import.panel.get_templates_dir",
            return_value=empty_dir,
        ):
            panel._reload_templates()
            panel._auto_template_decision(panel._sheet_data.headers)
        # 手动把 phone（第 1 行）映射到「公司」列 → 源表「公司」列高亮 + 示例值联动
        panel._on_mapping_changed(1, "公司")
        example = panel._mapping_table.item(1, 3).text()
        self.assertIn("A公司", example)
        highlighted = panel._source_table.item(0, 2).background().color().name()
        self.assertEqual(highlighted, "#d6eaf8")
        not_highlighted = panel._source_table.item(0, 0).background().color().name()
        self.assertNotEqual(not_highlighted, "#d6eaf8")
        # 置空映射 → 高亮清除
        panel._on_mapping_changed(1, "")
        cleared = panel._source_table.item(0, 2).background().color().name()
        self.assertNotEqual(cleared, "#d6eaf8")
        panel.close()


    def test_export_full_flow_vcf_suffix(self):
        """导出全流程：vcf 后缀正确导出；无后缀/错后缀提示并中断，不崩溃。"""
        import tempfile
        from unittest import mock
        from core.file_io.base import SheetData
        from features.contacts_import.panel import ContactsImportPanel

        panel = ContactsImportPanel()
        panel._sheet_data = SheetData(
            sheet_name="s", headers=["姓名", "手机号"],
            rows=[{"姓名": "张三", "手机号": "13800000000"}],
        )
        empty_dir = Path(tempfile.mkdtemp(prefix="wps_export_tpl_"))
        with mock.patch(
            "features.contacts_import.panel.get_templates_dir",
            return_value=empty_dir,
        ):
            panel._reload_templates()
            panel._auto_template_decision(panel._sheet_data.headers)
        panel._format_combo.setCurrentText("vcf")
        out_dir = Path(tempfile.mkdtemp(prefix="wps_out_"))

        def run_export(target: str) -> bool:
            """执行导出；返回是否走到写入（False 表示被格式校验中断）。"""
            wrote = []
            with mock.patch(
                "PyQt6.QtWidgets.QFileDialog.getSaveFileName",
                return_value=(target, ""),
            ):
                with mock.patch(
                    "features.contacts_import.ui.base.QInputDialog.getText",
                    return_value=("", False),  # 取消「保存为模板」输入框
                ):
                    with mock.patch(
                        "features.contacts_import.ui.base.QMessageBox",
                    ) as msg_mock:  # 屏蔽导入指南/去向弹窗
                        panel._export_btn.click()  # 真实信号路径（回归：clicked 带参 bug）
                    # warning 弹窗 = 格式中断
                    return not msg_mock.warning.called

        # 后缀正确 → 正常导出
        self.assertTrue(run_export(str(out_dir / "通讯录.vcf")))
        self.assertTrue((out_dir / "通讯录.vcf").exists())
        content = (out_dir / "通讯录.vcf").read_text(encoding="utf-8")
        self.assertIn("BEGIN:VCARD", content)
        # 无后缀 → 提示并中断，不自动补
        self.assertFalse(run_export(str(out_dir / "通讯录2")))
        self.assertFalse((out_dir / "通讯录2.vcf").exists())
        # 后缀与所选格式不符 → 提示并中断，不修正
        self.assertFalse(run_export(str(out_dir / "通讯录3.xlsx")))
        self.assertFalse((out_dir / "通讯录3.xlsx").exists())
        panel.close()

    def test_vcf_custom_row_visibility_by_format(self):
        """导出格式非 vcf 时，vcf 姓名前后缀/字段控件行隐藏（需求 1）。"""
        import tempfile
        from unittest import mock
        from core.file_io.base import SheetData
        from features.contacts_import.panel import ContactsImportPanel

        panel = ContactsImportPanel()
        self.assertFalse(panel._vcf_custom_row.isHidden())  # 默认 vcf 可见
        panel._format_combo.setCurrentText("xlsx")
        self.assertTrue(panel._vcf_custom_row.isHidden())
        panel._format_combo.setCurrentText("csv")
        self.assertTrue(panel._vcf_custom_row.isHidden())
        panel._format_combo.setCurrentText("vcf")
        self.assertFalse(panel._vcf_custom_row.isHidden())
        panel.close()

    def test_preview_display_matches_export_format(self):
        """预览展示导出内容：vcf 仅 vcf 字段列 + 姓名应用前后缀；xlsx 全列原值（需求 2）。"""
        import tempfile
        from unittest import mock
        from core.file_io.base import SheetData
        from core.settings import AppSettings
        from features.contacts_import.panel import ContactsImportPanel

        settings = AppSettings()  # 默认设置（隔离用户真实设置）
        settings.vcf_name_prefix = "客户-"
        settings.vcf_name_suffix = "-VIP"
        settings.vcf_timestamp = False  # 关闭时间戳，聚焦前缀/字段断言
        import core.settings as cs
        cs._cache = settings  # 写回缓存：预览等模块通过 get_app_settings 读取
        empty_dir = Path(tempfile.mkdtemp(prefix="wps_pv_"))
        with mock.patch(
            "features.contacts_import.panel.get_templates_dir",
            return_value=empty_dir,
        ), mock.patch(
            "features.contacts_import.panel.get_app_settings",
            return_value=settings,
        ):
            panel = ContactsImportPanel()
            panel._sheet_data = SheetData(
                sheet_name="s", headers=["姓名", "手机号"],
                rows=[{"姓名": "张三", "手机号": "13800000000"}],
            )
            panel._reload_templates()
            panel._auto_template_decision(panel._sheet_data.headers)
            panel._format_combo.setCurrentText("vcf")
        panel._refresh_preview()
        # vcf 为文本预览：内容与导出文件一致（含前后缀、字段过滤）
        text = panel._preview_text.toPlainText()
        self.assertIn("BEGIN:VCARD", text)
        self.assertIn("FN:客户-张三-VIP", text)
        self.assertIn("TEL;TYPE=CELL:13800000000", text)
        # xlsx 为表格预览：显示全部列且姓名不加前后缀
        panel._format_combo.setCurrentText("xlsx")
        panel._refresh_preview()
        self.assertFalse(panel._preview_table.isHidden())
        self.assertTrue(panel._preview_text.isHidden())
        headers = [
            panel._preview_table.horizontalHeaderItem(i).text()
            for i in range(panel._preview_table.columnCount())
        ]
        self.assertEqual(headers, ["姓名", "手机", "公司名", "网址"])
        self.assertEqual(panel._preview_table.item(0, 0).text(), "张三")
        # 取消勾选网址字段 → vcf 文本预览不含 URL（阻止保存到用户设置）
        with mock.patch("core.settings.save_app_settings"):
            panel._vcf_field_checks[3].setChecked(False)
        panel._format_combo.setCurrentText("vcf")
        panel._refresh_preview()
        text = panel._preview_text.toPlainText()
        self.assertNotIn("URL:", text)
        panel.close()

    def test_add_template_column_manual_empty(self):
        """添加模板列：状态手动、未设源列时导出处列为空、示例显示「—」。"""
        import tempfile
        from unittest import mock
        from core.file_io.base import SheetData
        from features.contacts_import.panel import ContactsImportPanel

        panel = ContactsImportPanel()
        panel._sheet_data = SheetData(
            sheet_name="s", headers=["姓名", "手机号", "公司"],
            rows=[{"姓名": "张三", "手机号": "13800000000", "公司": "A公司"}],
        )
        empty_dir = Path(tempfile.mkdtemp(prefix="wps_addcol_tpl_"))
        with mock.patch(
            "features.contacts_import.panel.get_templates_dir",
            return_value=empty_dir,
        ):
            panel._reload_templates()
            panel._auto_template_decision(panel._sheet_data.headers)
        with mock.patch(
            "features.contacts_import.ui.base.QInputDialog.getText",
            return_value=("备注", True),
        ):
            panel._on_add_template_column()
        keys = [c.key for c in panel._template.columns]
        self.assertIn("custom_1", keys)
        last = panel._matches[-1]
        self.assertEqual(last.status, "manual")
        self.assertIsNone(last.source_col)
        self.assertEqual(
            panel._mapping_table.item(len(panel._matches) - 1, 1).text(), "手动",
        )
        self.assertEqual(
            panel._mapping_table.item(len(panel._matches) - 1, 3).text(), "—",
        )
        # 导出时该列内容为空、列名存在
        self.assertEqual(panel._preview.rows[0].values[-1], "")
        panel.close()

    def test_edit_and_remove_template_column(self):
        """第一列编辑：已有行改名、占位行输入新增；删除按钮移除列。"""
        import tempfile
        from unittest import mock
        from PyQt6.QtWidgets import QTableWidgetItem
        from core.file_io.base import SheetData
        from features.contacts_import.panel import ContactsImportPanel

        panel = ContactsImportPanel()
        panel._sheet_data = SheetData(
            sheet_name="s", headers=["姓名", "手机号"],
            rows=[{"姓名": "张三", "手机号": "13800000000"}],
        )
        empty_dir = Path(tempfile.mkdtemp(prefix="wps_editcol_tpl_"))
        with mock.patch(
            "features.contacts_import.panel.get_templates_dir",
            return_value=empty_dir,
        ):
            panel._reload_templates()
            panel._auto_template_decision(panel._sheet_data.headers)
        # 占位行输入列名 → 新增列
        placeholder_row = len(panel._matches)
        item = QTableWidgetItem("邮箱")
        panel._on_column_name_edited(
            type("FakeItem", (), {
                "column": lambda self: 0,
                "row": lambda self: placeholder_row,
                "text": lambda self: "邮箱",
            })(),
        )
        self.assertEqual(panel._template.columns[-1].name, "邮箱")
        self.assertEqual(panel._matches[-1].status, "manual")
        # 已有行改名
        name_item = panel._mapping_table.item(0, 0)
        panel._on_column_name_edited(
            type("FakeItem2", (), {
                "column": lambda self: 0,
                "row": lambda self: 0,
                "text": lambda self: "联系人",
            })(),
        )
        self.assertEqual(panel._template.columns[0].name, "联系人")
        # 删除列（占位行上一行 = 刚添加的邮箱），确认框返回 Yes
        from PyQt6.QtWidgets import QMessageBox
        with mock.patch(
            "features.contacts_import.ui.base.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            panel._remove_template_column(len(panel._matches) - 1)
        names = [c.name for c in panel._template.columns]
        self.assertNotIn("邮箱", names)
        self.assertIn("联系人", names)
        panel.close()

    def test_delete_button_click_removes_clicked_row(self):
        """真实点击第 2 行删除按钮：删除指定行而非第一行（clicked 带参回归）。"""
        import tempfile
        from unittest import mock
        from PyQt6.QtWidgets import QMessageBox
        from core.file_io.base import SheetData
        from features.contacts_import.panel import ContactsImportPanel

        panel = ContactsImportPanel()
        panel._sheet_data = SheetData(
            sheet_name="s", headers=["姓名", "手机号", "公司"],
            rows=[{"姓名": "张三", "手机号": "13800000000", "公司": "A"}],
        )
        empty_dir = Path(tempfile.mkdtemp(prefix="wps_delrow_"))
        with mock.patch(
            "features.contacts_import.panel.get_templates_dir",
            return_value=empty_dir,
        ):
            panel._reload_templates()
            panel._auto_template_decision(panel._sheet_data.headers)
        names_before = [c.name for c in panel._template.columns]
        self.assertGreaterEqual(len(names_before), 3)
        # 真实点击第 2 行（index=1）的删除按钮（信号路径：clicked 带 checked 参数）
        del_btn = panel._mapping_table.cellWidget(1, 4)
        self.assertIsNotNone(del_btn)
        with mock.patch(
            "features.contacts_import.ui.base.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            del_btn.click()
        names_after = [c.name for c in panel._template.columns]
        self.assertEqual(len(names_after), len(names_before) - 1)
        self.assertEqual(names_after[1], names_before[2])  # 原第 2 行被删，其余顺移
        self.assertEqual(names_after[0], names_before[0])  # 第一行保留
        panel.close()


    def test_template_row_has_action_buttons(self):
        """模板表格每行有操作按钮（应用/编辑/重命名/删除），默认映射行只有应用。"""
        import tempfile
        from unittest import mock
        from core.file_io.base import SheetData
        from core.template import TemplateManager
        from core.template.config import TemplateColumn
        from features.contacts_import.panel import ContactsImportPanel

        panel = ContactsImportPanel()
        panel._sheet_data = SheetData(
            sheet_name="s", headers=["姓名", "手机号"],
            rows=[{"姓名": "张三", "手机号": "13800000000"}],
        )
        tpl_dir = Path(tempfile.mkdtemp(prefix="wps_ops_"))
        TemplateManager(tpl_dir, []).create(
            "测试模板", [TemplateColumn(key="name", name="姓名")],
        )
        with mock.patch(
            "features.contacts_import.panel.get_templates_dir",
            return_value=tpl_dir,
        ):
            panel._reload_templates()
            panel._auto_template_decision(panel._sheet_data.headers)
        # 表格 3 列：模板名 | 模板列 | 操作；末行新建提示占位
        self.assertEqual(panel._template_table.columnCount(), 3)
        self.assertEqual(panel._template_table.rowCount(), 3)  # 默认映射 + 模板 + 占位
        # 模板行操作列有 4 个按钮；默认映射行只有 1 个（应用）
        from PyQt6.QtWidgets import QPushButton
        ops = panel._template_table.cellWidget(1, 2)
        buttons = [
            b for b in ops.findChildren(QPushButton)
        ]
        self.assertEqual(len(buttons), 4)
        default_ops = panel._template_table.cellWidget(0, 2)
        self.assertEqual(len(default_ops.findChildren(QPushButton)), 1)
        panel.close()

    def test_template_create_hint_edits_template(self):
        """模板表格末行占位格输入「模板名：列1、列2」创建模板。"""
        import tempfile
        from unittest import mock
        from PyQt6.QtWidgets import QTableWidgetItem
        from features.contacts_import.panel import ContactsImportPanel

        panel = ContactsImportPanel()
        tpl_dir = Path(tempfile.mkdtemp(prefix="wps_create_"))
        with mock.patch(
            "features.contacts_import.panel.get_templates_dir",
            return_value=tpl_dir,
        ):
            panel._reload_templates()
            # 真实信号路径：setText 触发 itemChanged → handler 创建模板（延迟刷新不销毁 item）
            hint_row = panel._template_table.rowCount() - 1
            hint_item = panel._template_table.item(hint_row, 1)
            hint_item.setText("客户通讯录：姓名、手机号、公司")
            names = [
                t.name for t in panel._get_manager().list_templates()
            ]
            self.assertIn("客户通讯录", names)
            # 解析函数：无效格式返回空列
            self.assertEqual(
                panel._parse_template_create_input("没有冒号"),
                ("没有冒号", []),
            )
            self.assertEqual(
                panel._parse_template_create_input("模板A：姓名,手机"),
                ("模板A", ["姓名", "手机"]),
            )
        panel.close()

    def test_path_entered_invalid_suffix_blocked(self):
        """手动输入文件路径：后缀不合法 → 提示且不加载（无法进入下一步）。"""
        import tempfile
        from unittest import mock
        from features.contacts_import.panel import ContactsImportPanel

        panel = ContactsImportPanel()
        bad = Path(tempfile.mkdtemp(prefix="wps_bad_")) / "数据.txt"
        bad.write_text("x", encoding="utf-8")
        with mock.patch(
            "features.contacts_import.ui.base.QMessageBox.warning",
        ) as warn_mock:
            with mock.patch(
                "features.contacts_import.panel.get_templates_dir",
                return_value=Path(tempfile.mkdtemp(prefix="wps_bad_tpl_")),
            ):
                panel._file_picker.set_file_path(str(bad))
                panel._on_path_entered()
        self.assertTrue(warn_mock.called)
        self.assertIsNone(panel._sheet_data)  # 未加载 → 下一步被拦截
        self.assertFalse(panel._step_ready(0))
        panel.close()

    def test_template_selected_without_file(self):
        """无源文件时点应用模板：提示并终止，不记住选择。"""
        import tempfile
        from unittest import mock
        from core.template import TemplateManager
        from core.template.config import TemplateColumn
        from features.contacts_import.panel import ContactsImportPanel

        panel = ContactsImportPanel()  # 无 sheet_data
        tpl_dir = Path(tempfile.mkdtemp(prefix="wps_nofile_"))
        TemplateManager(tpl_dir, []).create(
            "通讯录模板", [TemplateColumn(key="name", name="姓名")],
        )
        with mock.patch(
            "features.contacts_import.panel.get_templates_dir",
            return_value=tpl_dir,
        ):
            panel._reload_templates()
            panel._select_template_by_name("通讯录模板")
            with mock.patch(
                "features.contacts_import.ui.base.QMessageBox.information",
            ) as info_mock:
                panel._apply_template()  # 无文件：提示并终止
            self.assertTrue(info_mock.called)
        self.assertIsNone(panel._template)  # 未应用
        self.assertEqual(panel._template_summary.text(), "")
        panel.close()

    def test_prompt_save_skipped_when_saved_template_applied(self):
        """已应用保存模板时导出成功不再弹「保存为模板」（mock 断言输入框未被调用）。"""
        import tempfile
        from unittest import mock
        from core.file_io.base import SheetData
        from core.template import TemplateManager
        from core.template.config import TemplateColumn
        from features.contacts_import.panel import ContactsImportPanel

        panel = ContactsImportPanel()
        panel._sheet_data = SheetData(
            sheet_name="s", headers=["姓名", "手机号"],
            rows=[{"姓名": "张三", "手机号": "13800000000"}],
        )
        tpl_dir = Path(tempfile.mkdtemp(prefix="wps_nosave_"))
        TemplateManager(tpl_dir, []).create(
            "已存模板", [TemplateColumn(key="name", name="姓名")],
        )
        with mock.patch(
            "features.contacts_import.panel.get_templates_dir",
            return_value=tpl_dir,
        ):
            panel._reload_templates()
            panel._apply_template_by_name("已存模板")
        with mock.patch(
            "features.contacts_import.ui.base.QInputDialog.getText",
        ) as get_text:
            panel._prompt_save_template()
        get_text.assert_not_called()  # 已应用保存模板 → 不再询问
        panel.close()

    def test_sync_vcf_settings(self):
        """预览页 vcf 前缀/后缀/字段修改同步保存到全局设置。"""
        import tempfile
        from unittest import mock
        from core.file_io.base import SheetData
        from core.settings import get_app_settings, reset_settings_cache
        from features.contacts_import.panel import ContactsImportPanel

        reset_settings_cache()
        tmp_data = Path(tempfile.mkdtemp(prefix="wps_vcfsync_"))
        with mock.patch("core.app_paths.get_data_dir", return_value=tmp_data):
            panel = ContactsImportPanel()
            # 默认：前缀 vcf_ + 时间戳开启（姓名前）
            self.assertEqual(panel._vcf_prefix_edit.text(), "vcf_")
            self.assertTrue(panel._vcf_ts_check.isChecked())
            self.assertEqual(panel._vcf_ts_pos_combo.currentText(), "姓名前")
            # 自定义：改前缀、关时间戳、位置姓名后
            panel._vcf_prefix_edit.setText("客户-")
            panel._vcf_ts_check.setChecked(False)
            panel._vcf_ts_pos_combo.setCurrentText("姓名后")
            panel._vcf_suffix_edit.setText("-VIP")
            panel._vcf_field_checks[2].setChecked(False)  # 取消公司名
            panel._sync_vcf_settings()
            reset_settings_cache()
            settings = get_app_settings()
            self.assertEqual(settings.vcf_name_prefix, "客户-")
            self.assertEqual(settings.vcf_name_suffix, "-VIP")
            self.assertFalse(settings.vcf_timestamp)
            self.assertEqual(settings.vcf_timestamp_position, "suffix")
            self.assertNotIn("company", settings.vcf_fields)
        panel.close()

    def test_auto_template_decision_matching(self):
        """选文件后：模板能匹配 → 停在步骤①等用户点应用；应用后直接进③预览。"""
        import tempfile
        from unittest import mock
        from core.file_io.base import SheetData
        from core.template import TemplateManager
        from core.template.config import TemplateColumn
        from features.contacts_import.panel import ContactsImportPanel

        panel = ContactsImportPanel()
        panel._sheet_data = SheetData(
            sheet_name="s", headers=["姓名", "手机号", "公司"],
            rows=[{"姓名": "张三", "手机号": "13800000000", "公司": "A公司"}],
        )
        tpl_dir = Path(tempfile.mkdtemp(prefix="wps_match_"))
        TemplateManager(tpl_dir, []).create(
            "企查查模板",
            [
                TemplateColumn(key="name", name="姓名"),
                TemplateColumn(key="phone", name="手机"),
                TemplateColumn(key="company", name="公司"),
            ],
        )
        with mock.patch(
            "features.contacts_import.panel.get_templates_dir",
            return_value=tpl_dir,
        ):
            panel._reload_templates()
            panel._auto_template_decision(panel._sheet_data.headers)
            # 匹配上：停在数据源步骤，等用户应用
            self.assertEqual(panel._stack.currentIndex(), 0)
            self.assertIsNone(panel._template)
            # 选择并应用 → 直接进入预览与导出（映射来自模板）
            panel._select_template_by_name("企查查模板")
            panel._apply_template()
        self.assertEqual(panel._stack.currentIndex(), 2)
        self.assertEqual(panel._template.name, "企查查模板")
        panel.close()

    def test_auto_template_decision_no_match(self):
        """匹配不上 → 自动默认映射并进入②列映射。"""
        import tempfile
        from unittest import mock
        from core.file_io.base import SheetData
        from core.template import TemplateManager
        from core.template.config import TemplateColumn
        from features.contacts_import.panel import ContactsImportPanel

        panel = ContactsImportPanel()
        panel._sheet_data = SheetData(
            sheet_name="s", headers=["X列", "Y列"],
            rows=[{"X列": "a", "Y列": "b"}],
        )
        tpl_dir = Path(tempfile.mkdtemp(prefix="wps_nomatch_"))
        TemplateManager(tpl_dir, []).create(
            "不匹配模板", [TemplateColumn(key="company", name="公司名")],
        )
        with mock.patch(
            "features.contacts_import.panel.get_templates_dir",
            return_value=tpl_dir,
        ):
            panel._reload_templates()
            panel._auto_template_decision(panel._sheet_data.headers)
        self.assertEqual(panel._stack.currentIndex(), 1)
        self.assertEqual(panel._template.name, "（默认映射：内置列）")
        panel.close()

    def test_step_indicator_click_validation(self):
        """步骤条点击：未就绪时被拦截（弹提示），就绪后可跳转。"""
        import tempfile
        from unittest import mock
        from PyQt6.QtWidgets import QMessageBox
        from features.contacts_import.panel import ContactsImportPanel

        panel = ContactsImportPanel()
        # 无文件：点击步骤 1 应被拦截
        with mock.patch(
            "features.contacts_import.ui.base.QMessageBox.information",
        ) as info:
            panel._goto_step_checked(1)
        info.assert_called_once()
        self.assertEqual(panel._stack.currentIndex(), 0)
        # 有文件 + 默认映射后：点击步骤 2 可跳转
        from core.file_io.base import SheetData
        panel._sheet_data = SheetData(
            sheet_name="s", headers=["姓名", "手机号"],
            rows=[{"姓名": "张三", "手机号": "13800000000"}],
        )
        empty_dir = Path(tempfile.mkdtemp(prefix="wps_stepclick_"))
        with mock.patch(
            "features.contacts_import.panel.get_templates_dir",
            return_value=empty_dir,
        ):
            panel._reload_templates()
            panel._auto_template_decision(panel._sheet_data.headers)
        panel._goto_step_checked(2)  # 映射已自动匹配 → 逐级校验通过
        self.assertEqual(panel._stack.currentIndex(), 2)
        panel.close()


if __name__ == "__main__":
    unittest.main()

    def test_sheet_combo_shows_name_and_rows(self):
        """sheet 下拉显示「名称（N 行）」，data 存真实 sheet 名。"""
        from unittest import mock
        from features.contacts_import.panel import ContactsImportPanel
        panel = ContactsImportPanel()
        try:
            with mock.patch(
                "features.contacts_import.panel.get_reader",
            ) as reader:
                reader.return_value.get_sheet_summaries.return_value = [
                    ("1", 235), ("通讯录", 120),
                ]
                panel._on_file_selected("/tmp/x.xlsx")
            self.assertEqual(panel._sheet_combo.count(), 2)
            self.assertEqual(panel._sheet_combo.itemText(0), "1（235 行）")
            self.assertEqual(panel._sheet_combo.itemData(0), "1")
            self.assertEqual(panel._sheet_combo.itemText(1), "通讯录（120 行）")
        finally:
            panel.close()

    def test_truncation_prompt_yes_continues(self):
        """截断提醒选「继续」后流程不受阻断。"""
        from unittest import mock
        from PyQt6.QtWidgets import QMessageBox
        from features.contacts_import.panel import ContactsImportPanel
        from features.contacts_import import processor as proc
        panel = ContactsImportPanel()
        try:
            from core.file_io.base import SheetData
            data = SheetData(
                sheet_name="s", headers=["号码"],
                rows=[{"号码": "1.38123E+10"}],
            )
            with mock.patch.object(
                QMessageBox, "question",
                return_value=QMessageBox.StandardButton.Yes,
            ), mock.patch.object(panel, "_status_bar") as sb:
                panel._check_truncated_numbers(data)
            self.assertFalse(sb.show_warning.called)  # 未中止
        finally:
            panel.close()

    def test_truncation_prompt_no_warns(self):
        """截断提醒选「中止」后给出指引提示。"""
        from unittest import mock
        from PyQt6.QtWidgets import QMessageBox
        from features.contacts_import.panel import ContactsImportPanel
        panel = ContactsImportPanel()
        try:
            from core.file_io.base import SheetData
            data = SheetData(
                sheet_name="s", headers=["号码"],
                rows=[{"号码": "110101199003070000"}],
            )
            with mock.patch.object(
                QMessageBox, "question",
                return_value=QMessageBox.StandardButton.No,
            ), mock.patch.object(panel, "_status_bar") as sb:
                panel._check_truncated_numbers(data)
            self.assertTrue(sb.show_warning.called)
        finally:
            panel.close()
