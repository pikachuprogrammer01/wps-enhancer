import csv
import io
from pathlib import Path
from typing import List, Optional

from core.exceptions import FileReadError, FileWriteError
from core.file_io.base import (
    BaseReader, BaseWriter, SheetData, WriteRequest,
    is_declaration_first_row, is_empty_row,
)
from core.logger import log_call

# csv 写入编码映射（unicode 即 UTF-16 LE 带 BOM）
_ENCODING_MAP = {
    "utf-8-bom": "utf-8-sig",
    "utf-8": "utf-8",
    "gbk": "gbk",
    "utf-16": "utf-16",
    "unicode": "utf-16",
}


def _detect_encoding(raw: bytes) -> str:
    """探测 csv 文件编码（BOM → UTF-8 → GBK）。"""
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return "utf-16"
    try:
        raw.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        return "gbk"


class CsvReader(BaseReader):
    """基于标准库 csv 的读取器（编码自动探测，无 Sheet 概念）。"""

    @log_call("core.file_io.csv")
    def get_sheet_names(self, file_path: str) -> List[str]:
        """返回单个伪 Sheet 名称（文件名不含扩展名）。"""
        return [Path(file_path).stem]

    @log_call("core.file_io.csv")
    def read_sheet(
        self, file_path: str, sheet_name: str,
        skip_declaration: bool = False,
        declaration_keywords: Optional[List[str]] = None,
    ) -> SheetData:
        """读取 csv 内容：第一行为表头（可选剔除首行声明）。"""
        try:
            raw = Path(file_path).read_bytes()
            encoding = _detect_encoding(raw)
            text = raw.decode(encoding)
        except (OSError, UnicodeDecodeError) as e:
            raise FileReadError(f"无法读取文件 '{file_path}'：{e}") from e

        rows = list(csv.reader(text.splitlines()))
        # 跳过前导空行（声明行前常见空行）
        while rows and is_empty_row(rows[0]):
            rows.pop(0)
        if not rows:
            raise FileReadError(f"无法读取文件 '{file_path}'：文件为空")
        skipped = False
        if skip_declaration and len(rows) >= 2 and is_declaration_first_row(
            rows[0], rows[1], declaration_keywords,
        ):
            rows = rows[1:]
            skipped = True
            # 声明行后可能跟空行
            while rows and is_empty_row(rows[0]):
                rows.pop(0)
        headers = [str(cell).strip() for cell in rows[0]]
        if not any(headers):
            raise FileReadError(f"无法读取文件 '{file_path}'：首行为空，无法确定表头")
        data_rows = []
        for row in rows[1:]:
            row_dict = {}
            for i, header in enumerate(headers):
                value = row[i] if i < len(row) else ""
                row_dict[header] = str(value)
            data_rows.append(row_dict)
        return SheetData(
            sheet_name=Path(file_path).stem,
            headers=headers,
            rows=data_rows,
            declaration_skipped=skipped,
        )


class CsvWriter(BaseWriter):
    """基于标准库 csv 的写入器（编码按设置，含 BOM 支持）。"""

    @log_call("core.file_io.csv")
    def write_export(self, request: WriteRequest) -> None:
        """写入 csv 文件：首行表头 + 数据行，编码按 request.encoding。"""
        encoding = _ENCODING_MAP.get(request.encoding, "utf-8-sig")
        try:
            with open(request.file_path, "w", encoding=encoding, newline="") as f:
                writer = csv.writer(f, lineterminator="\r\n")
                writer.writerow(request.headers)
                for row in request.data_rows:
                    writer.writerow(row)
        except OSError as e:
            raise FileWriteError(f"无法写入文件 '{request.file_path}'：{e}") from e


def build_csv_text(headers: List[str], rows: List[List[str]]) -> str:
    """按 csv 规则生成文件文本（预览与写入共用；行结束符归一为 \\n 便于展示）。"""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    return buf.getvalue()
