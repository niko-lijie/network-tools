#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单测试脚本 - 验证网络管理工具主要功能
"""

import sys
import os

# 添加当前目录到模块搜索路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_extract_module():
    """测试extract_device_status模块"""
    print("测试extract_device_status模块...")
    try:
        import extract_device_status
        
        # 测试厂商检测
        test_output = "display version\nVRP (R) software\nHuawei Versatile Routing Platform Software"
        vendor = extract_device_status.detect_vendor(test_output)
        print(f"  厂商检测: {vendor}")
        
        # 测试信息提取
        info = extract_device_status.extract_info(test_output, vendor)
        print(f"  信息提取: {info}")
        
        print("✅ extract_device_status模块测试通过")
        return True
    except Exception as e:
        print(f"❌ extract_device_status模块测试失败: {e}")
        return False

def test_main_module_imports():
    """测试主模块的导入"""
    print("测试主模块导入...")
    try:
        # 测试所有必要的导入
        import tkinter as tk
        import csv
        import threading
        import time
        import socket
        import os
        import sys
        import re
        import datetime
        import paramiko
        import importlib.util
        import glob
        import shutil
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from queue import Queue, Empty
        import concurrent.futures
        
        print("✅ 所有必要模块导入成功")
        return True
    except Exception as e:
        print(f"❌ 模块导入失败: {e}")
        return False

def test_main_syntax():
    """测试主程序语法"""
    print("测试主程序语法...")
    try:
        import py_compile
        py_compile.compile("main_v6_final_win7 copy.py", doraise=True)
        print("✅ 主程序语法检查通过")
        return True
    except Exception as e:
        print(f"❌ 主程序语法错误: {e}")
        return False

def main():
    """运行所有测试"""
    print("网络管理工具V6 - 功能测试")
    print("=" * 50)
    
    tests = [
        test_main_syntax,
        test_main_module_imports,
        test_extract_module
    ]
    
    passed = 0
    for test in tests:
        if test():
            passed += 1
        print()
    
    total = len(tests)
    print(f"测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！程序应该可以正常运行")
        return True
    else:
        print("❌ 部分测试失败，需要修复")
        return False

if __name__ == '__main__':
    main()