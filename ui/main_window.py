import importlib
from typing import List, Tuple, Type

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton,
    QFrame, QStackedWidget, QMessageBox,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QAction, QIcon, QKeySequence, QPainter, QPixmap, QFont

from core.app_paths import get_features_dir
from core.logger import get_logger
from ui.components.settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    """主窗口：功能卡片首页 + 功能面板页，自动扫描 features/ 注册。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("WPS Enhancer")
        self.setMinimumSize(900, 600)
        self._features: List[Tuple[str, str, Type[QWidget]]] = []
        self._load_features()
        self._setup_ui()
        self._schedule_update_check()

    def _load_features(self) -> None:
        """扫描 features/ 目录，动态导入各功能子包。"""
        features_dir = get_features_dir()
        if not features_dir.is_dir():
            return

        logger = get_logger("ui.main_window")
        for entry in features_dir.iterdir():
            if not entry.is_dir() or entry.name.startswith("_"):
                continue
            try:
                mod = importlib.import_module(f"features.{entry.name}")
                name = getattr(mod, "FEATURE_NAME", None)
                panel = getattr(mod, "Panel", None)
                desc = getattr(mod, "FEATURE_DESC", "")
                icon = getattr(mod, "FEATURE_ICON", "📄")
                if name and panel:
                    self._features.append((name, desc, icon, panel))
            except Exception as e:
                logger.warning(f"加载功能 '{entry.name}' 失败：{e}")

    def _setup_ui(self) -> None:
        """构建卡片首页与功能页堆叠，添加设置入口。"""
        self._add_settings_action()
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_home_page())
        self._feature_widget = QWidget()
        self._feature_layout = QVBoxLayout(self._feature_widget)
        self._feature_layout.setContentsMargins(0, 0, 0, 0)
        self._stack.addWidget(self._feature_widget)
        self.setCentralWidget(self._stack)

    def _build_home_page(self) -> QWidget:
        """首页：功能卡片列表（与 app 名称「WPS 增强工具」对应）。"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("WPS 增强工具")
        title.setStyleSheet("font-size: 22px; font-weight: bold;")
        layout.addWidget(title)
        subtitle = QLabel("选择一个功能开始使用")
        subtitle.setStyleSheet("color: #666666;")
        layout.addWidget(subtitle)
        layout.addSpacing(16)

        if not self._features:
            layout.addWidget(QLabel("未找到任何功能模块"))
            return page

        for name, desc, icon, panel_cls in self._features:
            layout.addWidget(self._build_card(name, desc, icon, panel_cls))
        layout.addStretch()
        return page

    def _build_card(
        self, name: str, desc: str, icon: str, panel_cls: Type[QWidget],
    ) -> QFrame:
        """构建单个功能卡片（整卡可点击进入）。"""
        card = QFrame()
        card.setObjectName("featureCard")
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setStyleSheet(
            "QFrame#featureCard { background: white; border: 1px solid #E0E0E0;"
            " border-radius: 10px; }"
            "QFrame#featureCard:hover { border: 2px solid #4A90D9;"
            " background: #F7FAFD; }"
        )
        layout = QHBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 16)

        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 30px;")
        layout.addWidget(icon_label)
        layout.addSpacing(8)

        text_layout = QVBoxLayout()
        name_label = QLabel(name)
        name_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        text_layout.addWidget(name_label)
        if desc:
            desc_label = QLabel(desc)
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet("color: #666666;")
            text_layout.addWidget(desc_label)
        layout.addLayout(text_layout, 1)

        arrow = QLabel("进入 →")
        arrow.setStyleSheet("color: #4A90D9; font-size: 14px;")
        layout.addWidget(arrow)

        # 整卡左键点击进入功能（不再依赖按钮）
        card.mouseReleaseEvent = lambda event: (
            self._enter_feature(name, panel_cls)
            if event.button() == Qt.MouseButton.LeftButton else None
        )
        return card

    def _enter_feature(self, name: str, panel_cls: Type[QWidget]) -> None:
        """进入功能：装载面板，顶部提供返回首页入口（任何异常不得让 app 退出）。"""
        try:
            self._clear_layout(self._feature_layout)
            top = QHBoxLayout()
            back_btn = QPushButton("← 返回首页")
            back_btn.clicked.connect(self._back_home)
            top.addWidget(back_btn)
            title_label = QLabel(name)
            title_label.setStyleSheet("font-weight: bold;")
            top.addWidget(title_label)
            top.addStretch()
            self._feature_layout.addLayout(top)
            panel = panel_cls()
            panel.back_home_requested.connect(self._back_home)
            self._feature_layout.addWidget(panel, 1)
            self._stack.setCurrentIndex(1)
        except Exception as e:
            get_logger("ui.main_window").exception(f"进入功能失败：{e}")
            QMessageBox.critical(self, "错误", f"进入功能失败：{e}\n详情见日志")

    def _back_home(self) -> None:
        """返回首页。"""
        self._stack.setCurrentIndex(0)

    def _clear_layout(self, layout: QVBoxLayout) -> None:
        """清空布局中的所有项。"""
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _add_settings_action(self) -> None:
        """工具栏「设置」入口：齿轮图标 + 下方文本 + ⌘, 快捷键。"""
        toolbar = self.addToolBar("设置")
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        toolbar.setIconSize(QSize(22, 22))
        settings_action = QAction(self._make_gear_icon(), "设置", self)
        settings_action.setToolTip("设置（⌘ ,）")
        settings_action.triggered.connect(self._open_settings)
        # macOS 上 Command 键对应 Qt 的 Ctrl 修饰符，因此用 Ctrl+,（Windows 亦适用）
        settings_action.setShortcut(QKeySequence("Ctrl+,"))
        toolbar.addAction(settings_action)

    def _make_gear_icon(self) -> QIcon:
        """绘制齿轮图标（⚙ emoji 渲染到 pixmap）。"""
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = QFont()
        font.setPointSize(15)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "⚙")
        painter.end()
        return QIcon(pixmap)

    def _open_settings(self) -> None:
        """打开全局设置对话框。"""
        SettingsDialog(self).exec()

    def _schedule_update_check(self) -> None:
        """启动延迟数秒后按设置自动检查更新（失败静默，不打扰使用）。"""
        try:
            from core.settings import get_app_settings
            if not get_app_settings().auto_update_enabled:
                return
        except Exception:
            return
        from PyQt6.QtCore import QTimer
        from ui.components.update_flow import check_update_now
        QTimer.singleShot(4000, lambda: check_update_now(self, True))
