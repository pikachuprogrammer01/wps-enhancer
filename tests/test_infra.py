import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.exceptions import TemplateError
from core.logger import log_call
from core.template import BuiltinColumn, Template, TemplateColumn, TemplateManager, match_columns
import core.settings as settings_mod
from core.settings import AppSettings, get_app_settings, save_app_settings, reset_settings_cache


def _builtins():
    """构造测试用内置列（姓名/手机/公司名/网址）。"""
    return [
        BuiltinColumn(key="name", label="姓名", aliases=["姓", "名称", "姓名"]),
        BuiltinColumn(key="phone", label="手机", aliases=["手机号", "电话", "手机"]),
        BuiltinColumn(key="company", label="公司名", aliases=["公司", "公司名称"]),
        BuiltinColumn(key="website", label="网址", aliases=["主页", "网址", "官网"]),
    ]


class AopLogTest(unittest.TestCase):
    """log_call 装饰器：正常执行、异常重抛。"""

    def test_log_call_preserves_result(self):
        @log_call("test.aop", log_args=True, log_result=True)
        def add(a: int, b: int) -> int:
            return a + b

        self.assertEqual(add(1, 2), 3)

    def test_log_call_rethrows_exception(self):
        @log_call("test.aop")
        def boom() -> None:
            raise ValueError("boom")

        with self.assertRaises(ValueError):
            boom()


