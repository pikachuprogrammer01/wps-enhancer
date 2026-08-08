import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.file_io.base import SheetData
from core.settings import AppSettings
from core.template import BuiltinColumn, Template, TemplateColumn, match_columns
from features.contacts_import.processor import (
    build_preview_data, build_write_request, split_phones, validate_phone,
)

_BUILTINS = [
    BuiltinColumn(key="name", label="姓名", aliases=["姓名", "姓", "名称"]),
    BuiltinColumn(key="phone", label="手机", aliases=["手机", "手机号", "电话", "有效手机号"]),
    BuiltinColumn(key="company", label="公司名", aliases=["公司", "公司名称"]),
]


def _template():
    return Template(name="通讯录", columns=[
        TemplateColumn(key="name", name="姓名"),
        TemplateColumn(key="phone", name="手机"),
        TemplateColumn(key="company", name="公司名"),
    ])


def _sheet():
    return SheetData(
        sheet_name="s",
        headers=["姓名", "手机号", "公司"],
        rows=[
            {"姓名": "张三", "手机号": "13800000000;13900000000", "公司": "A公司"},
            {"姓名": "李四", "手机号": "bad", "公司": "B公司"},
            {"姓名": "王五", "手机号": "", "公司": ""},
        ],
    )


class PhoneUtilTest(unittest.TestCase):
    """手机号拆分与校验。"""

    def test_split_phones(self):
        self.assertEqual(split_phones("138;139", [";"]), ["138", "139"])
        self.assertEqual(split_phones(" 138 ; 139 ", [";"]), ["138", "139"])
        self.assertEqual(split_phones("138;;139", [";"]), ["138", "139"])
        self.assertEqual(split_phones("", [";"]), [])
        # 多种分隔符依次拆分（默认分隔符集合）
        seps = [",", "，", ";", "；", "、", " ", "\n", "|"]
        self.assertEqual(
            split_phones("138,139；140、141 | 142", seps),
            ["138", "139", "140", "141", "142"],
        )
        # 多个手机号在同一行（空格分隔）
        self.assertEqual(split_phones("138 139", [" "]), ["138", "139"])

    def test_validate_phone(self):
        self.assertTrue(validate_phone("13800000000"))
        self.assertTrue(validate_phone("+8613800000000"))
        self.assertTrue(validate_phone(""))
        self.assertFalse(validate_phone("12345"))
        self.assertFalse(validate_phone("23800000000"))
        self.assertFalse(validate_phone("1380000000a"))


