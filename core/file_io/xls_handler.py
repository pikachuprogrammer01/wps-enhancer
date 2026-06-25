import xlrd
import xlwt
from typing import List

from core.file_io.base import BaseReader, BaseWriter, SheetData, WriteRequest
from core.exceptions import FileReadError, FileWriteError


class XlsReader(BaseReader):
    """基于 xlrd 的 xls 文件读取器。"""

    def get_sheet_names(self, file_path: str) -> List[str]:
        """读取文件中所有 Sheet 名称。"""
        try:
            wb = xlrd.open_workbook(file_path)
            return wb.sheet_names()
        except Exception as e:
            raise FileReadError(f"无法读取文件 '{file_path}'：{type(e).__name__}: {e}") from e

    def _non_empty_count(self, sheet, row_idx: int) -> int:
        """统计 xlrd Sheet 中某行非空单元格的数量。"""
        count = 0
        for col_idx in range(sheet.ncols):
            if sheet.cell_type(row_idx, col_idx) != 0 and str(sheet.cell_value(row_idx, col_idx)).strip():
                count += 1
        return count

    def _find_header_row(self, sheet) -> int:
        """在前 5 行中找非空单元格最多的行作为表头行。"""
        scan_end = min(sheet.nrows, 5)
        best = max(range(scan_end), key=lambda i: self._non_empty_count(sheet, i))
        return best

    def read_sheet(self, file_path: str, sheet_name: str) -> SheetData:
        """读取指定 Sheet 的表头和数据行。"""
        try:
            wb = xlrd.open_workbook(file_path)
            sheet = wb.sheet_by_name(sheet_name)
            if sheet.nrows == 0:
                raise FileReadError(
                    f"无法读取文件 '{file_path}'：Sheet '{sheet_name}' 为空"
                )
            header_row = self._find_header_row(sheet)
            data_start = header_row + 1
            headers = [str(v) for v in sheet.row_values(header_row)]
            rows = []
            for row_idx in range(data_start, sheet.nrows):
                row_dict = {}
                for col_idx, header in enumerate(headers):
                    cell_type = sheet.cell_type(row_idx, col_idx)
                    cell_value = sheet.cell_value(row_idx, col_idx)
                    if cell_type == 2:  # XL_CELL_NUMBER
                        int_val = int(cell_value)
                        str_value = str(int_val) if cell_value == int_val else str(cell_value)
                    elif cell_type == 0:  # XL_CELL_EMPTY
                        str_value = ""
                    else:
                        str_value = str(cell_value)
                    row_dict[header] = str_value
                rows.append(row_dict)
            return SheetData(sheet_name=sheet_name, headers=headers, rows=rows)
        except FileReadError:
            raise
        except Exception as e:
            raise FileReadError(f"无法读取文件 '{file_path}'：{type(e).__name__}: {e}") from e


class XlsWriter(BaseWriter):
    """基于 xlwt 的 xls 文件写入器。"""

    @staticmethod
    def _make_style(background_color: str):
        """为指定背景色创建 xlwt XFStyle。"""
        xf_style = xlwt.XFStyle()
        xf_style.pattern.pattern = xlwt.Pattern.SOLID_PATTERN
        xf_style.pattern.pattern_fore_colour = 0x0A
        return xf_style

    @staticmethod
    def _cell_style_key(row_idx: int, col_idx: int, styles: dict):
        """获取单元格样式，无样式时返回 None。"""
        style = styles.get((row_idx, col_idx))
        if style is None or style.background_color is None:
            return None
        return style

    def write_export(self, request: WriteRequest) -> None:
        """写入导出数据，含合并单元格和背景色标记。"""
        try:
            wb = xlwt.Workbook(encoding="utf-8")
            ws = wb.add_sheet("Sheet1")
            self._write_headers(ws, request.headers)
            self._write_data(ws, request)
            self._write_merges(ws, request)
            wb.save(request.file_path)
        except Exception as e:
            raise FileWriteError(f"无法写入文件 '{request.file_path}'：{e}") from e

    def _write_headers(self, ws, headers: List[str]) -> None:
        """写入加粗表头行。"""
        xf_bold = xlwt.XFStyle()
        xf_bold.font.bold = True
        for col_idx, header in enumerate(headers):
            ws.write(0, col_idx, header, xf_bold)

    def _write_data(self, ws, request: WriteRequest) -> None:
        """写入数据行，跳过合并区域内的所有格（交由 _write_merges 处理）。"""
        merge_cells = set()
        for m in request.merge_ranges:
            for r in range(m.row_start, m.row_end + 1):
                merge_cells.add((r, m.col_index))
        for row_idx, row in enumerate(request.data_rows):
            for col_idx, value in enumerate(row):
                if (row_idx, col_idx) in merge_cells:
                    continue
                cell_style = self._cell_style_key(row_idx, col_idx, request.cell_styles)
                if cell_style is not None:
                    xf = self._make_style(cell_style.background_color)
                    ws.write(row_idx + 1, col_idx, value, xf)
                else:
                    ws.write(row_idx + 1, col_idx, value)

    def _write_merges(self, ws, request: WriteRequest) -> None:
        """写入合并单元格，含样式。"""
        for merge in request.merge_ranges:
            r1 = merge.row_start + 1
            r2 = merge.row_end + 1
            c1 = merge.col_index
            c2 = merge.col_index
            label = request.data_rows[merge.row_start][merge.col_index]
            cell_style = self._cell_style_key(merge.row_start, merge.col_index, request.cell_styles)
            if cell_style is not None:
                xf = self._make_style(cell_style.background_color)
                ws.write_merge(r1, r2, c1, c2, label, xf)
            else:
                ws.write_merge(r1, r2, c1, c2, label)
