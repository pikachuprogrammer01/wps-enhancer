from dataclasses import dataclass
from typing import Dict, List, Tuple

from core.file_io.base import SheetData, WriteRequest, MergeRange, CellStyle
from core.exceptions import ColumnNotFoundError, DataProcessError
from features.phone_export.config import ColumnMapping, TARGET_HEADERS


@dataclass
class ExportRow:
    """单条导出数据行（一个手机号占一行）。"""
    name: str
    phone: str
    merge_span: int
    is_name_cell: bool
    phone_valid: bool
    source_row_index: int


@dataclass
class PreviewData:
    """数据转换的完整预览结果。"""
    rows: List[ExportRow]
    invalid_count: int
    invalid_summary: List[str]


# 规则二允许的手机号第二位字符
_VALID_SECOND_DIGITS = {'3', '4', '5', '6', '7', '8', '9'}


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


def split_phones(raw_phone: str) -> List[str]:
    """按分号分割手机号，去除空白并过滤空字符串。"""
    segments = raw_phone.split(';')
    result = [s.strip() for s in segments]
    result = [s for s in result if s]
    return result


def validate_columns(data: SheetData, mapping: ColumnMapping) -> None:
    """校验 mapping 中配置的列名是否存在于 SheetData 的 headers 中。"""
    for col in [mapping.source_name_col, mapping.source_phone_col]:
        if col not in data.headers:
            raise ColumnNotFoundError(
                f"列 '{col}' 在 Sheet '{data.sheet_name}' 中不存在，"
                f"当前列名为：{data.headers}"
            )


def build_export_rows(name: str, phones: List[str], row_index: int) -> List[ExportRow]:
    """将单个姓名的手机号列表转换为 ExportRow 列表。"""
    if not phones:
        return [ExportRow(
            name=name, phone="", merge_span=1,
            is_name_cell=True, phone_valid=True, source_row_index=row_index,
        )]
    count = len(phones)
    result = []
    for i, phone in enumerate(phones):
        result.append(ExportRow(
            name=name, phone=phone, merge_span=count,
            is_name_cell=(i == 0),
            phone_valid=validate_phone(phone.strip()),
            source_row_index=row_index,
        ))
    return result


def _process_source_row(
    row: Dict[str, str], mapping: ColumnMapping, row_index: int,
) -> Tuple[List[ExportRow], List[str]]:
    """处理单个源数据行，返回 ExportRow 列表和无效手机号描述列表。"""
    raw_phone = row.get(mapping.source_phone_col, "")
    phones = split_phones(raw_phone)
    name = row.get(mapping.source_name_col, "")
    export_rows = build_export_rows(name, phones, row_index)
    invalids = [
        f"第 {er.source_row_index} 行：{er.phone} 不是合法手机号"
        for er in export_rows if not er.phone_valid
    ]
    return export_rows, invalids


def _process_all_rows(
    data: SheetData, mapping: ColumnMapping,
) -> Tuple[List[ExportRow], List[str]]:
    """遍历所有数据行，逐行转换并收集无效信息。"""
    all_rows: List[ExportRow] = []
    invalid_summary: List[str] = []
    for row_index, row in enumerate(data.rows, start=1):
        rows, invalids = _process_source_row(row, mapping, row_index)
        all_rows.extend(rows)
        invalid_summary.extend(invalids)
    return all_rows, invalid_summary


def build_preview_data(data: SheetData, mapping: ColumnMapping) -> PreviewData:
    """将 SheetData 转换为 PreviewData（校验 + 转换 + 汇总）。"""
    validate_columns(data, mapping)
    if not data.rows:
        return PreviewData(rows=[], invalid_count=0, invalid_summary=[])

    try:
        all_rows, invalid_summary = _process_all_rows(data, mapping)
        return PreviewData(
            rows=all_rows,
            invalid_count=len(invalid_summary),
            invalid_summary=invalid_summary,
        )
    except (ColumnNotFoundError, DataProcessError):
        raise
    except Exception as e:
        raise DataProcessError(f"数据处理失败：{e}") from e


def _make_template_row(row: ExportRow, mapping: ColumnMapping, col_count: int) -> List[str]:
    """构建单行 25 列模板数据，将姓名和手机号填入对应位置。"""
    data_row = [""] * col_count
    if row.is_name_cell:
        data_row[mapping.target_name_index] = row.name
    data_row[mapping.target_phone_index] = row.phone
    return data_row


def _build_request_parts(
    rows: List[ExportRow], mapping: ColumnMapping,
) -> Tuple[List[List[str]], List[MergeRange], dict]:
    """从 ExportRow 列表构建 data_rows、merge_ranges 和 cell_styles。"""
    col_count = len(TARGET_HEADERS)
    data_rows: List[List[str]] = []
    merge_ranges: List[MergeRange] = []
    cell_styles: dict = {}
    for i, row in enumerate(rows):
        data_rows.append(_make_template_row(row, mapping, col_count))
        if row.is_name_cell and row.merge_span > 1:
            merge_ranges.append(MergeRange(
                row_start=i, row_end=i + row.merge_span - 1,
                col_index=mapping.target_name_index,
            ))
        if not row.phone_valid:
            cell_styles[(i, mapping.target_phone_index)] = CellStyle(background_color="#FF0000")
    return data_rows, merge_ranges, cell_styles


def build_write_request(
    preview: PreviewData, mapping: ColumnMapping, output_path: str,
) -> WriteRequest:
    """将 PreviewData 转换为 WriteRequest，准备写入文件。"""
    data_rows, merge_ranges, cell_styles = _build_request_parts(preview.rows, mapping)
    return WriteRequest(
        file_path=output_path,
        headers=list(TARGET_HEADERS),
        data_rows=data_rows,
        merge_ranges=merge_ranges,
        cell_styles=cell_styles,
    )