class PreviewTest(unittest.TestCase):
    """数据转换：拆分、校验、无 phone 映射。"""

    def setUp(self):
        self.template = _template()
        self.matches = match_columns(
            ["姓名", "手机号", "公司"], self.template, _BUILTINS,
        )
        self.settings = AppSettings()

    def test_split_and_merge_flags(self):
        preview = build_preview_data(_sheet(), self.template, self.matches, self.settings)
        rows = preview.rows
        self.assertEqual(len(rows), 4)  # 张三2行 + 李四1行 + 王五1行
        self.assertEqual(rows[0].values[0], "张三")
        self.assertEqual(rows[0].values[1], "13800000000")
        self.assertTrue(rows[0].is_first_of_split)
        self.assertEqual(rows[0].merge_span, 2)
        self.assertFalse(rows[1].is_first_of_split)
        self.assertEqual(rows[1].values[1], "13900000000")

    def test_invalid_phone_counted(self):
        preview = build_preview_data(_sheet(), self.template, self.matches, self.settings)
        self.assertEqual(preview.invalid_count, 1)
        self.assertIn("第 2 行：bad 不是合法手机号", preview.invalid_summary)

    def test_validation_disabled(self):
        settings = AppSettings(phone_validate=False)
        preview = build_preview_data(_sheet(), self.template, self.matches, settings)
        self.assertEqual(preview.invalid_count, 0)
        self.assertTrue(all(r.phone_valid for r in preview.rows))

    def test_empty_phone_valid(self):
        preview = build_preview_data(_sheet(), self.template, self.matches, self.settings)
        last = preview.rows[-1]
        self.assertEqual(last.values[1], "")
        self.assertTrue(last.phone_valid)

    def test_no_phone_mapping_no_split(self):
        tmpl = Template(name="无手机", columns=[
            TemplateColumn(key="name", name="姓名"),
            TemplateColumn(key="company", name="公司名"),
        ])
        matches = match_columns(["姓名", "公司"], tmpl, _BUILTINS)
        preview = build_preview_data(_sheet(), tmpl, matches, self.settings)
        self.assertEqual(len(preview.rows), 3)  # 每源行 1 条，不拆分
        self.assertEqual(preview.rows[0].values, ["张三", "A公司"])

    def test_unmatched_column_empty(self):
        tmpl = Template(name="多列", columns=[
            TemplateColumn(key="name", name="姓名"),
            TemplateColumn(key="phone", name="手机"),
            TemplateColumn(key="website", name="网址"),
        ])
        matches = match_columns(["姓名", "手机号"], tmpl, _BUILTINS)
        preview = build_preview_data(_sheet(), tmpl, matches, self.settings)
        self.assertEqual(preview.rows[0].values[2], "")  # 网址未匹配

    def test_merge_name_grouping(self):
        """勾选合并：同名跨行合并（姓名仅首行保留，组标记正确）。"""
        tmpl = Template(name="同名", columns=[
            TemplateColumn(key="name", name="姓名"),
            TemplateColumn(key="phone", name="手机"),
        ])
        data = SheetData(
            sheet_name="s", headers=["姓名", "手机"],
            rows=[
                {"姓名": "张三", "手机": "13800000000"},
                {"姓名": "李四", "手机": "13900000000"},
                {"姓名": "张三", "手机": "13700000000"},
            ],
        )
        matches = match_columns(["姓名", "手机"], tmpl, _BUILTINS)
        settings = AppSettings(phone_merge=True, phone_validate=False)
        preview = build_preview_data(data, tmpl, matches, settings)
        rows = preview.rows
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0].values[0], "张三")
        self.assertTrue(rows[0].is_first_of_split)
        self.assertEqual(rows[0].merge_span, 2)
        self.assertEqual(rows[1].values[0], "")      # 张三组非首行姓名置空
        self.assertFalse(rows[1].is_first_of_split)
        self.assertEqual(rows[2].values[0], "李四")  # 组间顺序：首次出现优先
        # 导出时仅张三组生成姓名列合并范围
        request = build_write_request(preview, tmpl, matches, settings, "/tmp/x.xlsx")
        self.assertEqual(len(request.merge_ranges), 1)
        self.assertEqual(
            (request.merge_ranges[0].row_start, request.merge_ranges[0].row_end),
            (0, 1),
        )

    def test_no_merge_every_phone_one_row(self):
        """未勾选合并：每号一行，相同内容不合并。"""
        data = SheetData(
            sheet_name="s", headers=["姓名", "手机"],
            rows=[{"姓名": "张三", "手机": "13800000000,13900000000"}],
        )
        matches = match_columns(["姓名", "手机"], self.template, _BUILTINS)
        settings = AppSettings(phone_merge=False, phone_validate=False)
        preview = build_preview_data(data, self.template, matches, settings)
        rows = preview.rows
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].values[0], "张三")
        self.assertEqual(rows[0].values[1], "13800000000")
        self.assertEqual(rows[1].values[0], "张三")  # 内容重复不合并
        self.assertEqual(rows[1].values[1], "13900000000")
        request = build_write_request(preview, self.template, matches, settings, "/tmp/x.xlsx")
        self.assertEqual(request.merge_ranges, [])  # 不生成合并范围


