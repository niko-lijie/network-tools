# -*- mode: python ; coding: utf-8 -*-

# 网络管理工具V6 Win7并发增强版 PyInstaller 配置
# 包含extract_device_status.py模块

import os

# 获取源文件路径
main_file = r"/home/runner/work/network-tools/network-tools/main_v6_final_win7 copy.py"
extract_file = r"/home/runner/work/network-tools/network-tools/extract_device_status.py"

a = Analysis(
    [main_file],
    pathex=[r"/home/runner/work/network-tools/network-tools"],
    binaries=[],
    datas=[
        # 重要：将extract_device_status.py打包进exe
        (extract_file, '.'),
    ],
    hiddenimports=[
        'tkinter', 
        'tkinter.filedialog', 
        'tkinter.messagebox',
        'tkinter.ttk',
        'paramiko', 
        'threading',
        'concurrent.futures',
        'datetime',
        'csv',
        'os',
        'sys',
        'time',
        're',
        'socket',
        'importlib.util'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='网络管理工具V6-Win7-并发增强版-完整版',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=None,
    uac_admin=False,
    uac_uiaccess=False,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
)
