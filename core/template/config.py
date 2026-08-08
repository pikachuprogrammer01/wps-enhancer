from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class TemplateColumn:
    """模板中的一列。"""
    key: str                # 语义键（稳定标识：name/phone/company/website/custom_<n>）
    name: str               # 列显示名（导出表头）
    enabled: bool = True    # 导出时是否包含


@dataclass
class Template:
    """一个模板 = 名称 + 列集合 + 可选建议映射（key → 源列名，应用时优先恢复）。"""
    name: str
    columns: List[TemplateColumn]
    mappings: Dict[str, str] = field(default_factory=dict)


@dataclass
class BuiltinColumn:
    """内置列（语义字段），可增删改查。"""
    key: str                # 语义键（创建时分配，不再修改）
    label: str              # 显示名（用户可改）
    aliases: List[str] = field(default_factory=list)  # 匹配别名（用户可维护）


def default_builtin_columns() -> List[BuiltinColumn]:
    """返回默认内置列列表（姓名/手机/公司名/网址），每次调用返回全新实例。"""
    return [
        BuiltinColumn(
            key="name", label="姓名",
            aliases=["姓名", "姓", "名称", "联系人", "名字"],
        ),
        BuiltinColumn(
            key="phone", label="手机",
            aliases=["手机", "手机号", "电话", "联系电话", "有效手机号",
                     "家庭手机", "手机号码", "联系方式"],
        ),
        BuiltinColumn(
            key="company", label="公司名",
            aliases=["公司", "公司名", "公司名称", "单位", "企业名称"],
        ),
        BuiltinColumn(
            key="website", label="网址",
            aliases=["网址", "官网", "网站", "官网网址", "主页", "网址链接"],
        ),
    ]
