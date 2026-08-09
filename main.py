import sys
import traceback

# 打包版（PyInstaller 冻结环境）下 openpyxl 初始化 descriptor 链会触发
# RecursionError，必须在一开始就提高递归深度（openpyxl 导入之前）。
sys.setrecursionlimit(10000)

from PyQt6.QtWidgets import QApplication

from core.app_paths import get_data_dir
from core.logger import get_logger
from ui.main_window import MainWindow


def _excepthook(exc_type, exc_value, exc_tb) -> None:
    """兜底：任何未捕获异常记录日志而非静默退出。"""
    get_logger("main").error(
        "未捕获异常：\n" + "".join(traceback.format_exception(exc_type, exc_value, exc_tb)),
    )


def main() -> None:
    """应用入口。"""
    get_logger("main").info("应用启动")
    sys.excepthook = _excepthook
    # 预创建可写数据目录（模板/设置存放），确保首次保存模板可用
    get_data_dir().mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv)
    from ui.theme import apply_global_theme
    apply_global_theme(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
