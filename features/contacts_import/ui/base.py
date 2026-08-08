"""contacts_import 界面层共用基础：常量、安全槽包装、弹窗共享引用。

弹窗类（QMessageBox/QInputDialog/QFileDialog）统一从本模块引用，
测试只需 patch 本模块的属性即可屏蔽所有面板弹窗（from X import Y
的绑定方式 patch 不生效，因此各模块用 `from ... import base as _dlg`
后以 `_dlg.QMessageBox` 属性访问）。
"""

from PyQt6.QtWidgets import QFileDialog, QInputDialog, QMessageBox

__all__ = ["QFileDialog", "QInputDialog", "QMessageBox", "_safe_slot"]

# ---------- 常量 ----------

_PREVIEW_LIMIT = 30
_SOURCE_PREVIEW_LIMIT = 10
_DEFAULT_MAPPING_NAME = "（默认映射：内置列）"
_STEP_NAMES = ["① 数据源", "② 列映射", "③ 预览与导出"]
# 模板表格末行新建提示（双击输入创建模板（格式：通过顿号分隔））
_TEMPLATE_CREATE_HINT = "双击输入创建模板（格式：通过顿号分隔）"
# 预览页 vcf 自定义的字段选项（与全局设置 vcf_fields 联动）
_VCF_FIELD_KEYS = ["name", "phone", "company", "website"]
_VCF_FIELD_LABELS = ["姓名", "手机", "公司名", "网址"]
_MAX_COL_WIDTH = 240  # 表格列宽上限（防长内容撑破 app 窗口）
_SOURCE_COL_WIDTH = 180
# 每种格式对应的保存对话框 filter（按所选格式传入，确保后缀正确）
_FORMAT_FILTERS = {
    "xlsx": "Excel 文件 (*.xlsx)",
    "xls": "Excel 文件 (*.xls)",
    "csv": "CSV 文件 (*.csv)",
    "vcf": "vCard 文件 (*.vcf)",
    "txt": "文本文件 (*.txt)",
}
# 列映射匹配状态显示文本
_STATUS_TEXT = {
    "manual": "手动",
    "exact": "自动匹配",
    "alias": "自动匹配",
    "none": "未匹配",
}

# ---------- 工具 ----------

import functools

from core.logger import get_logger


def _safe_slot(func):
    """槽函数安全包装：任何异常记录日志并提示，绝不让 PyQt6 以 qFatal 退出 app。

    PyQt6 槽内未捕获异常会触发 qFatal → abort（无法用 excepthook/handler 拦截），
    因此所有 Qt 槽必须经此包装保证异常不外泄。
    """

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except Exception as e:  # 兜底：任何异常都不得让 app 退出
            get_logger("contacts_import.panel").exception(
                f"槽函数 {func.__name__} 异常：{e}",
            )
            try:
                QMessageBox.critical(
                    self, "错误",
                    f"发生错误：{e}\n详情见日志",
                )
            except Exception:
                pass
    return wrapper
