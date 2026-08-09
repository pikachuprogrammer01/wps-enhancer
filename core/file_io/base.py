from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.exceptions import FileReadError, FileWriteError


@dataclass
class SheetData:
    """从单个 Sheet 读取的全部数据。"""
    sheet_name: str
    headers: List[str]
    rows: List[Dict[str, str]]
    declaration_skipped: bool = False  # 是否跳过了首行声明（企查查导出）


@dataclass
class CellStyle:
    """单元格样式描述。"""
    background_color: Optional[str] = None


@dataclass
class MergeRange:
    """合并单元格范围（数据区 0 索引，不含表头行）。"""
    row_start: int
    row_end: int
    col_index: int


@dataclass
class WriteRequest:
    """写入输出文件所需的所有信息（通用列结构）。"""
    file_path: str
    headers: List[str]
    data_rows: List[List[str]]
    merge_ranges: List[MergeRange] = field(default_factory=list)
    cell_styles: Dict[Tuple[int, int], CellStyle] = field(default_factory=dict)
    field_keys: Optional[List[str]] = None   # 与 headers 对应的语义 key（vcf 导出必需）
    encoding: str = "utf-8"                  # csv/txt 输出编码
    separator: str = " "                     # txt 行内分隔符
    vcf_fields: Optional[List[str]] = None   # vcf 导出字段（内置列 key 列表，None=全部）
    vcf_name_prefix: str = ""                # vcf 导出姓名前缀（方便通讯录批量管理）
    vcf_name_suffix: str = ""


def is_empty_row(row: List[object]) -> bool:
    """判断一行是否全空（None/空串/纯空白）。"""
    return not any(c is not None and str(c).strip() for c in row)


def is_declaration_first_row(
    first_row: List[object], second_row: List[object],
    keywords: Optional[List[str]] = None,
) -> bool:
    """判断首行是否为导出声明行（防误判优先，纯函数）。

    规则（按序，命中即停）：
    1. 首行全空 → 声明行（前导空行）
    2. 首行仅 1 个非空单元格且次行非空 ≥ 2 → 声明行（结构判定，不依赖关键词）
    3. 首行仅 1 个非空单元格且内容命中关键词 → 声明行（单格关键词判定）
    4. 多格行（非空 ≥ 2）→ 不判为声明行（避免正常表头含「声明/数据来源」等词被误判）
    """
    first_non_empty = [c for c in first_row if c is not None and str(c).strip()]
    if not first_non_empty:
        return True
    if len(first_non_empty) != 1:
        return False  # 多格行不参与关键词判定（防误判）
    cell = str(first_non_empty[0])
    if keywords and any(k in cell for k in keywords):
        return True
    second_non_empty = [c for c in second_row if c is not None and str(c).strip()]
    return len(second_non_empty) >= 2


class BaseReader(ABC):
    """文件读取抽象接口。"""

    @abstractmethod
    def get_sheet_names(self, file_path: str) -> List[str]:
        """读取文件中所有 Sheet 名称（csv 返回单个文件名）。"""
        ...

    @abstractmethod
    def get_sheet_summaries(self, file_path: str) -> List[Tuple[str, int]]:
        """读取所有 Sheet 的名称与数据行数（下拉选择时展示，便于区分同名/纯数字 Sheet）。"""
        ...

    @abstractmethod
    def read_sheet(
        self, file_path: str, sheet_name: str,
        skip_declaration: bool = False,
        declaration_keywords: Optional[List[str]] = None,
        separator: Optional[str] = None,
        encoding: Optional[str] = None,
    ) -> SheetData:
        """读取指定 Sheet 的表头和数据行；skip_declaration 时按声明规则剔除首行声明。

        separator/encoding 仅对 csv/txt 数据源生效（None=自动检测）。
        """
        ...


class BaseWriter(ABC):
    """文件写入抽象接口。"""

    @abstractmethod
    def write_export(self, request: WriteRequest) -> None:
        """写入导出数据；xlsx/xls 含合并与标红，csv/vcf/txt 按 request 参数。"""
        ...


def get_reader(file_path: str) -> BaseReader:
    """根据文件扩展名返回对应的 Reader 实例。"""
    suffix = Path(file_path).suffix.lower()
    if suffix == ".xlsx":
        from core.file_io.xlsx_handler import XlsxReader
        return XlsxReader()
    if suffix == ".xls":
        from core.file_io.xls_handler import XlsReader
        return XlsReader()
    if suffix == ".csv":
        from core.file_io.csv_handler import CsvReader
        return CsvReader()
    if suffix == ".txt":
        from core.file_io.csv_handler import CsvReader  # txt 复用分隔文本读取
        return CsvReader()
    raise FileReadError(f"不支持的文件格式：{suffix}")


def get_writer(file_path: str) -> BaseWriter:
    """根据文件扩展名返回对应的 Writer 实例。"""
    suffix = Path(file_path).suffix.lower()
    if suffix == ".xlsx":
        from core.file_io.xlsx_handler import XlsxWriter
        return XlsxWriter()
    if suffix == ".xls":
        from core.file_io.xls_handler import XlsWriter
        return XlsWriter()
    if suffix == ".csv":
        from core.file_io.csv_handler import CsvWriter
        return CsvWriter()
    if suffix == ".vcf":
        from core.file_io.vcf_handler import VcfWriter
        return VcfWriter()
    if suffix == ".txt":
        from core.file_io.txt_handler import TxtWriter
        return TxtWriter()
    raise FileWriteError(f"不支持的输出格式：{suffix}")
