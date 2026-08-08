# -*- mode: python ; coding: utf-8 -*-
import sys

from PyInstaller.utils.hooks import collect_submodules

hiddenimports = []
hiddenimports += collect_submodules('features')
hiddenimports += collect_submodules('core')
hiddenimports += collect_submodules('ui')

# onedir 模式：免去每次启动解包（onefile 每次启动解压到临时目录，启动慢）
# 排除运行用不到的模块，减小体积
excludes = ['tkinter', 'lib2to3', 'pydoc_data', 'test', 'unittest']

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('features', 'features')],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
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
