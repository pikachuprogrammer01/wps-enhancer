from dataclasses import dataclass
from typing import List

from core.template.matcher import ColumnMatch
from core.template.config import Template


@dataclass
class MappingConfig:
    """导入配置：选中的模板 + 列匹配结果。"""
    template: Template
    matches: List[ColumnMatch]
