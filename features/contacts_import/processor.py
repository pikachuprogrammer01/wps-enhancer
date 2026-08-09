import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

from core.file_io.base import SheetData, WriteRequest, MergeRange, CellStyle
from core.exceptions import DataProcessError
from core.logger import log_call
from core.settings import AppSettings
from core.template.config import Template
from core.template.matcher import ColumnMatch


@dataclass
class ExportRow:
    """单条导出数据行（一个手机号占一行；无手机映射时一源行一行）。"""
    values: List[str]           # 与模板 enabled 列一一对应的值列表
    phone_valid: bool           # 该行手机号是否通过校验（未启用校验或空号恒为 True）
    source_row_index: int       # 对应源表数据行号，从 1 开始计数，表头行不计
    merge_span: int = 1         # 同一源行拆分出的行数（1=无拆分）
    is_first_of_split: bool = False  # 拆分组首行（姓名合并起始行）


@dataclass
class PreviewData:
    """数据转换的完整预览结果。"""
    rows: List[ExportRow]
    invalid_count: int
    invalid_summary: List[str]


# 规则二允许的手机号第二位字符
_VALID_SECOND_DIGITS = {'3', '4', '5', '6', '7', '8', '9'}

# 数字截断/补零检测：科学计数法 / 长数字尾补零
_SCI_RE = re.compile(r"^[-+]?\d+(\.\d+)?[eE][-+]?\d+$")
_LONG_ZERO_RE = re.compile(r"^\d{15,}0{3,}$")


def detect_truncated_numbers(sheet_data: "SheetData") -> List[str]:
    """检测疑似数字截断/补零的单元格（手机号/身份证精度丢失）。

    两种特征（宁可漏检不误判）：
    1. 科学计数法文本（如 1.38123E+10）——浮点精度丢失的铁证
    2. 15 位以上纯数字且末尾连续 3+ 个 0——长数字补零特征
    返回每列一条提示文本，无问题返回空列表。
    """
    hints: List[str] = []
    for col in sheet_data.headers:
        samples: List[str] = []
        for row in sheet_data.rows:
            value = str(row.get(col, "")).strip()
            if _SCI_RE.match(value) or _LONG_ZERO_RE.match(value):
                samples.append(value[:20])
                if len(samples) >= 3:
                    break
        if samples:
            hints.append(
                f"列「{col}」：如 {', '.join(samples)}…"
                "（疑似号码/身份证被截断补零）"
            )
    return hints


def validate_phone(phone: str) -> bool:
    """校验单个手机号是否合法（调用方负责 strip）。"""
    if not phone:
        return True
    if phone.startswith('+'):
        return True
    if len(phone) != 11:
        return False
    if not phone.isdigit():
        return False
    if phone[0] != '1':
        return False
    if phone[1] not in _VALID_SECOND_DIGITS:
        return False
    return True


def split_phones(raw_phone: str, separators: List[str]) -> List[str]:
    """按配置的分隔符依次拆分手机号，去除空白并过滤空段。"""
    pieces = [raw_phone]
    for sep in separators:
        if not sep:
            continue
        pieces = [part for piece in pieces for part in piece.split(sep)]
    return [s.strip() for s in pieces if s.strip()]


def _enabled_matches(matches: List[ColumnMatch]) -> List[ColumnMatch]:
    """返回模板中 enabled 列的匹配结果（顺序与模板列一致）。"""
    return [m for m in matches if m.template_col.enabled]


def _source_value(row: Dict[str, str], match: ColumnMatch) -> str:
    """取源行中该匹配列的值（strip 后；未匹配返回空串）。"""
    if match.source_col is None:
        return ""
    return row.get(match.source_col, "").strip()


def _build_values(
    row: Dict[str, str], matches: List[ColumnMatch], phone_value: str,
) -> List[str]:
    """按 enabled 列顺序构建一行导出值（phone 列用拆分后的单段值）。"""
    values: List[str] = []
    for match in matches:
        if match.template_col.key == "phone":
            values.append(phone_value)
        else:
            values.append(_source_value(row, match))
    return values