class TemplateManagerTest(unittest.TestCase):
    """模板 CRUD：创建/重名/非法字符/表头导入/重命名/删除。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="wps_tpl_"))
        self.mgr = TemplateManager(self.tmp, _builtins())

    def test_create_writes_file(self):
        t = self.mgr.create("企业通讯录", [TemplateColumn(key="name", name="姓名")])
        self.assertEqual(t.name, "企业通讯录")
        self.assertTrue((self.tmp / "企业通讯录.json").exists())

    def test_duplicate_name_gets_suffix(self):
        self.mgr.create("企业通讯录", [TemplateColumn(key="name", name="姓名")])
        t2 = self.mgr.create("企业通讯录", [TemplateColumn(key="name", name="姓名")])
        self.assertEqual(t2.name, "企业通讯录_2")

    def test_illegal_chars_replaced_in_filename(self):
        t = self.mgr.create("a/b:c", [TemplateColumn(key="name", name="姓名")])
        self.assertTrue((self.tmp / "a_b_c.json").exists())

    def test_empty_name_raises(self):
        with self.assertRaises(TemplateError):
            self.mgr.create("   ", [])

    def test_create_from_headers_detects_keys(self):
        t = self.mgr.create_from_headers("来自表头", ["姓名", "手机号", "自定义1"])
        keys = [c.key for c in t.columns]
        self.assertEqual(keys, ["name", "phone", "custom_1"])

    def test_list_templates_sorted(self):
        self.mgr.create("B模板", [TemplateColumn(key="name", name="姓名")])
        self.mgr.create("A模板", [TemplateColumn(key="name", name="姓名")])
        names = [t.name for t in self.mgr.list_templates()]
        self.assertEqual(names, ["A模板", "B模板"])

    def test_rename_moves_file(self):
        self.mgr.create("旧名", [TemplateColumn(key="name", name="姓名")])
        t = self.mgr.rename("旧名", "新名")
        self.assertEqual(t.name, "新名")
        self.assertFalse((self.tmp / "旧名.json").exists())
        self.assertTrue((self.tmp / "新名.json").exists())

    def test_rename_to_existing_gets_suffix(self):
        self.mgr.create("旧名", [TemplateColumn(key="name", name="姓名")])
        self.mgr.create("新名", [TemplateColumn(key="name", name="姓名")])
        t = self.mgr.rename("旧名", "新名")
        self.assertEqual(t.name, "新名_2")

    def test_rename_same_name_noop(self):
        self.mgr.create("模板", [TemplateColumn(key="name", name="姓名")])
        t = self.mgr.rename("模板", "模板")
        self.assertEqual(t.name, "模板")
        self.assertTrue((self.tmp / "模板.json").exists())

    def test_delete_and_missing_raises(self):
        self.mgr.create("模板", [TemplateColumn(key="name", name="姓名")])
        self.mgr.delete("模板")
        self.assertFalse((self.tmp / "模板.json").exists())
        with self.assertRaises(TemplateError):
            self.mgr.delete("不存在")

    def test_mappings_round_trip(self):
        """建议映射随模板保存并在加载后保留。"""
        self.mgr.create(
            "带映射", [TemplateColumn(key="name", name="姓名")],
            mappings={"name": "法定代表人"},
        )
        loaded = self.mgr.list_templates()[0]
        self.assertEqual(loaded.mappings, {"name": "法定代表人"})
        # 无 mappings 的旧结构文件兼容（缺省空 dict）
        (self.tmp / "旧模板.json").write_text(
            '{"name": "旧模板", "version": 1, '
            '"columns": [{"key": "name", "name": "姓名"}]}',
            encoding="utf-8",
        )
        legacy = next(
            t for t in self.mgr.list_templates() if t.name == "旧模板"
        )
        self.assertEqual(legacy.mappings, {})


class MatcherTest(unittest.TestCase):
    """列匹配引擎：exact/alias/manual/none 与源列去重。"""

    def setUp(self):
        self.tmpl = Template(name="t", columns=[
            TemplateColumn(key="name", name="姓名"),
            TemplateColumn(key="phone", name="手机"),
            TemplateColumn(key="company", name="公司名"),
            TemplateColumn(key="website", name="网址"),
        ])

    def _status_map(self, matches):
        return {m.template_col.key: (m.source_col, m.status) for m in matches}

    def test_exact_and_alias_mixed(self):
        matches = match_columns(["姓名", "手机号", "公司", "主页"], self.tmpl, _builtins())
        got = self._status_map(matches)
        self.assertEqual(got["name"], ("姓名", "exact"))
        self.assertEqual(got["phone"], ("手机号", "alias"))
        self.assertEqual(got["company"], ("公司", "alias"))
        self.assertEqual(got["website"], ("主页", "alias"))

    def test_unmatched_is_none(self):
        matches = match_columns(["A列", "B列"], self.tmpl, _builtins())
        self.assertTrue(all(m.status == "none" and m.source_col is None for m in matches))

    def test_manual_map_overrides(self):
        matches = match_columns(
            ["姓名", "手机号"], self.tmpl, _builtins(), manual_map={"phone": ""},
        )
        self.assertEqual(self._status_map(matches)["phone"], (None, "manual"))

    def test_source_column_used_once(self):
        tmpl2 = Template(name="t2", columns=[
            TemplateColumn(key="name", name="姓名"),
            TemplateColumn(key="phone", name="姓名"),
        ])
        matches = match_columns(["姓名"], tmpl2, _builtins())
        self.assertEqual(matches[0].source_col, "姓名")
        self.assertIsNone(matches[1].source_col)


class SettingsTest(unittest.TestCase):
    """全局设置：默认值/保存重读/内置列持久化/损坏回退。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="wps_cfg_"))
        patcher = mock.patch.object(
            settings_mod, "get_settings_path", lambda: self.tmp / "settings.json",
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        reset_settings_cache()

    def tearDown(self):
        reset_settings_cache()

    def test_defaults(self):
        s = get_app_settings()
        self.assertTrue(s.phone_validate)
        self.assertTrue(s.phone_highlight)
        self.assertFalse(s.phone_merge)
        self.assertEqual(s.csv_encoding, "utf-8-bom")
        self.assertEqual(s.txt_separator, " ")
        self.assertEqual(s.vcf_fields, ["name", "phone", "company", "website"])
        self.assertTrue(s.declaration_detect)
        self.assertIn("企查查", s.declaration_keywords)
        self.assertIn("天眼查", s.declaration_keywords)
        self.assertFalse(s.log_debug)
        self.assertEqual(len(s.builtin_columns), 4)

    def test_save_and_reload(self):
        s2 = AppSettings(phone_validate=False, csv_encoding="gbk", log_debug=True)
        save_app_settings(s2)
        reset_settings_cache()
        s3 = get_app_settings()
        self.assertFalse(s3.phone_validate)
        self.assertEqual(s3.csv_encoding, "gbk")
        self.assertTrue(s3.log_debug)

    def test_builtin_columns_persisted(self):
        s = get_app_settings()
        s.builtin_columns.append(BuiltinColumn(key="custom_1", label="生日", aliases=["生日"]))
        save_app_settings(s)
        reset_settings_cache()
        s2 = get_app_settings()
        self.assertTrue(any(c.key == "custom_1" and c.label == "生日" for c in s2.builtin_columns))

    def test_old_qcc_field_migrates(self):
        """旧版 qcc_declaration_skip 字段迁移到 declaration_detect。"""
        (self.tmp / "settings.json").write_text(
            '{"app_settings": {"qcc_declaration_skip": false}}', encoding="utf-8",
        )
        reset_settings_cache()
        self.assertFalse(get_app_settings().declaration_detect)

    def test_corrupted_file_falls_back_to_defaults(self):
        (self.tmp / "settings.json").write_text("{bad json", encoding="utf-8")
        reset_settings_cache()
        self.assertTrue(get_app_settings().phone_validate)


if __name__ == "__main__":
    unittest.main()
