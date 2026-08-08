# -*- mode: python ; coding: utf-8 -*-
import sys

from PyInstaller.utils.hooks import collect_submodules

hiddenimports = []
hiddenimports += collect_submodules('features')
hiddenimports += collect_submodules('core')
hiddenimports += collect_submodules('ui')

# onedir 模式：免去每次启动解包（onefile 每次启动解压到临时目录，启动慢）
a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('features', 'features')],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # 排除运行用不到的模块（环境残留被 hook 保守收集），减小体积
    excludes=['tkinter', 'lib2to3', 'pydoc_data', 'test', 'unittest',
              'numpy', 'PIL', 'yaml', 'charset_normalizer'],
    noarchive=False,
    optimize=0,
)

# 排除 app 用不到的 Qt 库与可选图像插件（QtCore/QtGui/QtWidgets/QtDBus/QtSvg 保留——
# QtGui 硬依赖 QtDBus，imageformats 的 qsvg 插件依赖 QtSvg）
_BIN_EXCLUDE = ('QtPdf', 'QtNetwork',
                'libavif', 'libtiff', 'libwebp', 'libopenjp2', 'liblcms2')
a.binaries = [
    b for b in a.binaries
    if not any(p in b[0] for p in _BIN_EXCLUDE)
]
# 排除 Qt 自带翻译文件（界面中文硬编码，不用 Qt 翻译系统）
a.datas = [d for d in a.datas if '/translations/' not in d[0]]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='WPS增强工具',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='WPS增强工具',
)
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name='WPS增强工具.app',
        icon=None,
        bundle_identifier=None,
    )
# Windows：COLLECT 直接产出 <name>.exe + 依赖目录，无需 BUNDLE
