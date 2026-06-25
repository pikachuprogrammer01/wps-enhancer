from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Tuple, Optional

from core.exceptions import FileReadError


@dataclass
class SheetData:
    """从单个 Sheet 读取的全部数据。"""
    sheet_name: str
    headers: List[str]
    rows: List[Dict[str, str]]


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
    """写入输出文件所需的所有信息。"""
    file_path: str
    headers: List[str]
    data_rows: List[List[str]]
    merge_ranges: List[MergeRange]
    cell_styles: Dict[Tuple[int, int], CellStyle]


class BaseReader(ABC):
    """文件读取抽象接口。"""

    @abstractmethod
    def get_sheet_names(self, file_path: str) -> List[str]:
        """读取文件中所有 Sheet 名称。"""
        ...

    @abstractmethod
    def read_sheet(self, file_path: str, sheet_name: str) -> SheetData:
        """读取指定 Sheet 的表头和数据行。"""
        ...


class BaseWriter(ABC):
    """文件写入抽象接口。"""

    @abstractmethod
    def write_export(self, request: WriteRequest) -> None:
        """写入导出数据，含合并单元格和背景色标记。"""
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
    raise FileReadError(f"不支持的文件格式：{suffix}")
