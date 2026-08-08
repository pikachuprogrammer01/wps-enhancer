from typing import List, Optional

from core.exceptions import FileWriteError
from core.file_io.base import BaseWriter, WriteRequest
from core.logger import log_call

# 设置编码名 → Python 编码名（utf-8-bom 需映射为 utf-8-sig）
_ENCODING_MAP = {
    "utf-8-bom": "utf-8-sig",
    "utf-16": "utf-16",
    "unicode": "utf-16",
}


class TxtWriter(BaseWriter):
    """文本写入器：首行表头 + 数据行，分隔符与编码按设置。"""

    @log_call("core.file_io.txt")
    def write_export(self, request: WriteRequest) -> None:
        """写入 txt 文件：表头行 + 数据行，行内用 request.separator 连接。"""
        encoding = _ENCODING_MAP.get(request.encoding, request.encoding)
        try:
            with open(request.file_path, "w", encoding=encoding, newline="") as f:
                f.write(build_txt_text(request.headers, request.data_rows, request.separator))
        except OSError as e:
            raise FileWriteError(f"无法写入文件 '{request.file_path}'：{e}") from e


def build_txt_text(
    headers: List[str], rows: List[List[str]], separator: Optional[str],
) -> str:
    """按 txt 规则生成文件文本（预览与写入共用）：行内用分隔符连接，末尾换行。"""
    sep = separator if separator else " "
    lines = [sep.join(headers)]
    for row in rows:
        lines.append(sep.join(row))
    return "\n".join(lines) + "\n"
