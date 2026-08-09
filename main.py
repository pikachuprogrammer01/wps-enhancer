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
    # 启动后延迟自动清理过期日志（按设置保留天数，静默失败不影响启动）
    from PyQt6.QtCore import QTimer
    from core.logger import cleanup_logs

    def _auto_clean_logs() -> None:
        try:
            from core.settings import get_app_settings
            settings = get_app_settings()
            if settings.log_auto_clean:
                deleted, failed = cleanup_logs(retain_days=settings.log_retain_days)
                if deleted or failed:
                    get_logger("main").info(
                        f"自动清理日志：删除 {deleted} 个，失败 {failed} 个",
                    )
        except Exception as e:
            get_logger("main").warning(f"自动清理日志失败：{e}")

    _cleanup_timer = QTimer()
    _cleanup_timer.timeout.connect(_auto_clean_logs)
    _cleanup_timer.start(24 * 3600 * 1000)  # 常驻期间每天清理一次
    QTimer.singleShot(2000, _auto_clean_logs)  # 启动 2 秒后立即清理一次
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
