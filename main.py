import sys
import traceback

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
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
