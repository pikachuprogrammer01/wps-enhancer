"""轻提示组件（element-plus message 风格）：顶部滑入、自动淡出、非阻塞。

用法：
    show_toast(parent, "保存成功")            # 默认 2.5s
    show_toast(parent, "暂无日志", success=False)  # 失败提示（橙色）
"""

from PyQt6.QtCore import (
    QEasingCurve, QPoint, QPropertyAnimation, QTimer, Qt,
)
from PyQt6.QtWidgets import QLabel, QWidget


def show_toast(parent: QWidget, text: str,
               success: bool = True, duration_ms: int = 2500) -> None:
    """在 parent 顶部居中显示轻提示，自动淡出销毁（不阻塞、不挡点击）。

    成功绿色点 / 失败橙色点前缀，深色半透明圆角气泡（element-plus 风格）。
    """
    dot_color = "#34D399" if success else "#F59E0B"
    toast = QLabel(f'<span style="color:{dot_color};">●</span>　{text}', parent)
    toast.setStyleSheet(
        "background-color: rgba(31, 41, 55, 0.92); color: #FFFFFF;"
        "border-radius: 6px; padding: 8px 16px; font-size: 13px;",
    )
    toast.setTextFormat(Qt.TextFormat.RichText)
    toast.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    toast.adjustSize()
    x = (parent.width() - toast.width()) // 2
    toast.move(x, -toast.height())
    toast.show()

    # 滑入动画（持有引用防 GC 中断）
    anim = QPropertyAnimation(toast, b"pos", parent)
    anim.setDuration(200)
    anim.setStartValue(QPoint(x, -toast.height()))
    anim.setEndValue(QPoint(x, 24))
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    anim.start()
    toast._slide_anim = anim

    def _fade_out() -> None:
        fade = QPropertyAnimation(toast, b"windowOpacity", parent)
        fade.setDuration(300)
        fade.setStartValue(1.0)
        fade.setEndValue(0.0)
        fade.finished.connect(toast.deleteLater)
        fade.start()
        toast._fade_anim = fade

    QTimer.singleShot(duration_ms, _fade_out)
