from typing import List

from core.exceptions import FileWriteError
from core.file_io.base import BaseWriter, WriteRequest
from core.logger import log_call

# vCard 字段与内置列 key 的映射（VERSION:3.0）
_KEY_TO_VCF = {
    "name": "FN",
    "phone": "TEL;TYPE=CELL",
    "company": "ORG",
    "website": "URL",
}
_MAX_LINE_BYTES = 75


def _escape_vcf(value: str) -> str:
    """转义 vCard 文本特殊字符（\\ , ; 与 CR/LF）。"""
    return value.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;") \
        .replace("\r", "\\r").replace("\n", "\\n")


def _fold_line(line: str) -> str:
    """按 vCard 3.0 规则折叠超过 75 字节的行（续行以空格开头）。"""
    encoded = line.encode("utf-8")
    if len(encoded) <= _MAX_LINE_BYTES:
        return line
    parts = []
    for i in range(0, len(encoded), _MAX_LINE_BYTES):
        parts.append(encoded[i:i + _MAX_LINE_BYTES].decode("utf-8", errors="ignore"))
    return "\r\n ".join(parts)


class VcfWriter(BaseWriter):
    """vCard 3.0 写入器：一个手机号一条 vCard，字段按设置过滤。"""

    @log_call("core.file_io.vcf")
    def write_export(self, request: WriteRequest) -> None:
        """写入 vcf 文件：vcf_fields 中已映射且有值的字段才导出。"""
        try:
            with open(request.file_path, "w", encoding=request.encoding, newline="") as f:
                f.write("\n".join(build_vcf_lines(request)))
        except OSError as e:
            raise FileWriteError(f"无法写入文件 '{request.file_path}'：{e}") from e


def build_vcf_lines(request: WriteRequest) -> List[str]:
    """按 vcf 规则生成文件行（预览与写入共用，保证所见即所得）。

    仅导出 vcf_fields 中已映射且有值的字段；姓名应用前后缀。
    """
    if request.field_keys is None:
        raise FileWriteError("vcf 导出需要 field_keys（模板列语义 key）")
    allowed = request.vcf_fields if request.vcf_fields is not None else list(request.field_keys)
    selected = [
        (i, request.field_keys[i])
        for i in range(len(request.field_keys))
        if request.field_keys[i] in allowed and request.field_keys[i] in _KEY_TO_VCF
    ]
    lines: List[str] = []
    for row in request.data_rows:
        lines.append("BEGIN:VCARD")
        lines.append("VERSION:3.0")
        for col_idx, key in selected:
            value = row[col_idx].strip()
            if not value:
                continue
            if key == "name":
                # 姓名应用前后缀（方便通讯录批量管理）
                value = f"{request.vcf_name_prefix}{value}{request.vcf_name_suffix}"
            lines.append(_fold_line(f"{_KEY_TO_VCF[key]}:{_escape_vcf(value)}"))
        lines.append("END:VCARD")
        lines.append("")
    return lines