def _process_row(
    row: Dict[str, str], matches: List[ColumnMatch], has_phone: bool,
    row_index: int, validate: bool, separators: List[str],
) -> Tuple[List[ExportRow], List[str]]:
    """处理单个源数据行，返回 ExportRow 列表与无效手机号描述列表。"""
    if not has_phone:
        return [ExportRow(
            values=_build_values(row, matches, ""),
            phone_valid=True,
            source_row_index=row_index,
        )], []

    phone_match = next(m for m in matches if m.template_col.key == "phone")
    phones = split_phones(_source_value(row, phone_match), separators)
    if not phones:
        phones = [""]
    rows: List[ExportRow] = []
    invalids: List[str] = []
    for i, phone in enumerate(phones):
        valid = validate_phone(phone) if validate else True
        rows.append(ExportRow(
            values=_build_values(row, matches, phone),
            phone_valid=valid,
            source_row_index=row_index,
            merge_span=len(phones),
            is_first_of_split=(i == 0),
        ))
        if not valid:
            invalids.append(f"第 {row_index} 行：{phone} 不是合法手机号")
    return rows, invalids


def group_by_name(
    rows: List[ExportRow], name_index: int, merge_enabled: bool,
) -> List[ExportRow]:
    """按姓名分组（保持首次出现顺序）：组内除首行外姓名置空，并标记合并跨度。

    未启用合并或无姓名列时原样返回；空姓名行不参与分组（独立成行）。
    """
    if not merge_enabled or name_index < 0:
        return rows
    groups: Dict[str, List[ExportRow]] = {}
    order: List[str] = []
    result: List[ExportRow] = []
    for row in rows:
        name = row.values[name_index]
        if not name:
            result.append(row)  # 空姓名行独立，不参与合并
            continue
        if name not in groups:
            groups[name] = []
            order.append(name)
        groups[name].append(row)
    for name in order:
        group = groups[name]
        for i, row in enumerate(group):
            if i > 0:
                row.values[name_index] = ""  # 合并单元格：仅组首行显示姓名
            row.is_first_of_split = (i == 0)
            row.merge_span = len(group)
            result.append(row)
    return result


@log_call("contacts_import.processor", log_args=True, log_result=False)
def build_preview_data(
    data: SheetData, template: Template, matches: List[ColumnMatch],
    settings: AppSettings,
) -> PreviewData:
    """将 SheetData 转换为 PreviewData（按映射填充 + 按设置拆分/校验/分组合并）。"""
    enabled = _enabled_matches(matches)
    has_phone = any(m.template_col.key == "phone" and m.source_col for m in enabled)
    name_index = next(
        (i for i, m in enumerate(enabled) if m.template_col.key == "name"),
        -1,
    )
    all_rows: List[ExportRow] = []
    invalid_summary: List[str] = []
    try:
        for row_index, row in enumerate(data.rows, start=1):
            rows, invalids = _process_row(
                row, enabled, has_phone, row_index,
                settings.phone_validate, settings.phone_separators,
            )
            all_rows.extend(rows)
            invalid_summary.extend(invalids)
        all_rows = group_by_name(all_rows, name_index, settings.phone_merge)
    except Exception as e:
        raise DataProcessError(f"数据处理失败：{e}") from e
    return PreviewData(
        rows=all_rows,
        invalid_count=len(invalid_summary),
        invalid_summary=invalid_summary,
    )


def _build_merge_ranges(
    rows: List[ExportRow], name_col_index: int, merge_enabled: bool,
) -> List[MergeRange]:
    """构建姓名列合并范围（拆分组连续行合并）。"""
    if not merge_enabled or name_col_index < 0:
        return []
    ranges: List[MergeRange] = []
    for i, row in enumerate(rows):
        if row.is_first_of_split and row.merge_span > 1:
            ranges.append(MergeRange(
                row_start=i,
                row_end=i + row.merge_span - 1,
                col_index=name_col_index,
            ))
    return ranges


