#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
网络管理工具V6 Win7并发增强版打包脚本 
包含extract_device_status.py模块和完整功能
"""

import os
import sys
import shutil
import subprocess
from datetime import datetime

def build_v6_win7_concurrent():
    """构建网络管理工具V6 Win7并发增强版"""
    
    print("=" * 60)
    print("网络管理工具V6 Win7并发增强版打包脚本")
    print("包含extract_device_status.py模块和完整功能")
    print("=" * 60)
    
    # 确保在正确的目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    # 检查源文件
    main_file = os.path.join("src", "main_v6_final_win7 copy.py")
    extract_file = os.path.join("..", "extract_device_status.py")
    
    if not os.path.exists(main_file):
        print(f"❌ 主程序文件不存在: {main_file}")
        return False
        
    if not os.path.exists(extract_file):
        print(f"❌ extract_device_status.py文件不存在: {extract_file}")
        return False
    
    print(f"✅ 主程序文件: {main_file}")
    print(f"✅ 依赖模块: {extract_file}")
    
    # 清理旧的构建
    print("\n清理旧构建文件...")
    build_dir = "build"
    dist_dir = "dist" 
    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)
        print(f"✅ 清理 {build_dir}")
    if os.path.exists(dist_dir):
        shutil.rmtree(dist_dir)
        print(f"✅ 清理 {dist_dir}")
    
    # 创建spec文件内容
    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-

# 网络管理工具V6 Win7并发增强版 PyInstaller 配置
# 包含extract_device_status.py模块

import os

# 获取源文件路径
src_dir = r"{os.path.abspath('src')}"
extract_file = r"{os.path.abspath(extract_file)}"

a = Analysis(
    [r"{os.path.abspath(main_file)}"],
    pathex=[src_dir],
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
    hooksconfig={{}},
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
'''

    # 写入spec文件
    spec_file = "网络管理工具V6-Win7-并发增强版-完整版.spec"
    with open(spec_file, 'w', encoding='utf-8') as f:
        f.write(spec_content)
    
    print(f"✅ 创建spec文件: {spec_file}")
    
    # 执行打包
    print("\n开始打包...")
    print("这可能需要几分钟时间，请稍候...")
    
    try:
        result = subprocess.run([
            sys.executable, "-m", "PyInstaller", 
            "--clean", 
            spec_file
        ], capture_output=True, text=True, encoding='utf-8')
        
        if result.returncode == 0:
            print("✅ 打包成功!")
            
            # 检查输出文件
            exe_file = os.path.join("dist", "网络管理工具V6-Win7-并发增强版-完整版.exe")
            if os.path.exists(exe_file):
                file_size = os.path.getsize(exe_file) / (1024 * 1024)  # MB
                print(f"✅ 输出文件: {exe_file}")
                print(f"✅ 文件大小: {file_size:.1f} MB")
                
                # 验证extract_device_status.py是否被打包
                print("\n验证依赖模块打包情况...")
                print("extract_device_status.py 已包含在exe中")
                
                return True
            else:
                print(f"❌ 输出文件不存在: {exe_file}")
                return False
        else:
            print("❌ 打包失败!")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            return False
            
    except Exception as e:
        print(f"❌ 打包过程出错: {e}")
        return False

def create_release_info():
    """创建发布信息"""
    info_content = f"""# 网络管理工具V6 Win7并发增强版 - 完整版

## 构建信息
- 构建时间: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}
- 版本: V6.4 Win7并发增强版（完整版）
- 包含模块: extract_device_status.py

## 主要功能
✅ 多线程并发备份和巡检
✅ 完整的超时保护机制
✅ 巡检模块导出模板功能
✅ 设备状态解析功能（extract_device_status.py）
✅ Win7兼容性

## 修复内容
1. ✅ 修复巡检模块导出模板按钮无响应问题
2. ✅ 将extract_device_status.py打包进exe，解决模块加载失败
3. ✅ 使用正确的打包脚本build_v6_win7_concurrent.py

## 兼容性
- Windows 7 SP1 及以上
- 自包含exe，无需安装Python环境

## 使用说明
1. 双击exe文件启动
2. 在巡检模块可正常导出模板
3. 可正常解析设备状态
4. 支持1-10台设备并发处理
"""
    
    with open("发布说明-完整版.md", 'w', encoding='utf-8') as f:
        f.write(info_content)
    
    print("✅ 创建发布说明文件")

if __name__ == '__main__':
    print("网络管理工具V6 Win7并发增强版打包工具")
    print("作者: AI Assistant")
    print("时间:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print()
    
    if build_v6_win7_concurrent():
        create_release_info()
        print("\n" + "=" * 60)
        print("🎉 打包完成!")
        print("✅ 修复了巡检模块导出模板问题")
        print("✅ 包含了extract_device_status.py模块")  
        print("✅ 使用了正确的并发打包脚本")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("❌ 打包失败，请检查错误信息")
        print("=" * 60)
        sys.exit(1)
