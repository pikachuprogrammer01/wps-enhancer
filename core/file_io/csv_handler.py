import csv
import io
from pathlib import Path
from typing import List, Optional, Tuple

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


_DELIMITER_CANDIDATES = (",", ";", "\t", "|")


def _detect_delimiter(text: str) -> str:
    """探测 csv 分隔符（逗号/分号/制表符/竖线），取首个数据行中出现最多者。

    中文环境常见分号分隔，默认 csv.reader 仅认逗号会导致整列错位。
    """
    sample = ""
    for line in text.splitlines():
        if line.strip() and not line.strip().startswith(("#", "//")):
            sample = line
            break
    best, best_count = ",", 0
    for cand in _DELIMITER_CANDIDATES:
        count = sample.count(cand)
        if count > best_count:
            best, best_count = cand, count
    return best


class CsvReader(BaseReader):
    """基于标准库 csv 的读取器（编码自动探测，无 Sheet 概念）。"""

    @log_call("core.file_io.csv")
    def get_sheet_names(self, file_path: str) -> List[str]:
        """返回单个伪 Sheet 名称（文件名不含扩展名）。"""
        return [Path(file_path).stem]

    @log_call("core.file_io.csv")
    def get_sheet_summaries(self, file_path: str) -> List[Tuple[str, int]]:
        """返回单个伪 Sheet（文件名不含扩展名 + 二进制行数近似）。"""
        rows = 0
        try:
            with open(file_path, "rb") as f:
                rows = sum(1 for _ in f)
        except OSError:
            rows = 0
        return [(Path(file_path).stem, rows)]

    @log_call("core.file_io.csv")
    def read_sheet(
        self, file_path: str, sheet_name: str,
        skip_declaration: bool = False,
        declaration_keywords: Optional[List[str]] = None,
        separator: Optional[str] = None,
        encoding: Optional[str] = None,
    ) -> SheetData:
        """读取 csv/txt 内容：第一行为表头（可选剔除首行声明）。

        separator/encoding 为 None 时自动检测；指定时按用户设置执行，
        若文件格式与之不符（列数异常/编码非法）抛出明确提示。
        """
        try:
            raw = Path(file_path).read_bytes()
            if encoding and encoding != "auto":
                try:
                    text = raw.decode(encoding)
                except (LookupError, UnicodeDecodeError) as e:
                    raise FileReadError(
                        f"文件 '{file_path}' 不是 {encoding} 编码"
                        f"（请在设置中选择正确的数据源编码）",
                    ) from e
            else:
                text = raw.decode(_detect_encoding(raw))
        except (OSError, UnicodeDecodeError) as e:
            raise FileReadError(f"无法读取文件 '{file_path}'：{e}") from e

        delim = _detect_delimiter(text) if not separator or separator == "auto" \
            else separator
        # 指定分隔符校验：数据行中完全不存在该分隔符 → 明确报错（防静默错位）
        if separator and separator != "auto":
            sample = ""
            for line in text.splitlines():
                if line.strip():
                    sample = line
                    break
            if sample and separator not in sample:
                sep_display = {
                    "\t": "制表符 Tab", ",": "逗号 ,", ";": "分号 ;", "|": "竖线 |",
                }.get(separator, separator)
                raise FileReadError(
                    f"文件 '{file_path}' 未发现「{sep_display}」分隔符，"
                    "请检查设置中的数据源分隔符是否正确",
                )
        rows = list(csv.reader(text.splitlines(), delimiter=delim))
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
        # 列数校验：仅多列表头时启用（单列表头可能是声明行/单列文本，交由声明检测）
        # 某行列数超过表头即格式异常（尾空字段被 csv 截断属正常，不报）
        bad_rows = [
            (i + 2, len(row)) for i, row in enumerate(rows[1:])
            if len(headers) >= 2 and len(row) > len(headers)
        ]
        if bad_rows:
            first_line, cols = bad_rows[0]
            raise FileReadError(
                f"文件 '{file_path}' 第 {first_line} 行有 {cols} 列，"
                f"超出表头 {len(headers)} 列：请检查文件是否为纯文本表格，"
                "并在设置中选择正确的数据源分隔符",
            )
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
