# -*- mode: python ; coding: utf-8 -*-
import os
import sys

block_cipher = None

# Bundle required data files and assets
datas = [
    ('templates', 'templates'),
    ('static', 'static'),
    ('models', 'models'),
    ('.env', '.'),
]

# Hidden imports required for dynamic dependencies
hidden_imports = [
    'waitress',
    'waitress.adjustments',
    'waitress.buffers',
    'waitress.channel',
    'waitress.compat',
    'waitress.parser',
    'waitress.proxy_headers',
    'waitress.receiver',
    'waitress.rfc7230',
    'waitress.server',
    'waitress.task',
    'waitress.trigger',
    'waitress.utilities',
    'waitress.wasyncore',
    'webview',
    'webview.platforms.winforms',
    'webview.platforms.edgechromium',
    'clr',
    'pythonnet',
    'clr_loader',
    'google.generativeai',
    'docx',
    'docx.shared',
    'docx.enum.text',
    'docx.enum.table',
    'reportlab',
    'reportlab.graphics.barcode',
    'reportlab.lib.colors',
    'reportlab.lib.pagesizes',
    'reportlab.platypus',
    'openpyxl',
    'schedule',
    'PIL',
    'PIL.Image',
    'PIL.ImageOps',
    'cv2',
    'dns',
    'dns.resolver',
    'pymongo',
    'pymongo.srv_resolver',
    'requests',
]

# Application Icon
icon_file = os.path.join('static', 'favicon.ico')
if not os.path.exists(icon_file):
    icon_file = None

a = Analysis(
    ['desktop_app.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy', 'IPython', 'notebook'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Single-file standalone executable (no _internal directory needed)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ArgusAttendance',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No black terminal window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file,
)