def _build_cell_styles(
    rows: List[ExportRow], phone_col_index: int, highlight_enabled: bool,
) -> Dict[Tuple[int, int], CellStyle]:
    """构建非法手机号单元格的红色背景样式。"""
    styles: Dict[Tuple[int, int], CellStyle] = {}
    if not highlight_enabled or phone_col_index < 0:
        return styles
    for i, row in enumerate(rows):
        if not row.phone_valid:
            styles[(i, phone_col_index)] = CellStyle(background_color="#FF0000")
    return styles


@log_call("contacts_import.processor", log_args=True, log_result=False)
def build_write_request(
    preview: PreviewData, template: Template, matches: List[ColumnMatch],
    settings: AppSettings, output_path: str,
) -> WriteRequest:
    """将 PreviewData 转换为 WriteRequest（headers 来自模板 enabled 列）。"""
    enabled = _enabled_matches(matches)
    headers = [m.template_col.name for m in enabled]
    field_keys = [m.template_col.key for m in enabled]
    phone_index = next(
        (i for i, m in enumerate(enabled) if m.template_col.key == "phone"),
        -1,
    )
    name_index = next(
        (i for i, m in enumerate(enabled) if m.template_col.key == "name"),
        -1,
    )
    data_rows = [row.values for row in preview.rows]
    if _output_suffix(output_path) == "vcf":
        # vcf：同一姓名多个手机号时姓名追加 _1/_2 序号（仅 vcf，其余格式不受影响）
        data_rows = _vcf_indexed_rows(
            data_rows, [r.merge_span for r in preview.rows], name_index,
        )
    merge_ranges = _build_merge_ranges(preview.rows, name_index, settings.phone_merge)
    cell_styles = _build_cell_styles(preview.rows, phone_index, settings.phone_highlight)
    return WriteRequest(
        file_path=output_path,
        headers=headers,
        data_rows=data_rows,
        merge_ranges=merge_ranges,
        cell_styles=cell_styles,
        field_keys=field_keys,
        encoding=_output_encoding(output_path, settings),
        separator=settings.txt_separator,
        vcf_fields=list(settings.vcf_fields),
        vcf_name_prefix=_effective_vcf_prefix(settings),
        vcf_name_suffix=_effective_vcf_suffix(settings),
    )


def _output_suffix(output_path: str) -> str:
    """返回输出文件后缀（无后缀返回空串）。"""
    return output_path.lower().rsplit(".", 1)[-1] if "." in output_path else ""


def _vcf_indexed_rows(
    rows: List[List[str]], spans: List[int], name_index: int,
) -> List[List[str]]:
    """vcf 导出行：同姓名多手机号（merge_span>1 的组）姓名追加 _1/_2 序号。

    序号按组内位置从 1 累加；单行组不加序号；姓名已为空的行不追加。
    """
    if name_index < 0:
        return rows
    result = [list(r) for r in rows]
    i = 0
    while i < len(result):
        span = spans[i]
        if span > 1:
            # 预览截断时组可能被切断：实际组内行数 = min(span, 剩余行数)
            group_end = min(i + span, len(result))
            # vcf 无合并概念：组内被置空的姓名恢复为组首姓名
            base_name = next(
                (
                    result[j][name_index]
                    for j in range(i, group_end) if result[j][name_index]
                ),
                "",
            )
            for k in range(group_end - i):
                idx = i + k
                if result[idx][name_index]:
                    result[idx][name_index] = f"{result[idx][name_index]}_{k + 1}"
                elif base_name:
                    result[idx][name_index] = f"{base_name}_{k + 1}"
            i = group_end
        else:
            i += 1
    return result


def _vcf_timestamp(settings: AppSettings) -> str:
    """返回年月日时间戳（开关关闭时为空串）。"""
    if not settings.vcf_timestamp:
        return ""
    from datetime import datetime
    return datetime.now().strftime("%Y%m%d")


def _effective_vcf_prefix(settings: AppSettings) -> str:
    """返回 vcf 姓名前缀实际值（时间戳在姓名前时附加年月日）。"""
    ts = _vcf_timestamp(settings)
    if not ts or settings.vcf_timestamp_position != "prefix":
        return settings.vcf_name_prefix
    return f"{settings.vcf_name_prefix}{ts}"


