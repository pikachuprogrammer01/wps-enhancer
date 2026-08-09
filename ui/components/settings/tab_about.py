"""关于 tab（应用信息 / 项目链接 / 问题反馈 / 卸载入口）。"""

from PyQt6.QtWidgets import (
    QGroupBox, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from ui.components import toast


class AboutTabMixin:
    """关于与卸载设置分组（mixin：依赖宿主 SettingsDialog）。"""

    def _build_about_tab(self) -> QWidget:
        """关于：应用信息 + 项目链接 + 问题反馈 + 卸载入口。"""
        from core.version import APP_VERSION
        page = QWidget()
        layout = QVBoxLayout(page)
        group = QGroupBox("关于")
        gl = QVBoxLayout(group)
        gl.addWidget(QLabel(f"WPS 增强工具  v{APP_VERSION}"))
        intro = QLabel(
            "为 WPS 表格提供增强功能的跨平台桌面工具，当前支持"
            "「Excel 批量导入通讯录」：多格式导入（xlsx/xls/csv）、"
            "列映射与模板、导出 xlsx/csv/txt/vcf 通讯录。",
        )
        intro.setWordWrap(True)
        gl.addWidget(intro)
        repo_link = QLabel(
            '<a href="https://github.com/pikachuprogrammer01/wps-enhancer">'
            "GitHub 项目主页</a>",
        )
        repo_link.setOpenExternalLinks(True)
        gl.addWidget(repo_link)
        layout.addWidget(group)

        feedback_group = QGroupBox("问题反馈")
        fl = QVBoxLayout(feedback_group)
        issue_link = QLabel(
            '<a href="https://github.com/pikachuprogrammer01/wps-enhancer/issues/new">'
            "前往 GitHub Issues 提交问题</a>",
        )
        issue_link.setOpenExternalLinks(True)
        fl.addWidget(issue_link)
        guide = QLabel(
            "提 issue 的建议写法：\n"
            "1. 标题：一句话描述问题（如「导出 vcf 崩溃」）\n"
            "2. 正文：复现步骤（做了什么 → 期望结果 → 实际结果）\n"
            "3. 附上日志：设置 → 日志 → 「导出日志文件」，把日志内容贴进 issue\n"
            "4. 附截图或源文件样例（去掉敏感信息）会更快定位\n"
            "5. 说明操作系统版本（macOS / Windows）",
        )
        guide.setWordWrap(True)
        guide.setStyleSheet("color: #555555; font-size: 11px;")
        fl.addWidget(guide)
        layout.addWidget(feedback_group)
        layout.addStretch(1)
        uninstall_group = QGroupBox("卸载")
        ul = QVBoxLayout(uninstall_group)
        ul.addWidget(QLabel("卸载会删除选中的内容（默认仅应用本体与日志）。"))
        self._uninstall_btn = QPushButton("卸载 WPS 增强工具…")
        self._uninstall_btn.setStyleSheet(
            "color: #DC2626; border-color: #DC2626;",
        )
        self._uninstall_btn.clicked.connect(self._on_uninstall)
        ul.addWidget(self._uninstall_btn)
        layout.addWidget(uninstall_group)
        return page

    def _on_uninstall(self) -> None:
        """卸载流程：勾选清理项 → 二次确认 → 逐项执行 → 结果反馈。"""
        from PyQt6.QtWidgets import QCheckBox, QDialog, QDialogButtonBox, QVBoxLayout
        from core.uninstall import uninstall_app, uninstall_items
        items = uninstall_items()
        dlg = QDialog(self)
        dlg.setWindowTitle("卸载 WPS 增强工具")
        dlg.setMinimumWidth(420)
        v = QVBoxLayout(dlg)
        v.addWidget(QLabel("选择要删除的内容："))
        checks = {}
        for item in items:
            text = item.label + ("　⚠️ 高风险（用户数据）" if item.risky else "")
            cb = QCheckBox(text)
            cb.setChecked(item.default_checked)
            if item.key == "app":
                cb.setEnabled(False)  # 应用本体必选
            checks[item.key] = cb
            v.addWidget(cb)
        tip = QLabel(
            "提示：应用本体删除需在完全退出本应用后进行；\n"
            "若删除失败，请退出后手动删除 "
            + ("/Applications/WPS增强工具.app"
               if __import__("sys").platform == "darwin"
               else "安装目录（%LOCALAPPDATA%\\WPSEnhancer）"),
        )
        tip.setWordWrap(True)
        tip.setStyleSheet("color: #888888; font-size: 11px;")
        v.addWidget(tip)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("确认卸载")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        v.addWidget(buttons)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        keys = [k for k, cb in checks.items() if cb.isChecked()]
        # 二次确认（列出将删除项）
        summary = "\n".join(
            f"· {next(i.label for i in items if i.key == k)}"
            + ("（⚠️ 高风险）" if next(i.risky for i in items if i.key == k) else "")
            for k in keys
        )
        confirm = QMessageBox.question(
            self, "确认卸载",
            f"确定卸载并删除以下内容？\n\n{summary}\n\n"
            "此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        results = uninstall_app(keys)
        failed = [err for _, err in results if err]
        ok_count = len(results) - len(failed)
        if failed:
            toast.show_toast(
                self.parent() or self,
                f"已删除 {ok_count} 项，失败 {len(failed)} 项：{failed[0]}",
                success=False,
            )
        else:
            toast.show_toast(
                self.parent() or self,
                "卸载完成，建议重启电脑后检查",
            )
