"""更新 tab（自动检查开关 / 手动检查 / 更新源 / 目录配置）。"""

from pathlib import Path

from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QVBoxLayout, QWidget,
)

from core.logger import get_logger


class UpdateTabMixin:
    """更新设置分组（mixin：依赖宿主 SettingsDialog 的 self._settings）。"""

    def _build_update_tab(self) -> QWidget:
        """更新：自动检查开关 + 手动检查按钮 + 版本信息。"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self._build_update_group())
        layout.addStretch()
        return page

    def _build_update_group(self) -> QGroupBox:
        """更新分组（GitHub Releases 自动更新）。"""
        from core.version import APP_VERSION
        group = QGroupBox("更新")
        layout = QVBoxLayout(group)
        self._auto_update_check = QCheckBox("自动检查更新（启动时检查 GitHub Releases）")
        self._auto_update_check.setChecked(self._settings.auto_update_enabled)
        layout.addWidget(self._auto_update_check)
        self._proxy_check = QCheckBox("自动使用系统代理（网络受限时建议开启）")
        self._proxy_check.setChecked(self._settings.use_system_proxy)
        layout.addWidget(self._proxy_check)
        self._update_url_edit = QLineEdit(self._settings.update_url)
        self._update_url_edit.setReadOnly(True)  # 更新源内置，不允许手动修改
        self._update_url_edit.setStyleSheet(
            "background-color: #F3F4F6; color: #6B7280;",
        )
        layout.addWidget(QLabel("自定义更新源（内置，只读）"))
        layout.addWidget(self._update_url_edit)
        tip = QLabel(
            "app 默认从上方内置更新源检查更新（国内可达），不可修改；"
            "检查失败自动回退 GitHub Releases。",
        )
        tip.setWordWrap(True)
        tip.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(tip)
        dir_row = QHBoxLayout()
        self._download_dir_edit = QLineEdit(self._settings.download_dir)
        dir_row.addWidget(QLabel("更新包下载目录"))
        dir_row.addWidget(self._download_dir_edit, 1)
        browse_btn = QPushButton("浏览…")
        browse_btn.clicked.connect(self._on_browse_download_dir)
        dir_row.addWidget(browse_btn)
        layout.addLayout(dir_row)
        install_row = QHBoxLayout()
        self._install_dir_edit = QLineEdit(self._settings.install_dir)
        install_row.addWidget(QLabel("应用安装目录"))
        install_row.addWidget(self._install_dir_edit, 1)
        browse_install_btn = QPushButton("浏览…")
        browse_install_btn.clicked.connect(self._on_browse_install_dir)
        install_row.addWidget(browse_install_btn)
        layout.addLayout(install_row)
        row = QHBoxLayout()
        row.addWidget(QLabel(f"当前版本：v{APP_VERSION}"))
        row.addStretch()
        self._check_update_btn = QPushButton("检查更新")
        self._check_update_btn.clicked.connect(self._on_check_update)
        row.addWidget(self._check_update_btn)
        layout.addLayout(row)
        self._update_status_label = QLabel("")
        self._update_status_label.setStyleSheet("color: #666666;")
        self._update_status_label.setWordWrap(True)
        layout.addWidget(self._update_status_label)
        return group

    def _on_check_update(self) -> None:
        """手动检查更新（后台检查，结果弹窗；完成后复位状态文本）。"""
        from ui.components.update_flow import check_update_now
        self._check_update_btn.setEnabled(False)
        self._update_status_label.setText("正在检查更新…")

        def _reset_status() -> None:
            # 检查完成（无论成功失败）：复位按钮与状态文本
            self._check_update_btn.setEnabled(True)
            self._update_status_label.setText("")

        check_update_now(
            self, silent_on_failure=False, on_done=_reset_status,
            use_proxy=self._settings.use_system_proxy,
            update_url=self._update_url_edit.text().strip() or None,
        )

    def _on_browse_download_dir(self) -> None:
        """浏览选择更新包下载目录（异常静默兜底，不影响设置流程）。"""
        try:
            from PyQt6.QtWidgets import QFileDialog
            start = self._download_dir_edit.text().strip() or str(Path.home())
            path = QFileDialog.getExistingDirectory(
                self, "选择更新包下载目录", start,
            )
            if path:
                self._download_dir_edit.setText(path)
        except Exception as e:
            get_logger("ui.settings_dialog").warning(f"选择下载目录失败：{e}")

    def _on_browse_install_dir(self) -> None:
        """浏览选择应用安装目录（异常静默兜底，不影响设置流程）。"""
        try:
            from PyQt6.QtWidgets import QFileDialog
            start = self._install_dir_edit.text().strip() or str(Path.home())
            path = QFileDialog.getExistingDirectory(
                self, "选择应用安装目录", start,
            )
            if path:
                self._install_dir_edit.setText(path)
        except Exception as e:
            get_logger("ui.settings_dialog").warning(f"选择安装目录失败：{e}")
