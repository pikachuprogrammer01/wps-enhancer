"""全局 UI 主题：统一配色、圆角、hover 态（QSS）。

主窗口/对话框通过 apply_global_theme(app) 应用；局部样式优先级高于全局 QSS，
已有个性化样式的控件（如功能卡片）不受影响。
"""

PRIMARY = "#3B82F6"          # 主色（现代蓝）
PRIMARY_HOVER = "#2563EB"    # hover/按下
PRIMARY_LIGHT = "#E8F0FE"    # 选中底色
BG = "#F5F7FA"               # 窗口背景
CARD_BG = "#FFFFFF"          # 卡片/输入框背景
BORDER = "#E5E7EB"           # 边框
TEXT = "#1F2937"             # 主文字
TEXT_SECONDARY = "#6B7280"   # 次要文字

GLOBAL_QSS = f"""
QWidget {{
    font-family: "PingFang SC", "Microsoft YaHei", "Helvetica Neue", sans-serif;
    font-size: 13px;
    color: {TEXT};
}}
QMainWindow, QDialog {{
    background-color: {BG};
}}
QPushButton {{
    background-color: {PRIMARY};
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    padding: 6px 12px;
}}
QPushButton:hover {{ background-color: {PRIMARY_HOVER}; }}
QPushButton:pressed {{ background-color: {PRIMARY_HOVER}; }}
QPushButton:disabled {{ background-color: #A5C4F5; }}
QLineEdit, QPlainTextEdit, QComboBox {{
    background-color: {CARD_BG};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 4px 8px;
}}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{
    border: 1px solid {PRIMARY};
}}
/* 下拉框箭头：border 三角替代系统默认箭头 */
QComboBox::drop-down {{
    border: none;
    width: 26px;
}}
QComboBox::down-arrow {{
    width: 0;
    height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {TEXT_SECONDARY};
    margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background-color: {CARD_BG};
    border: 1px solid {BORDER};
    border-radius: 6px;
    selection-background-color: {PRIMARY_LIGHT};
    selection-color: {TEXT};
    outline: none;
}}
/* 顶部工具栏（设置入口）：白底 + 底部细线，与全局主题协调 */
QToolBar {{
    background-color: {CARD_BG};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 4px 8px;
    spacing: 4px;
}}
QToolBar::separator {{
    background-color: {BORDER};
    width: 1px;
    margin: 4px 8px;
}}
QToolBar QToolButton {{
    color: {TEXT_SECONDARY};
    border-radius: 6px;
    padding: 4px 10px;
}}
QToolBar QToolButton:hover {{
    background-color: #F3F4F6;
    color: {PRIMARY};
}}
QToolBar QToolButton:checked {{
    background-color: {PRIMARY_LIGHT};
    color: {PRIMARY};
}}
QTableWidget {{
    background-color: {CARD_BG};
    border: 1px solid {BORDER};
    border-radius: 6px;
    gridline-color: #F0F2F5;
}}
QHeaderView::section {{
    background-color: #F9FAFB;
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 6px;
    font-weight: bold;
}}
QTableWidget::item:selected {{
    background-color: {PRIMARY_LIGHT};
    color: {TEXT};
}}
QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    margin-top: 10px;
    padding-top: 8px;
    background-color: {CARD_BG};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: {TEXT_SECONDARY};
}}
QCheckBox {{ spacing: 6px; }}
QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    background: {CARD_BG};
}}
QTabBar::tab {{
    background: transparent;
    padding: 6px 16px;
    color: {TEXT_SECONDARY};
}}
QTabBar::tab:selected {{
    color: {PRIMARY};
    font-weight: bold;
    border-bottom: 2px solid {PRIMARY};
}}
"""


def apply_global_theme(app) -> None:
    """应用全局主题（幂等，重复调用安全）。"""
    app.setStyleSheet(GLOBAL_QSS)
