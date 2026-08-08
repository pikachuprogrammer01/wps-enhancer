import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.file_io.base import get_reader, get_writer
from core.settings import AppSettings
from core.template import BuiltinColumn, TemplateManager, match_columns
from features.contacts_import.processor import build_preview_data, build_write_request

try:
    import openpyxl  # noqa: F401
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False


@unittest.skipUnless(HAS_OPENPYXL, "openpyxl 未安装")
class EndToEndTest(unittest.TestCase):
    """端到端：企查查声明行剔除 → 模板 → 匹配 → 预览 → 五格式导出 → 读回。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="wps_e2e_"))
        self.src = self.tmp / "源表.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "客户"
        ws.append(["企查查导出数据"])
        ws.append(["姓名", "有效手机号", "公司", "官网"])
        ws.append(["张三", "13800000000;13900000000", "A公司", "http://a.com"])
        ws.append(["李四", "bad", "B公司", ""])
        wb.save(self.src)
        self.builtins = [
            BuiltinColumn(key="name", label="姓名", aliases=["姓名", "姓"]),
            BuiltinColumn(key="phone", label="手机", aliases=["手机号", "有效手机号", "手机"]),
            BuiltinColumn(key="company", label="公司名", aliases=["公司", "公司名称"]),
            BuiltinColumn(key="website", label="网址", aliases=["官网", "网址"]),
        ]

    def test_full_pipeline_five_formats(self):
        # 1. 读取（声明行剔除）
        reader = get_reader(str(self.src))
        data = reader.read_sheet(str(self.src), "客户", skip_declaration=True)
        self.assertTrue(data.declaration_skipped)
        self.assertEqual(data.headers, ["姓名", "有效手机号", "公司", "官网"])

        # 2. 从表头创建模板 + 自动匹配
        mgr = TemplateManager(self.tmp / "templates", self.builtins)
        template = mgr.create_from_headers("企业通讯录", data.headers)
        matches = match_columns(data.headers, template, self.builtins)
        self.assertEqual(
            {m.template_col.key: m.status for m in matches},
            {"name": "exact", "phone": "exact", "company": "exact", "website": "exact"},
        )

        # 3. 预览（合并开、vcf 不含 website）
        settings = AppSettings(phone_merge=True, vcf_fields=["name", "phone", "company"])
        preview = build_preview_data(data, template, matches, settings)
        self.assertEqual(len(preview.rows), 3)  # 张三2行 + 李四1行
        self.assertEqual(preview.invalid_count, 1)

        # 4. 五格式导出
        for fmt in ["xlsx", "xls", "csv", "vcf", "txt"]:
            out = self.tmp / f"out.{fmt}"
            req = build_write_request(preview, template, matches, settings, str(out))
            get_writer(str(out)).write_export(req)
            self.assertTrue(out.exists(), f"{fmt} 导出失败")

        # 5. xlsx 读回
        back = get_reader(str(self.tmp / "out.xlsx")).read_sheet(
            str(self.tmp / "out.xlsx"), "Sheet",
        )
        self.assertEqual(back.headers, ["姓名", "有效手机号", "公司", "官网"])
        self.assertEqual(len(back.rows), 3)

        # 6. xls 读回
        back_xls = get_reader(str(self.tmp / "out.xls")).read_sheet(
            str(self.tmp / "out.xls"), "Sheet1",
        )
        self.assertEqual(len(back_xls.rows), 3)

        # 7. csv（UTF-8 BOM）+ 声明行剔除在导出不适用
        csv_text = (self.tmp / "out.csv").read_bytes().decode("utf-8-sig")
        self.assertIn("张三", csv_text)
        self.assertIn("有效手机号", csv_text.splitlines()[0])

        # 8. txt 表头行 + 空格分隔（默认 txt 编码 utf-8-bom）
        txt_text = (self.tmp / "out.txt").read_text(encoding="utf-8-sig")
        self.assertEqual(txt_text.splitlines()[0], "姓名 有效手机号 公司 官网")
        self.assertIn("张三 13800000000 A公司 http://a.com", txt_text)

        # 9. vcf 字段过滤（无 URL）+ 拆分行
        vcf_text = (self.tmp / "out.vcf").read_text(encoding="utf-8")
        self.assertIn("TEL;TYPE=CELL:13800000000", vcf_text)
        self.assertIn("TEL;TYPE=CELL:13900000000", vcf_text)
        self.assertNotIn("URL:", vcf_text)
        self.assertEqual(vcf_text.count("BEGIN:VCARD"), 3)

    def test_merge_enabled_writes_merged_cells(self):
        """合并开启时 xlsx 输出含合并单元格。"""
        reader = get_reader(str(self.src))
        data = reader.read_sheet(str(self.src), "客户", skip_declaration=True)
        mgr = TemplateManager(self.tmp / "templates", self.builtins)
        template = mgr.create_from_headers("企业通讯录", data.headers)
        matches = match_columns(data.headers, template, self.builtins)
        settings = AppSettings(phone_merge=True)
        preview = build_preview_data(data, template, matches, settings)
        out = self.tmp / "merged.xlsx"
        req = build_write_request(preview, template, matches, settings, str(out))
        get_writer(str(out)).write_export(req)

        wb = openpyxl.load_workbook(out)
        ws = wb.active
        self.assertEqual(len(ws.merged_cells.ranges), 1)
        wb.close()


if __name__ == "__main__":
    unittest.main()
