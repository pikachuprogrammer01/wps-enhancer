"""设置对话框共享常量（各 tab mixin 共用）。"""

# vcf 可导出字段（v1 仅四个默认内置列）
_VCF_KEYS = ["name", "phone", "company", "website"]
_VCF_LABELS = {"name": "姓名", "phone": "手机", "company": "公司名", "website": "网址"}
_SEPARATOR_LABELS = {" ": "空格", "\t": "Tab", ",": "逗号", "、": "顿号", "|": "竖线"}
# 手机号分隔符编辑时的转义显示（空格/Tab/换行 无法直接看清）
_PHONE_SEP_DISPLAY = {" ": "[空格]", "\t": "[Tab]", "\n": "[换行]"}
_PHONE_SEP_PARSE = {v: k for k, v in _PHONE_SEP_DISPLAY.items()}
_ENCODING_LABELS = {
    "utf-8-bom": "UTF-8 带 BOM",
    "utf-8": "UTF-8",
    "gbk": "GBK",
    "utf-16": "UTF-16",
    "unicode": "Unicode（UTF-16）",
}
