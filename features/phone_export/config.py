from dataclasses import dataclass
from typing import List

# WPS 通讯录导入模板的完整 25 列表头
TARGET_HEADERS: List[str] = [
    "姓", "名", "昵称", "QQ号", "家庭手机", "工作手机", "其他手机",
    "家庭电话", "工作电话", "其他电话", "家庭传真", "工作传真",
    "公司/部门", "家庭地址", "工作地址", "其他地址", "备注",
    "电子邮件", "家庭邮箱", "办公邮箱", "网址", "家庭网址", "办公网址",
    "生日", "职务",
]


@dataclass
class ColumnMapping:
    """手机号导出的列映射配置。"""
    source_name_col: str = "法定代表人"    # 源表姓名列名
    source_phone_col: str = "有效手机号"   # 源表手机号列名
    target_name_col: str = "姓"            # 目标表姓名列名
    target_phone_col: str = "家庭手机"     # 目标表手机号列名
    target_name_index: int = 0             # 姓名列在目标模板中的索引
    target_phone_index: int = 4            # 手机号列在目标模板中的索引
