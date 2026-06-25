import importlib
from pathlib import Path
from typing import List, Tuple, Type

from PyQt6.QtWidgets import QMainWindow, QTabWidget, QLabel, QWidget

from core.logger import get_logger


class MainWindow(QMainWindow):
    """主窗口：自动扫描 features/ 并加载功能面板。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("WPS Enhancer")
        self.setMinimumSize(900, 600)
        self._features: List[Tuple[str, Type[QWidget]]] = []
        self._load_features()
        self._setup_ui()

    def _load_features(self) -> None:
        """扫描 features/ 目录，动态导入各功能子包。"""
        features_dir = Path("features")
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
                if name and panel:
                    self._features.append((name, panel))
            except Exception as e:
                logger.warning(f"加载功能 '{entry.name}' 失败：{e}")

    def _setup_ui(self) -> None:
        """创建 QTabWidget 并加载所有功能面板。"""
        if not self._features:
            self.setCentralWidget(QLabel("未找到任何功能模块"))
            return

        tab_widget = QTabWidget()
        for feature_name, panel_cls in self._features:
            panel_instance = panel_cls()
            tab_widget.addTab(panel_instance, feature_name)
        self.setCentralWidget(tab_widget)
