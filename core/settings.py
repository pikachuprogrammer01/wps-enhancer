import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional

from core.app_paths import get_settings_path
from core.logger import get_logger, log_call
from core.template.config import BuiltinColumn, default_builtin_columns

# csv 编码可选值（unicode 即 UTF-16 LE 带 BOM 的别名）
ENCODING_CHOICES: List[str] = ["utf-8-bom", "utf-8", "gbk", "utf-16", "unicode"]
# txt 分隔符可选值（支持自定义字符串）
SEPARATOR_CHOICES: List[str] = [" ", "\t", ",", "、", "|"]
# 手机号分隔符默认值（同一姓名多个手机号时的常用分隔形式）
DEFAULT_PHONE_SEPARATORS: List[str] = [",", "，", ";", "；", "、", " ", "\n", "|"]
# 声明行检测默认关键词（覆盖常见表格导出平台，用户可增删）
DEFAULT_DECLARATION_KEYWORDS: List[str] = [
    "企查查", "天眼查", "爱企查", "启信宝", "水滴信用",
    "导出数据", "导出声明", "数据来源", "声明",
]


@dataclass
class AppSettings:
    """全局设置（settings.json 的权威结构）。"""
    builtin_columns: List[BuiltinColumn] = field(default_factory=default_builtin_columns)
    phone_validate: bool = True
    phone_highlight: bool = True
    phone_merge: bool = False
    phone_separators: List[str] = field(
        default_factory=lambda: list(DEFAULT_PHONE_SEPARATORS),
    )  # 同一姓名多手机号的分隔符（拆分用）
    csv_encoding: str = "utf-8-bom"
    txt_encoding: str = "utf-8-bom"
    txt_separator: str = " "
    vcf_fields: List[str] = field(default_factory=lambda: ["name", "phone", "company", "website"])
    vcf_name_prefix: str = "vcf_"   # vcf 导出姓名前缀（纯文本，如「客户-」）
    vcf_name_suffix: str = ""
    vcf_timestamp: bool = True      # 是否在姓名上附加年月日时间戳
    vcf_timestamp_position: str = "prefix"  # 时间戳位置：prefix=姓名前 / suffix=姓名后
    declaration_detect: bool = True                              # 声明行检测（自动跳过首行声明）
    declaration_keywords: List[str] = field(
        default_factory=lambda: list(DEFAULT_DECLARATION_KEYWORDS),
    )
    log_debug: bool = False
    auto_update_enabled: bool = True  # 启动时自动检查 GitHub Releases 更新
    use_system_proxy: bool = True     # 检查/下载更新时自动走系统代理（默认开启）


_cache: Optional[AppSettings] = None


def _settings_dict(settings: AppSettings) -> dict:
    """将 AppSettings 序列化为 settings.json 结构（内置列与设置拆分为两个键）。"""
    return {
        "builtin_columns": [asdict(col) for col in settings.builtin_columns],
        "app_settings": {
            "phone_validate": settings.phone_validate,
            "phone_highlight": settings.phone_highlight,
            "phone_merge": settings.phone_merge,
            "phone_separators": list(settings.phone_separators),
            "csv_encoding": settings.csv_encoding,
            "txt_encoding": settings.txt_encoding,
            "txt_separator": settings.txt_separator,
            "vcf_fields": list(settings.vcf_fields),
            "vcf_name_prefix": settings.vcf_name_prefix,
            "vcf_name_suffix": settings.vcf_name_suffix,
            "vcf_timestamp": settings.vcf_timestamp,
            "vcf_timestamp_position": settings.vcf_timestamp_position,
            "declaration_detect": settings.declaration_detect,
            "declaration_keywords": list(settings.declaration_keywords),
            "log_debug": settings.log_debug,
            "auto_update_enabled": settings.auto_update_enabled,
        },
    }


def _parse_builtin_columns(raw: object) -> List[BuiltinColumn]:
    """从 JSON 原始数据构建内置列列表（非列表或为空时回退默认）。"""
    columns: List[BuiltinColumn] = []
    if not isinstance(raw, list):
        return default_builtin_columns()
    for item in raw:
        if not isinstance(item, dict):
            continue
        aliases_raw = item.get("aliases", [])
        aliases = [str(a) for a in aliases_raw if isinstance(a, str)] if isinstance(aliases_raw, list) else []
        columns.append(BuiltinColumn(
            key=str(item.get("key", "")),
            label=str(item.get("label", "")),
            aliases=aliases,
        ))
    return columns if columns else default_builtin_columns()


def _load_from_file(path: Path) -> AppSettings:
    """从文件读取设置（文件缺失或损坏时回退默认值并记录警告）。"""
    defaults = AppSettings()
    if not path.exists():
        return defaults
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        get_logger("core.settings").warning(f"设置文件读取失败，使用默认值：{e}")
        return defaults
    app = raw.get("app_settings", {}) if isinstance(raw, dict) else {}
    if not isinstance(app, dict):
        app = {}
    return AppSettings(
        builtin_columns=_parse_builtin_columns(
            raw.get("builtin_columns") if isinstance(raw, dict) else None,
        ),
        phone_validate=bool(app.get("phone_validate", defaults.phone_validate)),
        phone_highlight=bool(app.get("phone_highlight", defaults.phone_highlight)),
        phone_merge=bool(app.get("phone_merge", defaults.phone_merge)),
        phone_separators=[
            str(s) for s in app.get("phone_separators", list(defaults.phone_separators))
        ],
        csv_encoding=str(app.get("csv_encoding", defaults.csv_encoding)),
        txt_encoding=str(app.get("txt_encoding", defaults.txt_encoding)),
        txt_separator=str(app.get("txt_separator", defaults.txt_separator)),
        vcf_fields=[str(f) for f in app.get("vcf_fields", list(defaults.vcf_fields))],
        vcf_name_prefix=str(app.get("vcf_name_prefix", defaults.vcf_name_prefix)),
        vcf_name_suffix=str(app.get("vcf_name_suffix", defaults.vcf_name_suffix)),
        vcf_timestamp=bool(app.get("vcf_timestamp", defaults.vcf_timestamp)),
        vcf_timestamp_position=str(app.get(
            "vcf_timestamp_position", defaults.vcf_timestamp_position,
        )),
        declaration_detect=bool(app.get(
            "declaration_detect",
            app.get("qcc_declaration_skip", defaults.declaration_detect),  # 旧字段迁移
        )),
        declaration_keywords=[
            str(k) for k in app.get("declaration_keywords", list(defaults.declaration_keywords))
        ],
        log_debug=bool(app.get("log_debug", defaults.log_debug)),
        auto_update_enabled=bool(app.get(
            "auto_update_enabled", defaults.auto_update_enabled,
        )),
    )


def get_app_settings() -> AppSettings:
    """返回全局设置（首次读取文件，之后返回内存缓存）。"""
    global _cache
    if _cache is None:
        _cache = _load_from_file(get_settings_path())
    return _cache


@log_call("core.settings", log_args=False)
def save_app_settings(settings: AppSettings) -> None:
    """保存全局设置到文件并更新内存缓存（原子写入，失败抛 FileWriteError）。"""
    global _cache
    path = get_settings_path()
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(
            json.dumps(_settings_dict(settings), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp_path.replace(path)
    except OSError as e:
        raise FileWriteError(f"无法写入设置文件 '{path}'：{e}") from e
    _cache = settings


def reset_settings_cache() -> None:
    """清空设置缓存（测试用）。"""
    global _cache
    _cache = None