def _effective_vcf_suffix(settings: AppSettings) -> str:
    """返回 vcf 姓名后缀实际值（时间戳在姓名后时附加年月日）。"""
    ts = _vcf_timestamp(settings)
    if not ts or settings.vcf_timestamp_position != "suffix":
        return settings.vcf_name_suffix
    return f"{settings.vcf_name_suffix}{ts}"


@log_call("contacts_import.processor", log_args=True, log_result=False)
def build_preview_display(
    preview: PreviewData, matches: List[ColumnMatch],
    settings: AppSettings, fmt: str,
) -> Tuple[List[str], List[List[str]]]:
    """按导出格式生成预览表头与行内容（与导出文件展示一致）。

    vcf：仅保留 vcf_fields 且 vcf 支持的字段列，姓名应用前后缀；
    其他格式：模板 enabled 全部列，原值展示。
    """
    enabled = _enabled_matches(matches)
    keep = [
        i for i, m in enumerate(enabled)
        if fmt == "vcf" and m.template_col.key in settings.vcf_fields
        or fmt != "vcf"
    ]
    headers = [enabled[i].template_col.name for i in keep]
    name_key_idx = next(
        (i for i, m in enumerate(enabled) if m.template_col.key == "name"),
        -1,
    )
    rows: List[List[str]] = []
    for row in preview.rows:
        values = [row.values[i] for i in keep]
        if fmt == "vcf" and name_key_idx >= 0:
            name_pos = keep.index(name_key_idx) if name_key_idx in keep else -1
            if name_pos >= 0 and values[name_pos]:
                values[name_pos] = (
                    f"{settings.vcf_name_prefix}{values[name_pos]}"
                    f"{settings.vcf_name_suffix}"
                )
        rows.append(values)
    return headers, rows


@log_call("contacts_import.processor", log_args=True, log_result=False)
def build_text_preview(
    preview: PreviewData, matches: List[ColumnMatch],
    settings: AppSettings, fmt: str, row_limit: int = 30,
) -> str:
    """生成 csv/txt/vcf 的文本预览（与导出文件内容一致，最多前 row_limit 行数据）。

    csv/txt：表头 + 分隔符连接的数据行；vcf：完整 vCard 文本（含姓名前后缀）。
    """
    enabled = _enabled_matches(matches)
    headers = [m.template_col.name for m in enabled]
    data_rows = [row.values for row in preview.rows[:row_limit]]
    if fmt == "vcf":
        from core.file_io.base import WriteRequest
        from core.file_io.vcf_handler import build_vcf_lines
        name_index = next(
            (i for i, m in enumerate(enabled) if m.template_col.key == "name"),
            -1,
        )
        # 先对全量行做序号（组完整性），再截断显示行数
        all_rows = _vcf_indexed_rows(
            [r.values for r in preview.rows],
            [r.merge_span for r in preview.rows], name_index,
        )
        data_rows = all_rows[:row_limit]
        request = WriteRequest(
            file_path="",
            headers=headers,
            data_rows=data_rows,
            field_keys=[m.template_col.key for m in enabled],
            vcf_fields=list(settings.vcf_fields),
            vcf_name_prefix=_effective_vcf_prefix(settings),
            vcf_name_suffix=_effective_vcf_suffix(settings),
        )
        return "\n".join(build_vcf_lines(request))
    if fmt == "csv":
        from core.file_io.csv_handler import build_csv_text
        return build_csv_text(headers, data_rows)
    from core.file_io.txt_handler import build_txt_text
    return build_txt_text(headers, data_rows, settings.txt_separator)


def _output_encoding(output_path: str, settings: AppSettings) -> str:
    """按输出格式选择编码：csv 用 csv 编码，txt 用 txt 编码，其余固定 utf-8。"""
    suffix = output_path.lower().rsplit(".", 1)[-1] if "." in output_path else ""
    if suffix == "txt":
        return settings.txt_encoding
    if suffix == "csv":
        return settings.csv_encoding
    return "utf-8"  # vcf/xlsx/xls 固定 UTF-8
