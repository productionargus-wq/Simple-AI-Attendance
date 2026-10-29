# -*- mode: python ; coding: utf-8 -*-
import os
import sys

block_cipher = None

is_windows = sys.platform.startswith('win')
is_macos = sys.platform == 'darwin'

# Bundle required data files and assets
datas = [
    ('templates', 'templates'),
    ('static', 'static'),
    ('models', 'models'),
]

if os.path.exists('.env'):
    datas.append(('.env', '.'))

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

if is_windows:
    hidden_imports.extend([
        'webview.platforms.winforms',
        'webview.platforms.edgechromium',
        'clr',
        'pythonnet',
        'clr_loader',
    ])
elif is_macos:
    hidden_imports.extend([
        'webview.platforms.cocoa',
    ])

# Application Icon (use .ico on Windows only; macOS requires .icns or None)
if is_windows:
    icon_file = os.path.join('static', 'favicon.ico')
    if not os.path.exists(icon_file):
        icon_file = None
else:
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

# Single-file standalone executable
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
    upx=is_windows,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No terminal window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file,
)

# On macOS, generate standard .app application bundle
if is_macos:
    app = BUNDLE(
        exe,
        name='ArgusAttendance.app',
        icon=None,
        bundle_identifier='com.argus.attendance',
        info_plist={
            'NSCameraUsageDescription': 'Argus Attendance requires camera access for biometric face attendance.',
            'NSMicrophoneUsageDescription': 'Argus Attendance uses microphone access for voice assistance.',
            'CFBundleDisplayName': 'Argus Attendance',
            'CFBundleName': 'Argus Attendance',
            'CFBundleShortVersionString': '2.0.0',
            'CFBundleVersion': '2.0.0',
            'LSMinimumSystemVersion': '10.13.0',
        }
    )