class WriteRequestTest(unittest.TestCase):
    """WriteRequest 构建：headers/keys/合并/标红/导出参数。"""

    def setUp(self):
        self.template = _template()
        self.matches = match_columns(
            ["姓名", "手机号", "公司"], self.template, _BUILTINS,
        )

    def test_headers_and_field_keys(self):
        preview = build_preview_data(_sheet(), self.template, self.matches, AppSettings())
        req = build_write_request(
            preview, self.template, self.matches, AppSettings(), "/tmp/out.xlsx",
        )
        self.assertEqual(req.headers, ["姓名", "手机", "公司名"])
        self.assertEqual(req.field_keys, ["name", "phone", "company"])

    def test_merge_ranges_when_enabled(self):
        settings = AppSettings(phone_merge=True)
        preview = build_preview_data(_sheet(), self.template, self.matches, settings)
        req = build_write_request(preview, self.template, self.matches, settings, "/tmp/out.xlsx")
        self.assertEqual(len(req.merge_ranges), 1)
        self.assertEqual(req.merge_ranges[0].col_index, 0)  # name 列
        self.assertEqual(req.merge_ranges[0].row_end - req.merge_ranges[0].row_start + 1, 2)

    def test_no_merge_when_disabled(self):
        settings = AppSettings(phone_merge=False)
        preview = build_preview_data(_sheet(), self.template, self.matches, settings)
        req = build_write_request(preview, self.template, self.matches, settings, "/tmp/out.xlsx")
        self.assertEqual(req.merge_ranges, [])

    def test_red_style_for_invalid(self):
        settings = AppSettings()
        preview = build_preview_data(_sheet(), self.template, self.matches, settings)
        req = build_write_request(preview, self.template, self.matches, settings, "/tmp/out.xlsx")
        self.assertIn((2, 1), req.cell_styles)  # 第 3 行手机列（0 索引）
        self.assertEqual(req.cell_styles[(2, 1)].background_color, "#FF0000")

    def test_no_style_when_highlight_disabled(self):
        settings = AppSettings(phone_highlight=False)
        preview = build_preview_data(_sheet(), self.template, self.matches, settings)
        req = build_write_request(preview, self.template, self.matches, settings, "/tmp/out.xlsx")
        self.assertEqual(req.cell_styles, {})

    def test_export_params_from_settings(self):
        settings = AppSettings(csv_encoding="gbk", txt_encoding="utf-16",
                               txt_separator="、",
                               vcf_fields=["name", "phone"])
        preview = build_preview_data(_sheet(), self.template, self.matches, settings)
        req = build_write_request(preview, self.template, self.matches, settings, "/tmp/out.txt")
        self.assertEqual(req.encoding, "utf-16")  # txt 用 txt 编码
        self.assertEqual(req.separator, "、")
        self.assertEqual(req.vcf_fields, ["name", "phone"])
        # csv 用 csv 编码；其他格式固定 utf-8
        req_csv = build_write_request(preview, self.template, self.matches, settings, "/tmp/out.csv")
        self.assertEqual(req_csv.encoding, "gbk")
        req_xlsx = build_write_request(preview, self.template, self.matches, settings, "/tmp/out.xlsx")
        self.assertEqual(req_xlsx.encoding, "utf-8")

    def test_build_text_preview_csv_txt_vcf(self):
        """文本预览与导出文件内容一致（csv 逗号分隔、txt 用设置分隔符、vcf 完整 vCard）。"""
        from features.contacts_import.processor import build_text_preview

        settings = AppSettings(txt_separator="、", vcf_fields=["name", "phone"],
                               vcf_name_prefix="客户-", vcf_timestamp=False)
        preview = build_preview_data(_sheet(), self.template, self.matches, settings)
        # csv：表头 + 数据行，逗号分隔，引号转义
        csv_text = build_text_preview(preview, self.matches, settings, "csv")
        lines = csv_text.rstrip("\n").split("\n")
        self.assertEqual(lines[0], "姓名,手机,公司名")
        self.assertIn("张三,13800000000,A公司", lines)
        # txt：使用设置的分隔符
        txt_text = build_text_preview(preview, self.matches, settings, "txt")
        lines = txt_text.rstrip("\n").split("\n")
        self.assertEqual(lines[0], "姓名、手机、公司名")
        self.assertIn("张三、13800000000、A公司", lines)
        # vcf：完整 vCard 文本，姓名带前后缀，仅勾选字段
        vcf_text = build_text_preview(preview, self.matches, settings, "vcf")
        self.assertIn("BEGIN:VCARD", vcf_text)
        self.assertIn("FN:客户-张三", vcf_text)
        self.assertIn("TEL;TYPE=CELL:13800000000", vcf_text)
        self.assertNotIn("ORG:", vcf_text)  # company 未勾选不导出
        # 行数截断
        short = build_text_preview(preview, self.matches, settings, "csv", row_limit=1)
        self.assertEqual(len(short.rstrip("\n").split("\n")), 2)  # 表头 + 1 行

    def test_vcf_timestamp_switch_and_position(self):
        """vcf 时间戳：开关控制是否附加年月日，位置决定姓名前/后。"""
        from features.contacts_import.processor import (
            _effective_vcf_prefix, _effective_vcf_suffix,
        )

        # 默认：时间戳开启 + 姓名前 + 前缀 vcf_ → vcf_20260808
        settings = AppSettings(vcf_name_prefix="vcf_")
        prefix = _effective_vcf_prefix(settings)
        self.assertRegex(prefix, r"^vcf_\d{8}$")
        self.assertEqual(_effective_vcf_suffix(settings), "")
        # 关闭时间戳 → 纯前缀/后缀
        off = AppSettings(vcf_name_prefix="vcf_", vcf_timestamp=False)
        self.assertEqual(_effective_vcf_prefix(off), "vcf_")
        self.assertEqual(_effective_vcf_suffix(off), "")
        # 时间戳放姓名后 → 后缀附加日期
        suffix_ts = AppSettings(
            vcf_name_prefix="vcf_", vcf_name_suffix="-VIP",
            vcf_timestamp_position="suffix",
        )
        self.assertEqual(_effective_vcf_prefix(suffix_ts), "vcf_")
        self.assertRegex(_effective_vcf_suffix(suffix_ts), r"^-VIP\d{8}$")
        # 自定义前缀 + 时间戳姓名前
        custom = AppSettings(vcf_name_prefix="客户-")
        self.assertRegex(_effective_vcf_prefix(custom), r"^客户-\d{8}$")
        # 导出请求携带生效前缀
        settings_off = AppSettings(vcf_name_prefix="vcf_", vcf_timestamp=False)
        preview = build_preview_data(_sheet(), self.template, self.matches, settings_off)
        req = build_write_request(
            preview, self.template, self.matches, settings_off, "/tmp/out.vcf",
        )
        self.assertEqual(req.vcf_name_prefix, "vcf_")


if __name__ == "__main__":
    unittest.main()
