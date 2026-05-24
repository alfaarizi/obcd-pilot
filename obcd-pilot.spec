# -*- mode: python ; coding: utf-8 -*-
# No bootloader Splash(): PyInstaller's splash is unsupported on macOS (Tcl/Tk
# threading model). The Qt splash in __main__.py covers the cold-start gap;
# splash@2x.png is bundled under datas/ui/ for it to load at runtime.

a = Analysis(
    ['src/obcd_pilot/__main__.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        ('src/obcd_pilot/ui/styles/app.qss', 'ui/styles'),
        ('src/obcd_pilot/ui/splash@2x.png', 'ui'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='obcd-pilot',
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
    name='obcd-pilot',
)
app = BUNDLE(
    coll,
    name='OBCD Pilot.app',
    icon=None,
    bundle_identifier='com.obcd.pilot',
)
