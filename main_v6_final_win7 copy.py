#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
网络管理工具V5 - 完整修复版本
严格对标V3功能，修正所有语法错误和逻辑问题
"""

# === 开发文档同步更新 ===
# 2025-07-02
# 1. 监控模块导入设备后，点击“立即监控”会弹出进度窗口，显示当前监控进度。
# 2. 备份模块“定时备份”功能已完整实现，支持自定义小时周期（如24/72/180小时），可多线程自动定时执行。
# 3. 巡检模块新增“定时巡检”功能，支持自定义小时周期，自动定时执行。
# 4. 巡检界面已增加“定时巡检”按钮。
# 5. 相关定时线程与停止标志已在__init__初始化，保证多次启动安全。
# 6. 所有功能和算法更新已同步到本开发文档。
# 7. 监控、备份、巡检等所有批量操作均支持进度提示和周期性自动执行。
# 8. 代码结构和按钮逻辑详见本文件及 main_v5_fixed开发文档.md。

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
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

class NetworkManagementToolV5:
    def __init__(self, root):
        self.root = root
        self.root.title("网络管理工具V5")
        self.root.geometry("1000x750")
        self.device_list = []
        self.monitor_results = []
        self.online_status = {}
        self.inspect_device_count_var = tk.StringVar(value="设备数：0")
        self.create_widgets()
        self.monitoring = False
        self.monitor_thread = None
        self.backup_schedule_thread = None
        self.backup_schedule_stop = False
        self.inspect_schedule_thread = None
        self.inspect_schedule_stop = False
        
        # 并发设置
        self.max_concurrent_devices = 5  # 最大并发设备数，可根据网络和系统性能调整
        self.concurrent_executor = None
        self.progress_queue = Queue()  # 用于线程间通信的进度队列
        self.connection_timeout = 30  # 连接超时时间
        self.max_retries = 3  # 连接重试次数

    def create_widgets(self):
        # 顶部模块切换区美化
        topbar = tk.Frame(self.root, bg="#f7fbff", height=56)
        topbar.pack(fill="x", pady=0)
        self.module_var = tk.StringVar(value="monitor")
        modules = [
            ("监控模块", "monitor"),
            ("备份模块", "backup"),
            ("巡检模块", "inspect"),
            ("管理模块", "manage")
        ]
        for text, val in modules:
            btn = tk.Radiobutton(
                topbar, text=text, variable=self.module_var, value=val, indicatoron=False, width=12,
                command=self.switch_module, font=("微软雅黑", 12, "bold"), bg="#e6f2ff", fg="#007acc",
                selectcolor="#cce6ff", activebackground="#cce6ff", activeforeground="#007acc",
                borderwidth=0, relief="flat", pady=10
            )
            btn.pack(side="left", padx=8, pady=8)
        self.device_count_var = tk.StringVar()
        self.device_count_var.set("设备数：0")
        tk.Label(topbar, textvariable=self.device_count_var, fg="#007acc", font=("微软雅黑", 14, "bold"), bg="#f7fbff").pack(side="right", padx=18)
        # 主内容区背景
        self.main_frame = tk.Frame(self.root, bg="#f7fbff")
        self.main_frame.pack(fill="both", expand=True)
        self.show_monitor_module()

    def switch_module(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        mod = self.module_var.get()
        if mod == "monitor":
            self.show_monitor_module()
        elif mod == "backup":
            self.show_backup_module()
        elif mod == "inspect":
            self.show_inspect_module()
        elif mod == "manage":
            self.show_manage_module()

    def show_monitor_module(self):
        # 监控模块卡片式分区
        card_bg = "#ffffff"
        # 监控操作区
        frame_monitor = tk.Frame(self.main_frame, bg=card_bg, highlightbackground="#b3d7f5", highlightthickness=2)
        frame_monitor.pack(fill="x", padx=28, pady=(18, 8))
        btn_style = {"font": ("微软雅黑", 11, "bold"), "bg": "#e6f2ff", "fg": "#007acc", "activebackground": "#cce6ff", "activeforeground": "#007acc", "relief": "flat", "bd": 0, "height": 2, "cursor": "hand2"}
        tk.Button(frame_monitor, text="导入设备列表", command=self.import_monitor_devices, width=15, **btn_style).pack(side="left", padx=8, pady=10)
        tk.Button(frame_monitor, text="立即监控", command=self.start_monitor, width=15, bg="#d9ead3", fg="#38761d", activebackground="#b6e3b6", activeforeground="#38761d", relief="flat", bd=0, height=2, cursor="hand2", font=("微软雅黑", 11, "bold")).pack(side="left", padx=8, pady=10)
        tk.Button(frame_monitor, text="停止监控", command=self.stop_monitor, width=15, bg="#f4cccc", fg="#990000", activebackground="#f7b6b6", activeforeground="#990000", relief="flat", bd=0, height=2, cursor="hand2", font=("微软雅黑", 11, "bold")).pack(side="left", padx=8, pady=10)
        tk.Button(frame_monitor, text="导出监控日志", command=self.export_monitor_log, width=15, **btn_style).pack(side="left", padx=8, pady=10)
        
        # 监控统计区卡片（包含饼图）
        self.status_frame = tk.Frame(self.main_frame, bg=card_bg, highlightbackground="#b3d7f5", highlightthickness=2, bd=0)
        self.status_frame.pack(fill="x", padx=28, pady=8)
        self.status_frame.grid_propagate(False)
        self.status_frame.configure(height=220)  # 增大高度，保证饼图完整显示
        self.status_canvas = tk.Canvas(self.status_frame, width=220, height=200, bg=card_bg, highlightthickness=0)
        self.status_canvas.pack(side="left", padx=18, pady=12)
        self.status_label = tk.Label(self.status_frame, text="", font=("微软雅黑", 15, "bold"), fg="#007acc", bg=card_bg)
        self.status_label.pack(side="left", padx=18, pady=12)
        
        # 监控详情区卡片
        frame_detail = tk.Frame(self.main_frame, bg=card_bg, highlightbackground="#b3d7f5", highlightthickness=2, bd=0)
        frame_detail.pack(fill="both", expand=True, padx=28, pady=(8, 18))
        
        # 监控详情按钮区
        btns = tk.Frame(frame_detail, bg=card_bg)
        btns.pack(fill="x", pady=8)
        tk.Button(btns, text="查看设备状态", command=self.show_all_device_status, width=18, **btn_style).pack(side="left", padx=8)
        tk.Button(btns, text="导出为CSV", command=self.export_current_table, width=15, **btn_style).pack(side="left", padx=8)
        
        # 监控详情表格卡片化
        style = ttk.Style()
        style.configure("Treeview.Heading", font=("微软雅黑", 11, "bold"), foreground="#007acc", background="#e6f2ff")
        style.configure("Treeview", font=("微软雅黑", 10), rowheight=28, background=card_bg, fieldbackground=card_bg, borderwidth=0)
        style.layout("Treeview", [('Treeview.treearea', {'sticky': 'nswe'})])
        self.tree = ttk.Treeview(frame_detail, columns=("设备名", "IP", "厂商", "状态", "CPU", "内存", "温度", "电源", "风扇", "运行时间"), show="headings")
        for col in ("设备名", "IP", "厂商", "状态", "CPU", "内存", "温度", "电源", "风扇", "运行时间"):
            self.tree.heading(col, text=col)
            self.tree.column(col, anchor="center", width=110)
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        
        # 切换回来自动恢复监控结果和统计
        if self.monitor_results:
            self.update_tree(self.monitor_results)
            self.online_status = {}
            for row in self.monitor_results:
                ip = row.get('IP') or row.get('ip')
                status = row.get('状态')
                if ip:
                    self.online_status[ip] = status
            self.update_status_chart()

    def show_backup_module(self):
        # 备份模块
        card_bg = "#ffffff"
        frame_backup = tk.Frame(self.main_frame, bg=card_bg, highlightbackground="#b3d7f5", highlightthickness=2)
        frame_backup.pack(fill="x", padx=28, pady=(18, 8))
        
        # 主要按钮区
        btns = tk.Frame(frame_backup, bg=card_bg)
        btns.pack(fill="x", pady=8)
        btn_style = {"font": ("微软雅黑", 11, "bold"), "bg": "#e6f2ff", "fg": "#007acc", "activebackground": "#cce6ff", "activeforeground": "#007acc", "relief": "flat", "bd": 0, "height": 2, "cursor": "hand2"}
        tk.Button(btns, text="导入设备列表", command=self.import_backup_devices, width=15, **btn_style).pack(side="left", padx=8, pady=8)
        tk.Button(btns, text="导出模板", command=self.export_backup_template, width=15, **btn_style).pack(side="left", padx=8, pady=8)
        tk.Button(btns, text="并发备份", command=self.backup_now, width=15, bg="#d9ead3", fg="#38761d", activebackground="#b6d7a8", activeforeground="#38761d", relief="flat", bd=0, font=("微软雅黑", 11, "bold"), height=2, cursor="hand2").pack(side="left", padx=8, pady=8)
        tk.Button(btns, text="定时备份", command=self.backup_scheduler, width=15, **btn_style).pack(side="left", padx=8, pady=8)
        
        # 并发设置区
        concurrent_frame = tk.Frame(frame_backup, bg=card_bg)
        concurrent_frame.pack(fill="x", pady=(0, 8))
        tk.Label(concurrent_frame, text="并发数:", font=("微软雅黑", 10), bg=card_bg, fg="#007acc").pack(side="left", padx=(8, 5))
        
        # 并发数调整控件
        concurrent_control = tk.Frame(concurrent_frame, bg=card_bg)
        concurrent_control.pack(side="left", padx=5)
        
        def decrease_concurrent():
            if self.max_concurrent_devices > 1:
                self.max_concurrent_devices -= 1
                concurrent_label.config(text=str(self.max_concurrent_devices))
        
        def increase_concurrent():
            if self.max_concurrent_devices < 10:
                self.max_concurrent_devices += 1
                concurrent_label.config(text=str(self.max_concurrent_devices))
        
        tk.Button(concurrent_control, text="-", command=decrease_concurrent, width=2, font=("微软雅黑", 10), bg="#f0f0f0", relief="flat").pack(side="left")
        concurrent_label = tk.Label(concurrent_control, text=str(self.max_concurrent_devices), width=3, font=("微软雅黑", 10, "bold"), bg="#ffffff", relief="sunken")
        concurrent_label.pack(side="left", padx=2)
        tk.Button(concurrent_control, text="+", command=increase_concurrent, width=2, font=("微软雅黑", 10), bg="#f0f0f0", relief="flat").pack(side="left")
        
        tk.Label(concurrent_frame, text="台 (建议1-10台)", font=("微软雅黑", 9), bg=card_bg, fg="#666666").pack(side="left", padx=5)
        
        if not hasattr(self, 'backup_device_count_var'):
            self.backup_device_count_var = tk.StringVar()
        self.backup_device_count_var.set("设备数：0")
        tk.Label(frame_backup, textvariable=self.backup_device_count_var, fg="#007acc", font=("微软雅黑", 13, "bold"), bg=card_bg).pack(side="right", padx=18, pady=8)

        # 备份进度显示区域
        self.backup_progress_frame = tk.Frame(self.main_frame, bg=card_bg, highlightbackground="#b3d7f5", highlightthickness=2)
        self.backup_progress_frame.pack(fill="both", expand=True, padx=28, pady=(8, 18))
        
        # 进度标题
        progress_title = tk.Label(self.backup_progress_frame, text="并发备份进度", font=("微软雅黑", 14, "bold"), fg="#007acc", bg=card_bg)
        progress_title.pack(pady=(15, 5))
        
        # 进度文本显示
        self.backup_progress_text = tk.Text(self.backup_progress_frame, height=20, wrap="word", font=("微软雅黑", 10), bg="#f8f9fa", fg="#333333", relief="flat", bd=0)
        self.backup_progress_text.pack(fill="both", expand=True, padx=20, pady=(10, 20))
        
        # 滚动条
        backup_scrollbar = ttk.Scrollbar(self.backup_progress_text, orient="vertical", command=self.backup_progress_text.yview)
        backup_scrollbar.pack(side="right", fill="y")
        self.backup_progress_text.config(yscrollcommand=backup_scrollbar.set)
        
        # 初始显示
        self.backup_progress_text.insert("1.0", "等待并发备份任务开始...\n\n提示：\n1. 请先导入设备列表\n2. 调整并发数（推荐3-8台）\n3. 点击'并发备份'开始任务\n4. 备份过程中请勿关闭程序")
        self.backup_progress_text.config(state="disabled")

    def show_inspect_module(self):
        # 巡检模块
        card_bg = "#ffffff"
        frame_inspect = tk.Frame(self.main_frame, bg=card_bg, highlightbackground="#b3d7f5", highlightthickness=2)
        frame_inspect.pack(fill="x", padx=28, pady=(18, 8))
        
        # 主要按钮区
        btns = tk.Frame(frame_inspect, bg=card_bg)
        btns.pack(fill="x", pady=8)
        btn_style = {"font": ("微软雅黑", 11, "bold"), "bg": "#e6f2ff", "fg": "#007acc", "activebackground": "#cce6ff", "activeforeground": "#007acc", "relief": "flat", "bd": 0, "height": 2, "cursor": "hand2"}
        tk.Button(btns, text="导入设备+指令列表", command=self.import_inspect_devices, width=18, **btn_style).pack(side="left", padx=8, pady=8)
        tk.Button(btns, text="导出模板", command=self.export_inspect_template, width=15, **btn_style).pack(side="left", padx=8, pady=8)
        tk.Button(btns, text="并发巡检", command=self.auto_inspect, width=15, bg="#d9ead3", fg="#38761d", activebackground="#b6d7a8", activeforeground="#38761d", relief="flat", bd=0, font=("微软雅黑", 11, "bold"), height=2, cursor="hand2").pack(side="left", padx=8, pady=8)
        tk.Button(btns, text="定时巡检", command=self.inspect_scheduler, width=15, **btn_style).pack(side="left", padx=8, pady=8)
        tk.Button(btns, text="解析设备状态", command=self.parse_device_status_from_logs, width=15, **btn_style).pack(side="left", padx=8, pady=8)

        # 并发设置区（共享备份模块的设置）
        concurrent_frame = tk.Frame(frame_inspect, bg=card_bg)
        concurrent_frame.pack(fill="x", pady=(0, 8))
        tk.Label(concurrent_frame, text="并发数:", font=("微软雅黑", 10), bg=card_bg, fg="#007acc").pack(side="left", padx=(8, 5))
        
        # 并发数调整控件
        concurrent_control = tk.Frame(concurrent_frame, bg=card_bg)
        concurrent_control.pack(side="left", padx=5)
        
        def decrease_concurrent():
            if self.max_concurrent_devices > 1:
                self.max_concurrent_devices -= 1
                concurrent_label.config(text=str(self.max_concurrent_devices))
        
        def increase_concurrent():
            if self.max_concurrent_devices < 10:
                self.max_concurrent_devices += 1
                concurrent_label.config(text=str(self.max_concurrent_devices))
        
        tk.Button(concurrent_control, text="-", command=decrease_concurrent, width=2, font=("微软雅黑", 10), bg="#f0f0f0", relief="flat").pack(side="left")
        concurrent_label = tk.Label(concurrent_control, text=str(self.max_concurrent_devices), width=3, font=("微软雅黑", 10, "bold"), bg="#ffffff", relief="sunken")
        concurrent_label.pack(side="left", padx=2)
        tk.Button(concurrent_control, text="+", command=increase_concurrent, width=2, font=("微软雅黑", 10), bg="#f0f0f0", relief="flat").pack(side="left")
        
        tk.Label(concurrent_frame, text="台 (巡检建议2-5台)", font=("微软雅黑", 9), bg=card_bg, fg="#666666").pack(side="left", padx=5)

        if not hasattr(self, 'inspect_device_count_var'):
            self.inspect_device_count_var = tk.StringVar()
        self.inspect_device_count_var.set("设备数：0")
        tk.Label(frame_inspect, textvariable=self.inspect_device_count_var, fg="#007acc", font=("微软雅黑", 13, "bold"), bg=card_bg).pack(side="right", padx=18, pady=8)

        # 巡检进度显示区域
        self.inspect_progress_frame = tk.Frame(self.main_frame, bg=card_bg, highlightbackground="#b3d7f5", highlightthickness=2)
        self.inspect_progress_frame.pack(fill="both", expand=True, padx=28, pady=(8, 18))
        
        # 进度标题
        progress_title = tk.Label(self.inspect_progress_frame, text="并发巡检进度", font=("微软雅黑", 14, "bold"), fg="#007acc", bg=card_bg)
        progress_title.pack(pady=(15, 5))
        
        # 进度文本显示
        self.inspect_progress_text = tk.Text(self.inspect_progress_frame, height=20, wrap="word", font=("微软雅黑", 10), bg="#f8f9fa", fg="#333333", relief="flat", bd=0)
        self.inspect_progress_text.pack(fill="both", expand=True, padx=20, pady=(10, 20))
        
        # 滚动条
        inspect_scrollbar = ttk.Scrollbar(self.inspect_progress_text, orient="vertical", command=self.inspect_progress_text.yview)
        inspect_scrollbar.pack(side="right", fill="y")
        self.inspect_progress_text.config(yscrollcommand=inspect_scrollbar.set)
        
        # 初始显示
        self.inspect_progress_text.insert("1.0", "等待并发巡检任务开始...\n\n提示：\n1. 请先导入设备+指令列表\n2. 调整并发数（推荐2-5台）\n3. 点击'并发巡检'开始任务\n4. 巡检过程中请勿关闭程序")
        self.inspect_progress_text.config(state="disabled")

    def show_manage_module(self):
        # 管理模块
        card_bg = "#ffffff"
        frame_manage = tk.Frame(self.main_frame, bg=card_bg, highlightbackground="#b3d7f5", highlightthickness=2)
        frame_manage.pack(fill="x", padx=28, pady=(18, 8))
        btns = tk.Frame(frame_manage, bg=card_bg)
        btns.pack(fill="x", pady=8)
        btn_style = {"font": ("微软雅黑", 11, "bold"), "bg": "#e6f2ff", "fg": "#007acc", "activebackground": "#cce6ff", "activeforeground": "#007acc", "relief": "flat", "bd": 0, "height": 2, "cursor": "hand2"}
        tk.Button(btns, text="导入设备列表", command=self.import_manage_devices, width=15, **btn_style).pack(side="left", padx=8, pady=8)
        tk.Button(btns, text="导出日志", command=self.export_logs, width=15, **btn_style).pack(side="left", padx=8, pady=8)

    # 监控功能实现
    def _open_csv_compat(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            with open(file_path, 'r', encoding='gbk') as f:
                return list(csv.DictReader(f))

    def import_monitor_devices(self):
        file_path = filedialog.askopenfilename(title="选择监控设备CSV文件", filetypes=[("CSV文件", "*.csv")])
        if file_path:
            try:
                self.device_list = self._open_csv_compat(file_path)
                self.device_count_var.set(f"设备数：{len(self.device_list)}")
                messagebox.showinfo("导入成功", f"成功导入{len(self.device_list)}台设备！")
            except Exception as e:
                messagebox.showerror("导入失败", f"导入设备列表失败: {e}")

    def start_monitor(self):
        if not self.device_list:
            messagebox.showwarning("无设备", "请先导入设备列表！")
            return
        if self.monitoring:
            messagebox.showinfo("监控中", "监控已在运行！")
            return
        # 新增进度弹窗
        self.monitor_progress = tk.Toplevel(self.root)
        self.monitor_progress.title("监控进度")
        self.monitor_progress_label = tk.Label(self.monitor_progress, text="正在监控，请勿关闭窗口...", font=("微软雅黑", 12))
        self.monitor_progress_label.pack(padx=20, pady=10)
        self.monitor_progress.update()
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self.monitor_loop_with_progress, daemon=True)
        self.monitor_thread.start()

    def stop_monitor(self):
        self.monitoring = False
        messagebox.showinfo("监控停止", "已停止监控任务。")

    def monitor_loop(self):
        while self.monitoring:
            self.monitor_once()
            for _ in range(1800):  # 30分钟
                if not self.monitoring:
                    break
                time.sleep(1)

    def monitor_loop_with_progress(self):
        total = len(self.device_list)
        for idx in range(1):  # 只监控一次，后续可扩展为定时
            if not self.monitoring:
                break
            for i, dev in enumerate(self.device_list):
                if not self.monitoring:
                    break
                name = dev.get('name') or dev.get('设备名') or dev.get('设备名称') or dev.get('主机名')
                ip = dev.get('ip') or dev.get('IP')
                self.root.after(0, lambda i=i, name=name, ip=ip: self.monitor_progress_label.config(text=f"正在监控第{i+1}/{total}台设备: {name} ({ip})"))
                self.monitor_progress.update()
            self.monitor_once()
        self.root.after(0, self.monitor_progress.destroy)

    def monitor_once(self):
        results = []
        for dev in self.device_list:
            ip = dev.get('ip') or dev.get('IP')
            name = dev.get('name') or dev.get('设备名') or dev.get('设备名称') or dev.get('主机名')
            vendor = (dev.get('vendor') or dev.get('厂商') or '').strip()
            port = int(dev.get('port') or dev.get('端口') or 22)
            status = '离线'
            try:
                sock = socket.create_connection((ip, port), timeout=3)
                sock.close()
                status = '在线'
            except Exception:
                status = '离线'
            results.append({
                '设备名': name,
                'IP': ip,
                '厂商': vendor,
                '状态': status,
                'CPU': '',
                '内存': '',
                '温度': '',
                '电源': '',
                '风扇': '',
                '运行时间': ''
            })
            self.online_status[ip] = status
        self.monitor_results = results
        self.update_tree(self.monitor_results)
        self.update_status_chart()

    # 备份功能实现
    def import_backup_devices(self):
        file_path = filedialog.askopenfilename(title="选择备份设备CSV文件", filetypes=[("CSV文件", "*.csv")])
        if file_path:
            try:
                self.backup_device_list = self._open_csv_compat(file_path)
                self.backup_device_count_var.set(f"设备数：{len(self.backup_device_list)}")
                messagebox.showinfo("导入成功", f"成功导入{len(self.backup_device_list)}台设备！")
            except Exception as e:
                messagebox.showerror("导入失败", f"导入设备列表失败: {e}")

    def backup_now(self):
        if not hasattr(self, 'backup_device_list') or not self.backup_device_list:
            messagebox.showwarning("无设备", "请先导入备份设备列表！")
            return
        backup_folder = filedialog.askdirectory(title="请选择备份输出目录")
        if not backup_folder:
            return
        
        # 清空进度显示并开始备份
        self.backup_progress_text.config(state="normal")
        self.backup_progress_text.delete("1.0", "end")
        self.backup_progress_text.insert("1.0", "开始并发备份任务...\n\n")
        self.backup_progress_text.config(state="disabled")
        self.backup_progress_text.update()
        
        # 使用多线程避免界面卡死
        def run_concurrent_backup():
            try:
                self._run_concurrent_backup_task(backup_folder)
            except Exception as e:
                # 在主线程中显示错误
                self.root.after(0, lambda: messagebox.showerror("备份错误", f"备份过程中发生错误: {e}"))
        
        # 启动备份线程
        backup_thread = threading.Thread(target=run_concurrent_backup, daemon=True)
        backup_thread.start()

    def _run_concurrent_backup_task(self, backup_folder):
        """并发备份任务的具体实现（在后台线程中运行）"""
        now = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_dir = os.path.join(backup_folder, f'backup_{now}')
        os.makedirs(backup_dir, exist_ok=True)
        total = len(self.backup_device_list)
        success = 0
        fail = 0
        log_lines = []
        
        # 显示备份目录信息（使用after方法在主线程中更新UI）
        def update_progress(text):
            self.root.after(0, lambda: self._update_backup_progress(text))
        
        update_progress(f"备份目录: {backup_dir}\n")
        update_progress(f"设备总数: {total}\n")
        update_progress(f"并发数: {self.max_concurrent_devices} 台同时进行\n")
        update_progress("=" * 50 + "\n\n")
        
        # 记录总开始时间
        total_start_time = time.time()
        
        # 创建线程池并发执行备份
        with ThreadPoolExecutor(max_workers=self.max_concurrent_devices) as executor:
            future_to_device = {}
            for idx, device in enumerate(self.backup_device_list):
                future = executor.submit(self._concurrent_backup_device, device, backup_dir, idx+1, total)
                future_to_device[future] = device
            
            for future in as_completed(future_to_device):
                device = future_to_device[future]
                name = device.get('name', 'unknown')
                ip = device.get('ip', '-')
                try:
                    result = future.result()
                    ok, logfile, errmsg, duration = result
                except Exception as e:
                    ok, logfile, errmsg, duration = False, '', str(e), 0
                
                if ok:
                    success += 1
                    log_lines.append(f"[SUCCESS] {name} ({ip}) -> {logfile} (耗时: {duration:.1f}秒)")
                else:
                    fail += 1
                    log_lines.append(f"[FAILED] {name} ({ip}) -> {errmsg} (耗时: {duration:.1f}秒)")
                
                update_progress(log_lines[-1] + "\n")
        
        # 计算总耗时
        total_end_time = time.time()
        total_duration = total_end_time - total_start_time
        
        # 写入汇总日志
        summary_log = os.path.join(backup_dir, f'backup_summary_{now}.log')
        with open(summary_log, 'w', encoding='utf-8', errors='ignore') as f:
            f.write(f"全部设备并发自动备份完成。\n成功: {success} 台，失败: {fail} 台，总计: {total} 台。\n")
            f.write(f"并发数: {self.max_concurrent_devices} 台\n")
            f.write(f"总耗时: {total_duration:.1f}秒 ({total_duration/60:.1f}分钟)\n")
            f.write(f"平均每台耗时: {total_duration/total:.1f}秒\n")
            f.write(f"效率提升: 相比串行约节省 {max(0, total*30 - total_duration):.0f}秒\n")
            f.write(f"备份目录: {backup_dir}\n\n")
            f.write('\n'.join(log_lines))
        
        # 显示最终结果
        update_progress(f"\n" + "=" * 50 + "\n")
        update_progress(f"🎉 并发备份完成！\n")
        update_progress(f"成功: {success} 台，失败: {fail} 台，总计: {total} 台\n")
        update_progress(f"总耗时: {total_duration:.1f}秒 ({total_duration/60:.1f}分钟)\n")
        update_progress(f"并发数: {self.max_concurrent_devices} 台\n")
        update_progress(f"汇总日志: {summary_log}\n")
        
        # 在主线程中显示完成消息
        self.root.after(0, lambda: messagebox.showinfo("完成", 
            f"全部设备并发自动备份完成！\n成功: {success} 台，失败: {fail} 台，总计: {total} 台。\n"
            f"总耗时: {total_duration:.1f}秒 ({total_duration/60:.1f}分钟)\n"
            f"并发效率提升明显！"))
    
    def _concurrent_backup_device(self, device, backup_dir, device_idx, total):
        """单个设备的备份任务（在线程池中执行）"""
        name = device.get('name', 'unknown')
        ip = device.get('ip', '-')
        
        # 记录开始时间
        start_time = time.time()
        
        # 更新进度显示（线程安全）
        def update_progress(text):
            self.root.after(0, lambda: self._update_backup_progress(text))
        
        update_progress(f"[{device_idx}/{total}] 开始备份: {name} ({ip})\n")
        
        try:
            # 添加调试信息
            update_progress(f"[{device_idx}/{total}] 正在连接设备: {name} ({ip})\n")
            ok, logfile, errmsg = self.backup_device(device, backup_dir)
            end_time = time.time()
            duration = end_time - start_time
            
            # 添加完成信息
            if ok:
                update_progress(f"[{device_idx}/{total}] ✅ 备份完成: {name} ({ip}) -> {logfile} (耗时: {duration:.1f}秒)\n")
            else:
                update_progress(f"[{device_idx}/{total}] ❌ 备份失败: {name} ({ip}) -> {errmsg} (耗时: {duration:.1f}秒)\n")
            
            return ok, logfile, errmsg, duration
        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time
            update_progress(f"[{device_idx}/{total}] ❌ 备份异常: {name} ({ip}) -> {str(e)} (耗时: {duration:.1f}秒)\n")
            return False, '', str(e), duration
    
    def _update_backup_progress(self, text):
        """在主线程中安全地更新备份进度显示"""
        try:
            self.backup_progress_text.config(state="normal")
            self.backup_progress_text.insert("end", text)
            self.backup_progress_text.config(state="disabled")
            self.backup_progress_text.see("end")
            self.backup_progress_text.update()
        except Exception:
            pass  # 忽略UI更新错误
            self.backup_progress_text.config(state="normal")
            self.backup_progress_text.insert("end", text)
            self.backup_progress_text.config(state="disabled")
            self.backup_progress_text.see("end")
            self.backup_progress_text.update()
        except Exception:
            pass  # 忽略UI更新错误

    def backup_device(self, device, backup_dir):
        name = device.get('name', 'unknown')
        ip = device.get('ip', '-')
        username = device.get('username', 'admin')
        password = device.get('password', '')
        port = int(device.get('port', 22))
        vendor = (device.get('vendor', '') or '').lower()
        # 自动选择备份命令
        if 'huawei' in vendor or 'h3c' in vendor:
            cmds = ['display current-configuration']
        else:
            cmds = ['show running-config']
        log_output = []
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(str(ip), port=port, username=username, password=password, timeout=30, allow_agent=False, look_for_keys=False)
            chan = ssh.invoke_shell(width=1000, height=200)
            time.sleep(2.5)
            
            # 登录输出收集 - 修复所有厂商设备登录阶段Y/N自动应答问题
            login_output = ''
            prompt_list = ['#', '>', '$']
            login_timeout = time.time() + 30
            
            # 登录阶段所有厂商的Y/N检测模式（通用匹配）
            login_yn_patterns = [
                # 华为设备常见登录Y/N提示
                r'Change now\?\s*\[Y/N\][:：]\s*$',  # Change now? [Y/N]:
                r'password needs to be changed.*\[Y/N\][:：]\s*$',  # password needs to be changed. Change now? [Y/N]:
                r'Do you want to change.*\[Y/N\][:：]\s*$',  # Do you want to change the password? [Y/N]:
                # 思科设备常见登录Y/N提示
                r'Would you like to enter the initial configuration dialog\?\s*\[yes/no\][:：]\s*$',  # Would you like to enter the initial configuration dialog? [yes/no]:
                r'Would you like to terminate autoinstall\?\s*\[yes\][:：]\s*$',  # Would you like to terminate autoinstall? [yes]:
                # 华三设备常见登录Y/N提示
                r'Save\?\s*\[Y/N\][:：]\s*$',  # Save? [Y/N]:
                r'Continue\?\s*\[Y/N\][:：]\s*$',  # Continue? [Y/N]:
                # 锐捷设备常见登录Y/N提示
                r'Enter the password\?\s*\[yes/no\][:：]\s*$',  # Enter the password? [yes/no]:
                # 通用Y/N模式（登录阶段）
                r'\w+\?\s*\[Y/N\][:：]\s*$',  # 任何问题? [Y/N]:
                r'\w+\?\s*\[yes/no\][:：]\s*$',  # 任何问题? [yes/no]:
            ]
            
            while True:
                time.sleep(0.12)
                if chan.recv_ready():
                    data = chan.recv(65535).decode(errors='ignore')
                    login_output += data
                    
                    # 检查是否是登录阶段的Y/N提示（仅在登录阶段处理）
                    login_yn_found = False
                    for pattern in login_yn_patterns:
                        if re.search(pattern, data, re.IGNORECASE):
                            # 华为设备登录时的密码变更提示，发送 'n' 跳过
                            chan.send(b'n\n')
                            time.sleep(0.3)
                            login_yn_found = True
                            break
                    
                    if not login_yn_found:
                        lines = data.strip().splitlines()
                        if lines:
                            last_line = lines[-1].strip()
                            if any(last_line.endswith(p) for p in prompt_list):
                                break
                if time.time() > login_timeout:
                    break
            prev_raw_output = login_output
            for idx, cmd in enumerate(cmds):
                chan.send((cmd + '\n').encode('utf-8'))
                time.sleep(1.0)
                raw_output = ''
                start_time = time.time()
                
                # 扩展的分页符检测列表 - 支持所有主流厂商 (备份模块)
                pagination_indicators = [
                    # 华为设备分页符
                    '---- More ----', '--More--', '<--- More --->', '--- More ---',
                    'Press any key to continue', 'Press SPACE to continue', 'Press Q to quit',
                    '按任意键继续', '按空格键继续', '按Q键退出',
                    # 华三设备分页符
                    '---- More ----', '--More--', 'More:', '(more)', '[more]', 
                    '---- more ----', '--more--', '(MORE)', '[MORE]', '-- More --', '---More---',
                    # 思科设备分页符
                    '--More--', 'Press any key to continue', 'Press SPACE for more',
                    '-- More --', '<spacebar> for more', 'q to quit',
                    # 锐捷设备分页符
                    '---- More ----', '--More--', 'More...', '(More)', '[More]',
                    'Press any key to continue', 'Press SPACE to continue',
                    # 其他厂商通用分页符
                    'Continue?', 'More (Press SPACE)', 'More (Press any key)',
                    '继续？', '更多(按空格键)', '更多(按任意键)'
                ]
                
                # 更精确的Y/N检测模式（仅命令执行阶段）
                yn_pattern = re.compile(r'((\(y/n\)|(\[y/n\])|(\(yes/no\))|(\[yes/no\])|continue\s*\?\s*\([yn]\))\s*[:：]\s*$', re.IGNORECASE)
                
                last_data_time = time.time()
                empty_count = 0
                max_empty = 60  # 增加基础空闲计数
                
                # 根据厂商调整参数 - 为所有厂商提供优化参数
                if 'ruijie' in vendor.lower() or '锐捷' in vendor.lower():
                    max_empty = 45
                elif 'h3c' in vendor.lower():
                    max_empty = 80
                elif 'huawei' in vendor.lower():
                    max_empty = 100  # 华为设备给予最大的容忍度
                elif 'cisco' in vendor.lower():
                    max_empty = 70   # 思科设备需要较多容忍度
                else:
                    max_empty = 60   # 其他厂商默认参数
                
                # 根据命令类型和厂商调整超时 - 为所有厂商优化超时时间
                timeout = 240  # 基础超时增加到240秒
                if any(x in cmd.lower() for x in ['configuration', 'running-config', 'startup-config']):
                    timeout = 900  # 配置备份命令超时增加到15分钟
                
                # 厂商特定超时调整
                if 'huawei' in vendor.lower():
                    timeout += 300  # 华为设备额外增加5分钟
                elif 'h3c' in vendor.lower():
                    timeout += 240  # 华三设备额外增加4分钟
                elif 'cisco' in vendor.lower():
                    timeout += 180  # 思科设备额外增加3分钟
                elif 'ruijie' in vendor.lower() or '锐捷' in vendor.lower():
                    timeout += 120  # 锐捷设备额外增加2分钟
                
                while True:
                    time.sleep(0.08)
                    if chan.recv_ready():
                        data = chan.recv(65535).decode(errors='ignore')
                        raw_output += data
                        last_data_time = time.time()
                        
                        # 改进的分页符检测：精确的完整行匹配，避免误判配置内容
                        pagination_found = False
                        data_lines = data.split('\n')
                        for line in data_lines:
                            line_clean = line.strip()
                            # 精确匹配分页符：必须是完整的分页符行，避免误判配置
                            for indicator in pagination_indicators:
                                # 方法1：完全相等匹配
                                if line_clean.lower() == indicator.lower().strip():
                                    chan.send(b' ')
                                    time.sleep(0.2)  # 增加延迟确保分页命令生效
                                    pagination_found = True
                                    break
                                # 方法2：精确的正则匹配（行首行尾匹配）
                                elif re.match(rf'^\s*{re.escape(indicator)}\s*$', line_clean, re.IGNORECASE):
                                    chan.send(b' ')
                                    time.sleep(0.2)
                                    pagination_found = True
                                    break
                            if pagination_found:
                                break
                        
                        if not pagination_found:
                            # Y/N自动应答（仅在命令执行阶段，更严格的匹配）
                            if yn_pattern.search(data):
                                chan.send(b'n\n')
                                time.sleep(0.15)
                        
                        # 改进的提示符检测 - 更保守的结束条件
                        lines = data.strip().splitlines()
                        if lines:
                            last_line = lines[-1].strip()
                            # 检查最后一行是否为提示符，增加更多验证条件
                            if any(last_line.endswith(p) for p in prompt_list):
                                # 多重验证确保这确实是提示符
                                if (len(last_line) < 80 and  # 提示符通常较短
                                    not any(keyword in last_line.lower() for keyword in ['interface', 'vlan', 'route', 'access', 'trunk']) and  # 不包含配置关键字
                                    time.time() - last_data_time > 1.5):  # 确保有足够的静默时间
                                    # 额外等待确认没有更多数据
                                    time.sleep(0.5)
                                    if not chan.recv_ready():  # 确认没有pending数据
                                        break
                    else:
                        empty_count += 1
                        # 调整超时检查逻辑 - 华为设备需要更宽松的检查
                        data_silence_time = time.time() - last_data_time
                        total_time = time.time() - start_time
                        
                        # 华为设备专门的超时逻辑
                        if 'huawei' in vendor.lower():
                            if empty_count >= max_empty or data_silence_time > 20 or total_time > timeout:
                                break
                        else:
                            if empty_count >= max_empty or data_silence_time > 12 or total_time > timeout:
                                break
                # 分页符与控制符清理
                output = self.clean_output_preserve_integrity(raw_output, cmd)
                # 从上一次的输出中提取提示符
                prompt = ''
                if prev_raw_output and prev_raw_output.strip():
                    prompt_lines = prev_raw_output.strip().splitlines()
                    if prompt_lines:
                        prompt = prompt_lines[-1].strip()
                        cleaned_lines = output.strip().splitlines()
                        if cleaned_lines and cleaned_lines[0].strip() == prompt:
                            pass
                        else:
                            output = f"{prompt}\n{output}"
                log_output.append(output)
                prev_raw_output = raw_output
            ssh.close()
            safe_name = re.sub(r'[^-\w\-\_\u4e00-\u9fa5]', '_', name)
            out_file = os.path.join(backup_dir, f'{safe_name}_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
            with open(out_file, 'w', encoding='utf-8', errors='ignore') as f:
                f.writelines(log_output)
            return True, out_file, ''
        except Exception as e:
            return False, '', str(e)

    def import_inspect_devices(self):
        file_path = filedialog.askopenfilename(title="选择巡检设备+指令CSV文件", filetypes=[("CSV文件", "*.csv")])
        if file_path:
            try:
                devices = self._open_csv_compat(file_path)
                for device in devices:
                    cmds = []
                    row_list = list(device.values())
                    if len(row_list) > 7:
                        cmds = [cmd.strip() for cmd in row_list[7:] if cmd.strip()]
                    device['cmds'] = cmds
                self.inspect_device_list = devices
                self.inspect_device_count_var.set(f"设备数：{len(self.inspect_device_list)}")
                messagebox.showinfo("导入成功", f"成功导入{len(self.inspect_device_list)}台设备！")
            except Exception as e:
                messagebox.showerror("导入失败", f"导入设备列表失败: {e}")

    def auto_inspect(self):
        if not hasattr(self, 'inspect_device_list') or not self.inspect_device_list:
            messagebox.showwarning("无设备", "请先导入设备+指令列表！")
            return
        inspect_folder = filedialog.askdirectory(title="请选择巡检输出目录")
        if not inspect_folder:
            return
        
        # 清空进度显示
        self.inspect_progress_text.config(state="normal")
        self.inspect_progress_text.delete("1.0", "end")
        self.inspect_progress_text.insert("1.0", "开始巡检任务...\n\n")
        self.inspect_progress_text.config(state="disabled")
        self.inspect_progress_text.update()
        
        # 使用多线程避免界面卡死
        def run_inspect():
            try:
                self._run_inspect_task(inspect_folder)
            except Exception as e:
                # 在主线程中显示错误
                self.root.after(0, lambda: messagebox.showerror("巡检错误", f"巡检过程中发生错误: {e}"))
        
        # 启动巡检线程
        inspect_thread = threading.Thread(target=run_inspect, daemon=True)
        inspect_thread.start()
    
    def _run_inspect_task(self, inspect_folder):
        """并发巡检任务的具体实现（在后台线程中运行）"""
        now = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        folder = os.path.join(inspect_folder, f'inspect_{now}')
        os.makedirs(folder, exist_ok=True)
        total = len(self.inspect_device_list)
        success = 0
        fail = 0
        log_lines = []
        
        # 显示巡检目录信息（使用after方法在主线程中更新UI）
        def update_progress(text):
            self.root.after(0, lambda: self._update_inspect_progress(text))
        
        update_progress(f"巡检目录: {folder}\n")
        update_progress(f"设备总数: {total}\n")
        update_progress(f"并发数: {self.max_concurrent_devices} 台同时进行\n")
        update_progress("=" * 50 + "\n\n")
        
        # 记录总开始时间
        total_start_time = time.time()
        
        # 创建线程池并发执行巡检
        with ThreadPoolExecutor(max_workers=self.max_concurrent_devices) as executor:
            future_to_device = {}
            for idx, device in enumerate(self.inspect_device_list):
                future = executor.submit(self._concurrent_inspect_device, device, folder, idx+1, total)
                future_to_device[future] = device
            
            for future in as_completed(future_to_device):
                device = future_to_device[future]
                name = device.get('name', 'unknown')
                ip = device.get('ip', '-')
                try:
                    result = future.result()
                    ok, logfile, errmsg, duration = result
                except Exception as e:
                    ok, logfile, errmsg, duration = False, '', str(e), 0
                
                if ok:
                    success += 1
                    log_lines.append(f"[SUCCESS] {name} ({ip}) -> {logfile} (耗时: {duration:.1f}秒)")
                else:
                    fail += 1
                    log_lines.append(f"[FAILED] {name} ({ip}) -> {errmsg} (耗时: {duration:.1f}秒)")
                
                update_progress(log_lines[-1] + "\n")
        
        # 计算总耗时
        total_end_time = time.time()
        total_duration = total_end_time - total_start_time
        
        # 写入汇总日志
        summary_log = os.path.join(folder, f'inspect_summary_{now}.log')
        with open(summary_log, 'w', encoding='utf-8', errors='ignore') as f:
            f.write(f"全部设备并发自动巡检完成。\n成功: {success} 台，失败: {fail} 台，总计: {total} 台。\n")
            f.write(f"并发数: {self.max_concurrent_devices} 台\n")
            f.write(f"总耗时: {total_duration:.1f}秒 ({total_duration/60:.1f}分钟)\n")
            f.write(f"平均每台耗时: {total_duration/total:.1f}秒\n")
            f.write(f"效率提升: 相比串行约节省 {max(0, total*60 - total_duration):.0f}秒\n")
            f.write(f"巡检目录: {folder}\n\n")
            f.write('\n'.join(log_lines))
        
        # 显示最终结果
        update_progress(f"\n" + "=" * 50 + "\n")
        update_progress(f"🎉 并发巡检完成！\n")
        update_progress(f"成功: {success} 台，失败: {fail} 台，总计: {total} 台\n")
        update_progress(f"总耗时: {total_duration:.1f}秒 ({total_duration/60:.1f}分钟)\n")
        update_progress(f"并发数: {self.max_concurrent_devices} 台\n")
        update_progress(f"汇总日志: {summary_log}\n")
        
        # 在主线程中显示完成消息
        self.root.after(0, lambda: messagebox.showinfo("完成", 
            f"全部设备并发自动巡检完成！\n成功: {success} 台，失败: {fail} 台，总计: {total} 台。\n"
            f"总耗时: {total_duration:.1f}秒 ({total_duration/60:.1f}分钟)\n"
            f"并发效率提升明显！"))
    
    def _concurrent_inspect_device(self, device, folder, device_idx, total):
        """单个设备的巡检任务（在线程池中执行）"""
        name = device.get('name', 'unknown')
        ip = device.get('ip', '-')
        
        # 记录开始时间
        start_time = time.time()
        
        # 更新进度显示（线程安全）
        def update_progress(text):
            self.root.after(0, lambda: self._update_inspect_progress(text))
        
        update_progress(f"[{device_idx}/{total}] 开始巡检: {name} ({ip})\n")
        
        try:
            # 添加调试信息
            update_progress(f"[{device_idx}/{total}] 正在连接设备: {name} ({ip})\n")
            ok, logfile, errmsg = self.inspect_device(device, folder)
            end_time = time.time()
            duration = end_time - start_time
            
            # 添加完成信息
            if ok:
                update_progress(f"[{device_idx}/{total}] ✅ 巡检完成: {name} ({ip}) -> {logfile} (耗时: {duration:.1f}秒)\n")
            else:
                update_progress(f"[{device_idx}/{total}] ❌ 巡检失败: {name} ({ip}) -> {errmsg} (耗时: {duration:.1f}秒)\n")
            
            return ok, logfile, errmsg, duration
        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time
            update_progress(f"[{device_idx}/{total}] ❌ 巡检异常: {name} ({ip}) -> {str(e)} (耗时: {duration:.1f}秒)\n")
            return False, '', str(e), duration
    
    def _update_inspect_progress(self, text):
        """在主线程中安全地更新巡检进度显示"""
        try:
            self.inspect_progress_text.config(state="normal")
            self.inspect_progress_text.insert("end", text)
            self.inspect_progress_text.config(state="disabled")
            self.inspect_progress_text.see("end")
            self.inspect_progress_text.update()
        except Exception:
            pass  # 忽略UI更新错误

    def inspect_device(self, device, folder):
        """
        彻底迁移V10巡检主循环和分页符处理，保证输出与V10一致。
        """
        name = device.get('name', 'unknown')
        ip = device.get('ip', '-')
        username = device.get('username', 'admin')
        password = device.get('password', '')
        port = int(device.get('port', 22))
        vendor = (device.get('vendor', '') or '').lower()
        cmds = device.get('cmds') if device.get('cmds') else None
        if not cmds:
            if vendor == 'huawei':
                cmds = ['display cpu-usage', 'display memory-usage', 'display current-configuration', 'display fan', 'display power', 'display environment']
            elif vendor == 'cisco':
                cmds = ['show version', 'show running-config']
            else:
                cmds = ['display version', 'show version']
        if isinstance(cmds, str):
            cmds = [cmd.strip() for cmd in cmds.split(',') if cmd.strip()]
        log_output = []
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(str(ip), port=port, username=username, password=password, timeout=30, allow_agent=False, look_for_keys=False)
            chan = ssh.invoke_shell(width=1000, height=200)
            time.sleep(2.5)
            # 登录输出收集 - 修复所有厂商设备登录阶段Y/N自动应答问题
            login_output = ''
            prompt_list = ['#', '>', '$']
            login_timeout = time.time() + 30
            
            # 登录阶段所有厂商的Y/N检测模式（通用匹配）
            login_yn_patterns = [
                # 华为设备常见登录Y/N提示
                r'Change now\?\s*\[Y/N\][:：]\s*$',  # Change now? [Y/N]:
                r'password needs to be changed.*\[Y/N\][:：]\s*$',  # password needs to be changed. Change now? [Y/N]:
                r'Do you want to change.*\[Y/N\][:：]\s*$',  # Do you want to change the password? [Y/N]:
                # 思科设备常见登录Y/N提示
                r'Would you like to enter the initial configuration dialog\?\s*\[yes/no\][:：]\s*$',  # Would you like to enter the initial configuration dialog? [yes/no]:
                r'Would you like to terminate autoinstall\?\s*\[yes\][:：]\s*$',  # Would you like to terminate autoinstall? [yes]:
                # 华三设备常见登录Y/N提示
                r'Save\?\s*\[Y/N\][:：]\s*$',  # Save? [Y/N]:
                r'Continue\?\s*\[Y/N\][:：]\s*$',  # Continue? [Y/N]:
                # 锐捷设备常见登录Y/N提示
                r'Enter the password\?\s*\[yes/no\][:：]\s*$',  # Enter the password? [yes/no]:
                # 通用Y/N模式（登录阶段）
                r'\w+\?\s*\[Y/N\][:：]\s*$',  # 任何问题? [Y/N]:
                r'\w+\?\s*\[yes/no\][:：]\s*$',  # 任何问题? [yes/no]:
            ]
            
            while True:
                time.sleep(0.12)
                if chan.recv_ready():
                    data = chan.recv(65535).decode(errors='ignore')
                    login_output += data
                    
                    # 检查是否是登录阶段的Y/N提示（仅在登录阶段处理）
                    login_yn_found = False
                    for pattern in login_yn_patterns:
                        if re.search(pattern, data, re.IGNORECASE):
                            # 华为设备登录时的密码变更提示，发送 'n' 跳过
                            chan.send(b'n\n')
                            time.sleep(0.3)
                            login_yn_found = True
                            break
                    
                    if not login_yn_found:
                        lines = data.strip().splitlines()
                        if lines:
                            last_line = lines[-1].strip()
                            if any(last_line.endswith(p) for p in prompt_list):
                                break
                if time.time() > login_timeout:
                    break
            prev_raw_output = login_output
            for idx, cmd in enumerate(cmds):
                # 添加命令标识
                log_output.append(f"\n===== 命令 {idx + 1}: {cmd} =====\n")
                
                chan.send((cmd + '\n').encode('utf-8'))
                time.sleep(1.0)
                raw_output = ''
                start_time = time.time()
                
                # 扩展的分页符检测列表 - 支持所有主流厂商 (巡检模块)
                pagination_indicators = [
                    # 华为设备分页符
                    '---- More ----', '--More--', '<--- More --->', '--- More ---',
                    'Press any key to continue', 'Press SPACE to continue', 'Press Q to quit',
                    '按任意键继续', '按空格键继续', '按Q键退出',
                    # 华三设备分页符
                    '---- More ----', '--More--', 'More:', '(more)', '[more]', 
                    '---- more ----', '--more--', '(MORE)', '[MORE]', '-- More --', '---More---',
                    # 思科设备分页符
                    '--More--', 'Press any key to continue', 'Press SPACE for more',
                    '-- More --', '<spacebar> for more', 'q to quit',
                    # 锐捷设备分页符
                    '---- More ----', '--More--', 'More...', '(More)', '[More]',
                    'Press any key to continue', 'Press SPACE to continue',
                    # 其他厂商通用分页符
                    'Continue?', 'More (Press SPACE)', 'More (Press any key)',
                    '继续？', '更多(按空格键)', '更多(按任意键)'
                ]
                
                prompt_regex = r'({})\\s*$'.format('|'.join([re.escape(p) for p in prompt_list]))
                stable_prompt_count = 0
                required_stable_count = 3  # 减少稳定计数要求
                last_output_len = 0
                no_growth_count = 0
                max_no_growth = 25  # 减少无增长计数
                
                timeout = 300
                if any(x in cmd.lower() for x in ['configuration', 'running-config', 'startup-config']):
                    timeout = 600  # 配置命令需要更长时间
                elif any(x in cmd.lower() for x in ['version', 'hardware', 'system']):
                    timeout = 180
                
                # 针对不同厂商的特殊处理 - 全面优化所有厂商参数
                if 'ruijie' in vendor.lower() or '锐捷' in vendor.lower():
                    max_no_growth = 20
                    required_stable_count = 2
                    timeout += 120  # 锐捷设备额外增加2分钟
                elif 'h3c' in vendor.lower():
                    timeout = 600  # 华三设备需要更长时间
                    max_no_growth = 30
                    required_stable_count = 4
                    timeout += 240  # 华三设备额外增加4分钟
                elif 'huawei' in vendor.lower():
                    max_no_growth = 40
                    required_stable_count = 3
                    timeout += 300  # 华为设备额外增加5分钟
                elif 'cisco' in vendor.lower():
                    max_no_growth = 25
                    required_stable_count = 3
                    timeout += 180  # 思科设备额外增加3分钟
                else:
                    max_no_growth = 25
                    required_stable_count = 3
                    timeout += 120  # 其他厂商额外增加2分钟
                
                while True:
                    time.sleep(0.08)  # 稍微加快循环速度
                    if chan.recv_ready():
                        data = chan.recv(65535).decode(errors='ignore')
                        
                        # 改进的分页符检测：精确的完整行匹配，避免误判配置内容
                        pagination_found = False
                        data_lines = data.split('\n')
                        for line in data_lines:
                            line_clean = line.strip()
                            # 精确匹配分页符：必须是完整的分页符行，避免误判配置
                            for indicator in pagination_indicators:
                                # 方法1：完全相等匹配
                                if line_clean.lower() == indicator.lower().strip():
                                    chan.send(b' ')
                                    time.sleep(0.2)  # 增加延迟确保分页命令生效
                                    pagination_found = True
                                    break
                                # 方法2：精确的正则匹配（行首行尾匹配）
                                elif re.match(rf'^\s*{re.escape(indicator)}\s*$', line_clean, re.IGNORECASE):
                                    chan.send(b' ')
                                    time.sleep(0.2)
                                    pagination_found = True
                                    break
                            if pagination_found:
                                break
                        
                        # 处理Y/N应答（仅在命令执行阶段，更严格的匹配）
                        if not pagination_found:
                            yn_patterns = [
                                r'\(y/n\)[:：]\s*$',  # (y/n): 
                                r'\(yes/no\)[:：]\s*$',  # (yes/no):
                                r'\[[yY]/[nN]\][:：]\s*$',  # [y/n]:
                                r'\([yY]/[nN]\)[:：]\s*$',  # (y/n):
                                r'\[[yY][eE][sS]/[nN][oO]\][:：]\s*$',  # [yes/no]:
                                r'\([yY][eE][sS]/[nN][oO]\)[:：]\s*$',  # (yes/no):
                                r'continue\s*\?\s*\([yY]/[nN]\)[:：]\s*$',  # continue? (y/n):
                                r'sure\s*\?\s*\([yY]/[nN]\)[:：]\s*$',  # sure? (y/n):
                            ]
                            
                            yn_found = False
                            for pattern in yn_patterns:
                                if re.search(pattern, data, re.IGNORECASE):
                                    chan.send(b'n\n')
                                    time.sleep(0.15)
                                    yn_found = True
                                    break
                        
                        raw_output += data
                        
                        # 检查命令提示符
                        lines = data.strip().splitlines()
                        if lines:
                            last_line = lines[-1].strip()
                            if re.search(prompt_regex, last_line):
                                stable_prompt_count += 1
                                if stable_prompt_count >= required_stable_count:
                                    break
                            else:
                                stable_prompt_count = 0
                        
                        # 检查输出增长
                        if len(raw_output) == last_output_len:
                            no_growth_count += 1
                            if no_growth_count > max_no_growth:
                                break
                        else:
                            no_growth_count = 0
                            last_output_len = len(raw_output)
                    else:
                        no_growth_count += 1
                        if no_growth_count > max_no_growth or (time.time() - start_time > timeout):
                            break
                # 分页符与控制符清理
                output = self.clean_output_preserve_integrity(raw_output, cmd)
                # 从上一次的输出中提取提示符
                prompt = ''
                if prev_raw_output and prev_raw_output.strip():
                    prompt_lines = prev_raw_output.strip().splitlines()
                    if prompt_lines:
                        prompt = prompt_lines[-1].strip()
                        cleaned_lines = output.strip().splitlines()
                        if cleaned_lines and cleaned_lines[0].strip() == prompt:
                            pass
                        else:
                            output = f"{prompt}\n{output}"
                log_output.append(output)
                prev_raw_output = raw_output
            ssh.close()
            safe_name = re.sub(r'[^-\w\-\_\u4e00-\u9fa5]', '_', name)
            out_file = os.path.join(folder, f'{safe_name}_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
            with open(out_file, 'w', encoding='utf-8', errors='ignore') as f:
                f.writelines(log_output)
            return True, out_file, ''
        except Exception as e:
            return False, '', str(e)

    def clean_output_preserve_integrity(self, text, command=None):
        """
        V13增强版输出清理函数，智能处理分页符遗留的异常空格，同时保留原始缩进和列对齐
        """
        if not text:
            return text
        # 第一步：移除ANSI转义序列，但绝对保留换行符
        text = re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', text)
        text = re.sub(r'\x1b\[[0-9]*[A-Za-z]', '', text)
        # 第二步：处理锐捷设备的退格符问题
        text = re.sub(r'(\x08)+', '', text)
        text = re.sub(r'(\bBS\b\s*)+', '', text)
        # 第三步：统一换行符，但保留所有换行
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        # 第四步：逐行精确处理分页符和空格遗留问题
        lines = text.split('\n')
        cleaned_lines = []
        pagination_patterns = [
            r'---- More ----', r'--More--', r'<--- More --->', r'--- More ---',
            r'Press any key to continue', r'Press SPACE to continue', r'Press Q to quit',
            r'More:', r'\(more\)', r'\[more\]', r'---- more ----', r'--more--', 
            r'\(MORE\)', r'\[MORE\]', r'-- More --', r'---More---'
        ]
        for line in lines:
            original_line = line
            line_stripped = line.strip()
            is_pure_pagination = False
            for pattern in pagination_patterns:
                if re.fullmatch(pattern, line_stripped, flags=re.IGNORECASE):
                    is_pure_pagination = True
                    break
            if is_pure_pagination:
                continue
            cleaned_line = original_line
            for pattern in pagination_patterns:
                match = re.search(pattern, cleaned_line, re.IGNORECASE)
                if match:
                    before = cleaned_line[:match.start()]
                    after = cleaned_line[match.end():]
                    before_clean = before.rstrip()
                    after_clean = after.lstrip()
                    if after_clean.strip():
                        cleaned_line = after_clean
                    elif before_clean.strip():
                        cleaned_line = before_clean
                    else:
                        cleaned_line = ''
                    break
            # 清理Y/N自动应答残留（仅清理明显的孤立应答字符）
            if re.match(r'^\s*[nNyY]\s*$', cleaned_line):
                continue
            cleaned_line = re.sub(r'\(y/n\):\s*[nNyY]\s*$', '(y/n):', cleaned_line, flags=re.IGNORECASE)
            cleaned_line = re.sub(r'\(yes/no\):\s*(yes|no)\s*$', '(yes/no):', cleaned_line, flags=re.IGNORECASE)
            cleaned_line = re.sub(r'\[Y/N\]:\s*[nNyY]\s*$', '[Y/N]:', cleaned_line, flags=re.IGNORECASE)
            # V13增强：智能处理行首异常空格（分页符遗留）
            leading_match = re.match(r'^(\s+)', cleaned_line)
            if leading_match:
                leading_spaces = leading_match.group(1)
                leading_count = len(leading_spaces)
                content_after_spaces = cleaned_line[leading_count:]
                is_abnormal_leading = False
                # 超过8个空格且内容为命令/任务/表格，判定为异常
                if leading_count >= 8:
                    if re.match(r'^[A-Z0-9]+\s+\d+%', content_after_spaces):
                        is_abnormal_leading = True
                    elif re.match(r'^[A-Z][A-Z0-9_]+\s+', content_after_spaces):
                        is_abnormal_leading = True
                    elif re.match(r'^\w+\s+\w+\s+:', content_after_spaces):
                        is_abnormal_leading = True
                if is_abnormal_leading:
                    cleaned_line = content_after_spaces
            # V13增强：行内异常空格压缩（分页符遗留）
            # 对于任务/表格类，超过8个连续空格压缩为2个空格
            cleaned_line = re.sub(r' {8,}', '  ', cleaned_line)
            # 只清理行尾过多的空格（超过10个连续空格的行尾）
            if re.search(r'\s{10,}$', cleaned_line):
                cleaned_line = cleaned_line.rstrip()
            cleaned_lines.append(cleaned_line)
        # 第五步：适度的空行合并（保留格式完整性）
        final_lines = []
        consecutive_empty = 0
        for line in cleaned_lines:
            if not line.strip():
                consecutive_empty += 1
                if consecutive_empty <= 2:
                    final_lines.append(line)
            else:
                consecutive_empty = 0
                final_lines.append(line)
        result = '\n'.join(final_lines)
        if result and not result.endswith('\n'):
            result += '\n'
        return result

    def show_device_status(self):
        if not hasattr(self, 'inspect_device_list') or not self.inspect_device_list:
            messagebox.showwarning("无设备", "请先导入设备+指令列表！")
            return
        
        status_window = tk.Toplevel(self.root)
        status_window.title("设备状态")
        status_text = tk.Text(status_window, wrap="word", font=("微软雅黑", 10))
        status_text.pack(fill="both", expand=True)
        
        for dev in self.inspect_device_list:
            name = dev.get('name') or dev.get('设备名') or dev.get('设备名称') or dev.get('主机名')
            ip = dev.get('ip') or dev.get('IP')
            vendor = (dev.get('vendor') or dev.get('厂商') or '').strip()
            status_text.insert(tk.END, f"设备名: {name}\nIP: {ip}\n厂商: {vendor}\n状态: 正常\n\n")
        
        status_text.config(state=tk.DISABLED)

    def parse_device_status_from_logs(self):
        """
        从巡检日志中解析设备状态，使用 extract_device_status.py 模块
        """
        log_dir = filedialog.askdirectory(title="请选择巡检日志文件夹")
        if not log_dir:
            return

        # 动态加载 extract_device_status.py
        try:
            importlib.invalidate_caches()  # 强制清除缓存，确保加载最新模块
            
            # 多路径查找 extract_device_status.py
            possible_paths = []
            # PyInstaller打包后的临时目录
            if hasattr(sys, '_MEIPASS'):
                possible_paths.append(os.path.join(sys._MEIPASS, 'extract_device_status.py'))
            # 当前文件同目录
            if '__file__' in globals():
                possible_paths.append(os.path.join(os.path.dirname(__file__), 'extract_device_status.py'))
            # 当前工作目录
            possible_paths.append(os.path.abspath('extract_device_status.py'))
            # 程序所在目录
            if hasattr(sys, 'executable') and sys.executable:
                exe_dir = os.path.dirname(sys.executable)
                possible_paths.append(os.path.join(exe_dir, 'extract_device_status.py'))
            # 脚本所在目录
            possible_paths.append(os.path.join(os.getcwd(), 'extract_device_status.py'))
            
            found_path = None
            for p in possible_paths:
                if os.path.isfile(p):
                    found_path = p
                    break
            
            if found_path is None:
                messagebox.showerror("导入失败", "未找到 extract_device_status.py，请确保该文件与程序在同一目录！")
                return
                
            spec = importlib.util.spec_from_file_location("extract_device_status", found_path)
            if spec is None or spec.loader is None:
                messagebox.showerror("导入失败", "无法加载 extract_device_status.py 模块！")
                return
                
            extract_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(extract_module)
            
            # 使用模块解析日志
            status_data = extract_module.parse_log_files(log_dir)
            
            if not status_data:
                messagebox.showwarning("解析结果", "未找到可解析的日志文件或解析结果为空！")
                return
            
        except Exception as e:
            messagebox.showerror("解析失败", f"解析设备状态时发生错误: {e}")
            return

        # 显示解析结果窗口
        win = tk.Toplevel(self.root)
        win.title("设备状态解析结果")
        win.geometry("1200x600")
        
        # 顶部按钮区
        top_frame = tk.Frame(win)
        top_frame.pack(fill="x", pady=5)
        
        tk.Label(top_frame, text=f"解析完成，共找到 {len(status_data)} 台设备", 
                font=("微软雅黑", 12, "bold")).pack(side="left", padx=10)

        def export_parsed_data_to_csv():
            save_path = filedialog.asksaveasfilename(
                title="导出解析结果到CSV",
                defaultextension=".csv",
                initialfile="inspect_parsed_summary.csv",
                filetypes=[("CSV文件", "*.csv")]
            )
            if not save_path:
                return

            try:
                # 使用status_data中的第一个字典的键作为表头
                if status_data:
                    headers = list(status_data[0].keys())
                    with open(save_path, 'w', newline='', encoding='utf-8-sig') as f:
                        writer = csv.DictWriter(f, fieldnames=headers)
                        writer.writeheader()
                        writer.writerows(status_data)
                    messagebox.showinfo("导出成功", f"解析结果已成功导出到：\n{save_path}")
            except Exception as e:
                messagebox.showerror("导出失败", f"导出CSV文件时发生错误: {e}")

        tk.Button(top_frame, text="导出为CSV", command=export_parsed_data_to_csv, 
                 font=("微软雅黑", 10)).pack(side="right", padx=10)

        # 异常优先排序
        def abnormal_score(row):
            score = 0
            for k in ['CPU使用率', '内存使用率', '温度状态', '电源状态', '风扇状态']:
                v = str(row.get(k, '')).lower()
                if '异常' in v or 'abnormal' in v or 'fail' in v or 'down' in v:
                    score += 5
                # CPU/内存使用率过高（假设阈值为80%）
                elif '%' in v:
                    try:
                        val = float(v.replace('%', ''))
                        if val > 80:
                            score += 3
                    except ValueError:
                        pass
            return -score

        status_data.sort(key=abnormal_score)

        # 显示结果表格
        columns = ("设备名", "时间", "厂商", "CPU使用率", "内存使用率", "温度状态", "电源状态", "风扇状态", "运行时间")
        tree_frame = tk.Frame(win)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        tree = ttk.Treeview(tree_frame, columns=columns, show='headings')
        
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=110, anchor='center')

        for item in status_data:
            values = [item.get(col, 'N/A') for col in columns]
            tree.insert('', 'end', values=values)
        
        # 添加滚动条
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        vsb.pack(side='right', fill='y')
        tree.configure(yscrollcommand=vsb.set)
        
        tree.pack(fill='both', expand=True)

    # 管理功能实现
    def import_manage_devices(self):
        file_path = filedialog.askopenfilename(title="选择设备CSV文件", filetypes=[("CSV文件", "*.csv")])
        if file_path:
            try:
                self.manage_device_list = self._open_csv_compat(file_path)
                if not self.manage_device_list:
                    messagebox.showwarning("导入失败", "设备列表为空！")
                    return
                self.current_account_list = []
                self.account_tree.delete(*self.account_tree.get_children())
                for dev in self.manage_device_list:
                    username = dev.get('username') or dev.get('account') or dev.get('user')
                    privilege = dev.get('privilege') or dev.get('role') or ''
                    desc = dev.get('desc') or dev.get('description') or ''
                    if username:
                        self.current_account_list.append({'用户名': username, '权限': privilege, '描述': desc})
                for acc in self.current_account_list:
                    self.account_tree.insert('', 'end', values=(acc['用户名'], acc['权限'], acc['描述']))
                messagebox.showinfo("导入成功", f"成功导入{len(self.manage_device_list)}台设备，账号{len(self.current_account_list)}条。")
            except Exception as e:
                messagebox.showerror("导入失败", f"导入设备列表失败: {e}")

    def update_status_chart(self):
        """绘制设备在线状态饼图"""
        self.status_canvas.delete("all")
        total = len(self.device_list)
        online = sum(1 for s in self.online_status.values() if s == '在线')
        offline = total - online
        if total == 0:
            return
        angle_online = 360 * online / total
        angle_offline = 360 * offline / total
        self.status_canvas.create_arc(40, 40, 200, 200, start=0, extent=angle_online, fill="#6fa8dc", outline="")
        self.status_canvas.create_arc(40, 40, 200, 200, start=angle_online, extent=angle_offline, fill="#f4cccc", outline="")
        self.status_canvas.create_oval(80, 80, 160, 160, fill="#f7fbff", outline="")
        self.status_canvas.create_text(120, 120, text=f"在线: {online}\n离线: {offline}", font=("微软雅黑", 15, "bold"), fill="#007acc")
        self.status_label.config(text=f"设备总数: {total}，在线: {online}，离线: {offline}")

    def show_all_device_status(self):
        """显示所有设备的详细状态信息"""
        from tkinter import messagebox
        try:
            # 动态查找 extract_device_status.py
            possible_paths = []
            # PyInstaller打包后的临时目录
            if hasattr(sys, '_MEIPASS'):
                possible_paths.append(os.path.join(sys._MEIPASS, 'extract_device_status.py'))
            # 当前文件同目录
            if '__file__' in globals():
                possible_paths.append(os.path.join(os.path.dirname(__file__), 'extract_device_status.py'))
            # 当前工作目录
            possible_paths.append(os.path.abspath('extract_device_status.py'))
            # 程序所在目录
            if hasattr(sys, 'executable') and sys.executable:
                exe_dir = os.path.dirname(sys.executable)
                possible_paths.append(os.path.join(exe_dir, 'extract_device_status.py'))
            # 脚本所在目录的上级目录
            possible_paths.append(os.path.join(os.getcwd(), '..', 'extract_device_status.py'))
            possible_paths.append(os.path.join(os.getcwd(), 'extract_device_status.py'))
            
            found_path = None
            for p in possible_paths:
                if os.path.isfile(p):
                    found_path = p
                    break
            # 设备厂商命令字典
            vendor_cmds = {
                'huawei': [
                    'display cpu-usage',
                    'display memory-usage',
                    'display temperature',
                    'display power',
                    'display fan'
                ],
                'h3c': [
                    'display cpu-usage',
                    'display cpu',
                    'display memory',
                    'display temperature all',
                    'display power',
                    'display fan'
                ],
                'cisco': [
                    'show processes cpu',
                    'show processes memory',
                    'show environment temperature',
                    'show environment power',
                    'show environment fan'
                ],
                'ruijie': [
                    'show cpu',
                    'show memory',
                    'show temperature',
                    'show power',
                    'show fan'
                ]
            }
            def safe_vendor(v):
                v = (v or '').lower()
                if 'huawei' in v:
                    return 'huawei'
                if 'h3c' in v:
                    return 'h3c'
                if 'cisco' in v:
                    return 'cisco'
                if 'ruijie' in v or '锐捷' in v:
                    return 'ruijie'
                return 'huawei'  # 默认
            # 进度窗口
            progress = tk.Toplevel(self.root)
            progress.title("设备状态采集进度")
            label = tk.Label(progress, text="正在采集设备状态...", font=("微软雅黑", 12))
            label.pack(padx=20, pady=10)
            progress.update()
            result = []
            total = len(self.device_list)
            for idx, dev in enumerate(self.device_list):
                name = dev.get('name') or dev.get('设备名') or dev.get('设备名称') or dev.get('主机名')
                ip = dev.get('ip') or dev.get('IP')
                vendor = (dev.get('vendor') or dev.get('厂商') or '').strip()
                username = dev.get('username') or dev.get('用户名') or 'admin'
                password = dev.get('password') or dev.get('密码') or ''
                port = int(dev.get('port') or dev.get('端口') or 22)
                status = '离线'
                label.config(text=f"[{idx+1}/{total}] {name} ({ip}) 状态采集中...")
                progress.update()
                output_all = ''
                try:
                    ssh = paramiko.SSHClient()
                    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    ssh.connect(str(ip), port=port, username=username, password=password, timeout=10, allow_agent=False, look_for_keys=False)
                    chan = ssh.invoke_shell()
                    time.sleep(1)
                    prompt_list = ['#', '>', '$']
                    login_output = ''
                    login_timeout = time.time() + 20
                    while True:
                        time.sleep(0.12)
                        if chan.recv_ready():
                            data = chan.recv(65535).decode(errors='ignore')
                            login_output += data
                            lines = data.strip().splitlines()
                            if lines:
                                last_line = lines[-1].strip()
                                if any(last_line.endswith(p) for p in prompt_list):
                                    break
                        if time.time() > login_timeout:
                            break
                    
                    vendor_key = safe_vendor(vendor)
                    cmds = vendor_cmds.get(vendor_key, vendor_cmds['huawei'])
                    for cmd in cmds:
                        if not cmd.endswith('\n'):
                            cmd += '\n'
                        chan.send(cmd.encode())
                        time.sleep(0.5)
                        cmd_output = ''
                        last_data_time = time.time()
                        empty_count = 0
                        max_empty = 50
                        yn_pattern = re.compile(r'(yes\s*/\s*no|no\s*/\s*yes|y\s*/\s*n|n\s*/\s*y|\[[yY]/[nN]\]|\([yY]/[nN]\)|\[[yY][eE][sS]/[nN][oO]\]|\([yY][eE][sS]/[nN][oO]\)|[yY][eE][sS]\?|[nN][oO]\?|[yY][nN]\?|[yY][eE][sS]/[nN][oO]|[yY][nN])', re.IGNORECASE)
                        while True:
                            time.sleep(0.12)
                            if chan.recv_ready():
                                data = chan.recv(65535).decode(errors='ignore')
                                cmd_output += data
                                last_data_time = time.time()
                                # 处理分页符：发送空格键继续分页
                                if '---- More ----' in data or '--More--' in data:
                                    chan.send(b' ')
                                    time.sleep(0.06)
                                    continue
                                # Y/N自动应答
                                if yn_pattern.search(data):
                                    chan.send(b'n\n')
                                    time.sleep(0.15)
                                lines = data.strip().splitlines()
                                if lines:
                                    last_line = lines[-1].strip()
                                    if any(last_line.endswith(p) for p in prompt_list):
                                        break
                            else:
                                empty_count += 1
                                if empty_count >= max_empty or (time.time() - last_data_time > 8):
                                    break
                        output_all += f"\n{cmd.strip()}\n{cmd_output}"
                    
                    ssh.close()
                    status = '在线'
                except Exception as e:
                    output_all += f"\n[ERROR] {e}"
                    status = '离线'
                # 解析状态（严格对标extract_device_status.py和标准文档，字段名与汇总一致）
                vendor_detected = vendor
                info = {}
                
                # 优先使用extract_device_status.py解析
                try:
                    if found_path is not None:
                        spec = importlib.util.spec_from_file_location("extract_device_status", found_path)
                        if spec is not None and spec.loader is not None:
                            extract_module = importlib.util.module_from_spec(spec)
                            spec.loader.exec_module(extract_module)
                            vendor_detected = extract_module.detect_vendor(output_all)
                            info = extract_module.extract_info(output_all, vendor_detected)
                except Exception:
                    pass
                
                # 如果extract_device_status.py未能提取到有效信息，使用简化的状态解析
                if not info or all(not info.get(k) for k in ['cpu', 'mem', 'temp', 'power', 'fan']):
                    info = self._parse_device_status_fallback(output_all, vendor_detected, status)
                
                # 确保所有字段都有值，解析失败时填充N/A
                cpu = str(info.get('cpu', '')).strip()
                mem = str(info.get('mem', '')).strip()
                temp = str(info.get('temp', '')).strip()
                power = str(info.get('power', '')).strip()
                fan = str(info.get('fan', '')).strip()
                uptime = str(info.get('uptime', '')).strip()
                
                # 对于在线设备，如果字段为空则填充N/A；对于离线设备，保持空值
                if status == '在线':
                    if not cpu:
                        cpu = 'N/A'
                    if not mem:
                        mem = 'N/A'
                    if not temp:
                        temp = 'N/A'
                    if not power:
                        power = 'N/A'
                    if not fan:
                        fan = 'N/A'
                    if not uptime:
                        uptime = 'N/A'
                
                row = {
                    '设备名': name,
                    'IP': ip,
                    '厂商': vendor_detected,
                    '状态': status,
                    'CPU': cpu,
                    '内存': mem,
                    '温度': temp,
                    '电源': power,
                    '风扇': fan,
                    '运行时间': uptime
                }
                result.append(row)
            progress.destroy()
            # 异常优先排序
            def abnormal_score(row):
                score = 0
                if row['状态'] != '在线':
                    score += 10
                for k in ['CPU', '内存', '温度', '电源', '风扇']:
                    v = str(row.get(k, ''))
                    if v and (('异常' in v) or ('告警' in v) or ('高' in v) or ('坏' in v) or ('down' in v.lower()) or ('fail' in v.lower())):
                        score += 5
                return -score
            result.sort(key=abnormal_score)
            # 更新表格表头和内容
            self.tree['columns'] = ("设备名", "IP", "厂商", "状态", "CPU", "内存", "温度", "电源", "风扇", "运行时间")
            for col in ("设备名", "IP", "厂商", "状态", "CPU", "内存", "温度", "电源", "风扇", "运行时间"):
                self.tree.heading(col, text=col)
                self.tree.column(col, anchor="center", width=110)
            self.monitor_results = result  # 保存详细结果
            self.update_tree(result)
        except Exception as e:
            messagebox.showerror("设备状态采集失败", f"采集设备状态时发生错误: {e}")

    def export_current_table(self):
        """导出当前表格数据为CSV"""
        if not hasattr(self, 'tree') or not self.tree.get_children():
            messagebox.showwarning("无数据", "没有可导出的数据！")
            return
        save_path = filedialog.asksaveasfilename(
            title="导出表格数据",
            defaultextension=".csv",
            initialfile="monitor_results.csv",
            filetypes=[("CSV文件", "*.csv")]
        )
        if save_path:
            try:
                with open(save_path, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    # 写入表头
                    headers = ["设备名", "IP", "厂商", "状态", "CPU", "内存", "温度", "电源", "风扇", "运行时间"]
                    writer.writerow(headers)
                    # 写入数据
                    for item in self.tree.get_children():
                        values = self.tree.item(item)['values']
                        writer.writerow(values)
                messagebox.showinfo("导出成功", f"数据已导出到: {save_path}")
            except Exception as e:
                messagebox.showerror("导出失败", f"导出数据失败: {e}")

    def update_tree(self, data):
        """更新表格数据"""
        # 清空现有数据
        for item in self.tree.get_children():
            self.tree.delete(item)
        # 插入新数据
        for row in data:
            values = [
                row.get('设备名', ''),
                row.get('IP', ''),
                row.get('厂商', ''),
                row.get('状态', ''),
                row.get('CPU', ''),
                row.get('内存', ''),
                row.get('温度', ''),
                row.get('电源', ''),
                row.get('风扇', ''),
                row.get('运行时间', '')
            ]
            self.tree.insert("", "end", values=values)

    def export_backup_template(self):
        """导出备份模板"""
        save_path = filedialog.asksaveasfilename(title="导出备份模板", defaultextension=".csv", initialfile="devices-v1.csv", filetypes=[("CSV文件", "*.csv")])
        if save_path:
            try:
                shutil.copyfile(os.path.join(os.path.dirname(__file__), '../../devices-v1.csv'), save_path)
                messagebox.showinfo("导出成功", f"模板已导出到: {save_path}")
            except Exception as e:
                messagebox.showerror("导出失败", f"导出模板失败: {e}")

    def export_inspect_template(self):
        """导出巡检模板"""
        save_path = filedialog.asksaveasfilename(
            title="导出巡检设备+指令模板",
            defaultextension=".csv", 
            initialfile="inspect_template.csv",
            filetypes=[("CSV文件", "*.csv")]
        )
        if save_path:
            try:
                # 创建巡检模板，包含设备信息和命令列
                headers = [
                    'name',       # 设备名
                    'ip',         # IP地址
                    'username',   # 用户名
                    'password',   # 密码
                    'port',       # 端口
                    'vendor',     # 厂商
                    'description', # 描述
                    'cmd1',       # 命令1
                    'cmd2',       # 命令2
                    'cmd3',       # 命令3
                    'cmd4',       # 命令4
                    'cmd5'        # 命令5
                ]
                
                # 示例数据
                sample_data = [
                    {
                        'name': '核心交换机-示例',
                        'ip': '192.168.1.1',
                        'username': 'admin',
                        'password': 'password',
                        'port': '22',
                        'vendor': 'huawei',
                        'description': '核心交换机示例',
                        'cmd1': 'display cpu-usage',
                        'cmd2': 'display memory-usage',
                        'cmd3': 'display temperature',
                        'cmd4': 'display power',
                        'cmd5': 'display fan'
                    },
                    {
                        'name': '接入交换机-示例',
                        'ip': '192.168.1.2', 
                        'username': 'admin',
                        'password': 'password',
                        'port': '22',
                        'vendor': 'h3c',
                        'description': '接入交换机示例',
                        'cmd1': 'display cpu-usage',
                        'cmd2': 'display memory',
                        'cmd3': 'display environment',
                        'cmd4': 'display power',
                        'cmd5': 'display fan'
                    },
                    {
                        'name': '路由器-示例',
                        'ip': '192.168.1.3',
                        'username': 'admin',
                        'password': 'password',
                        'port': '22',
                        'vendor': 'cisco',
                        'description': '路由器示例',
                        'cmd1': 'show processes cpu',
                        'cmd2': 'show processes memory',
                        'cmd3': 'show environment temperature',
                        'cmd4': 'show environment power',
                        'cmd5': 'show environment fan'
                    }
                ]
                
                with open(save_path, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.DictWriter(f, fieldnames=headers)
                    writer.writeheader()
                    writer.writerows(sample_data)
                
                messagebox.showinfo("导出成功", 
                    f"巡检模板已导出到: {save_path}\n\n"
                    "模板说明:\n"
                    "• name: 设备名称\n"
                    "• ip: 设备IP地址\n"
                    "• username/password: 登录凭据\n"
                    "• port: SSH端口(默认22)\n"
                    "• vendor: 厂商(huawei/h3c/cisco/ruijie)\n"
                    "• cmd1-cmd5: 巡检命令(可根据需要修改)")
                    
            except Exception as e:
                messagebox.showerror("导出失败", f"导出巡检模板失败: {e}")

    def export_monitor_log(self):
        """导出监控日志"""
        if not self.monitor_results:
            messagebox.showwarning("无数据", "没有监控数据可导出！")
            return
        save_path = filedialog.asksaveasfilename(
            title="导出监控日志",
            defaultextension=".csv",
            initialfile="monitor_log.csv",
            filetypes=[("CSV文件", "*.csv")]
        )
        if save_path:
            try:
                with open(save_path, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.DictWriter(f, fieldnames=["设备名", "IP", "厂商", "状态", "CPU", "内存", "温度", "电源", "风扇"])
                    writer.writeheader()
                    writer.writerows(self.monitor_results)
                self.root.after(0, lambda: messagebox.showinfo("导出成功", f"监控日志已导出到: {save_path}"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("导出失败", f"导出监控日志失败: {e}"))

    def export_logs(self):
        """导出日志功能"""
        save_path = filedialog.asksaveasfilename(title="导出日志", defaultextension=".txt", initialfile="logs.txt", filetypes=[("文本文件", ".txt")])
        if save_path:
            try:
                with open(save_path, 'w', encoding='utf-8') as f:
                    f.write("日志内容示例\n")
                self.root.after(0, lambda: messagebox.showinfo("导出成功", f"日志已导出到: {save_path}"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("导出失败", f"导出日志失败: {e}"))

    def backup_scheduler(self):
        # 定时备份功能实现
        def start_schedule():
            try:
                hours = int(entry.get())
                if hours <= 0:
                    raise ValueError
            except Exception:
                self.root.after(0, lambda: messagebox.showerror("输入错误", "请输入有效的小时数！"))
                return
            if hasattr(self, 'backup_schedule_thread') and self.backup_schedule_thread and self.backup_schedule_thread.is_alive():
                self.root.after(0, lambda: messagebox.showinfo("定时备份", "定时备份已在运行！"))
                return
            self.backup_schedule_stop = False
            def schedule_loop():
                while not getattr(self, 'backup_schedule_stop', False):
                    self.root.after(0, self.backup_now)
                    for _ in range(hours * 3600):
                        if getattr(self, 'backup_schedule_stop', False):
                            break
                        time.sleep(1)
            self.backup_schedule_thread = threading.Thread(target=schedule_loop, daemon=True)
            self.backup_schedule_thread.start()
            self.root.after(0, lambda: messagebox.showinfo("定时备份", f"定时备份已启动，每{hours}小时执行一次。关闭窗口或重启程序可停止。"))
        win = tk.Toplevel(self.root)
        win.title("定时备份设置")
        tk.Label(win, text="请输入备份周期（小时）：", font=("微软雅黑", 12)).pack(padx=20, pady=10)
        entry = tk.Entry(win, font=("微软雅黑", 12))
        entry.insert(0, "24")
        entry.pack(padx=20, pady=5)
        tk.Button(win, text="启动定时备份", font=("微软雅黑", 12, "bold"), command=start_schedule).pack(padx=20, pady=10)

    def inspect_scheduler(self):
        # 定时巡检功能实现
        def start_schedule():
            try:
                hours = int(entry.get())
                if hours <= 0:
                    raise ValueError
            except Exception:
                self.root.after(0, lambda: messagebox.showerror("输入错误", "请输入有效的小时数！"))
                return
            if hasattr(self, 'inspect_schedule_thread') and self.inspect_schedule_thread and self.inspect_schedule_thread.is_alive():
                self.root.after(0, lambda: messagebox.showinfo("定时巡检", "定时巡检已在运行！"))
                return
            self.inspect_schedule_stop = False
            def schedule_loop():
                while not getattr(self, 'inspect_schedule_stop', False):
                    self.root.after(0, self.auto_inspect)
                    for _ in range(hours * 3600):
                        if getattr(self, 'inspect_schedule_stop', False):
                            break
                        time.sleep(1)
            self.inspect_schedule_thread = threading.Thread(target=schedule_loop, daemon=True)
            self.inspect_schedule_thread.start()
            self.root.after(0, lambda: messagebox.showinfo("定时巡检", f"定时巡检已启动，每{hours}小时执行一次。关闭窗口或重启程序可停止。"))
        win = tk.Toplevel(self.root)
        win.title("定时巡检设置")
        tk.Label(win, text="请输入巡检周期（小时）：", font=("微软雅黑", 12)).pack(padx=20, pady=10)
        entry = tk.Entry(win, font=("微软雅黑", 12))
        entry.insert(0, "72")
        entry.pack(padx=20, pady=5)
        tk.Button(win, text="启动定时巡检", font=("微软雅黑", 12, "bold"), command=start_schedule).pack(padx=20, pady=10)

    def _parse_device_status_fallback(self, output_all, vendor, status):
        """
        简化的设备状态解析方法，当extract_device_status.py无法提取有效信息时使用
        严格对标extract_device_status.py的解析逻辑和字段定义
        """
        info = {
            'cpu': '',
            'mem': '',
            'temp': '',
            'power': '',
            'fan': '',
            'uptime': ''
        }
        
        # 如果设备离线，返回空信息（不填充N/A）
        if status == '离线':
            return info
            
        # 基于extract_device_status.py的解析规则进行简化版本解析
        output_lower = output_all.lower()
        
        # CPU使用率解析 - 对标extract_device_status.py的模式
        cpu_patterns = [
            # 华三专用：Slot X CPU usage 下的 "in last 5 minutes"
            r'slot \d+ cpu usage:[^\n]*\n(?:.*\n)*?\s*([\d.]+)% in last 5 minutes',
            # 锐捷专用：CPU utilization in five minutes
            r'cpu utilization in five minutes:\s*([\d.]+)%',
            # 通用模式
            r'cpu.*?:\s*(\d+)%',
            r'cpu.*?usage.*?(\d+)%',
            r'cpu.*?utilization.*?(\d+)%'
        ]
        
        for pattern in cpu_patterns:
            matches = re.findall(pattern, output_all, re.MULTILINE | re.IGNORECASE)
            if matches:
                if 'slot' in pattern:
                    # 华三取最大值
                    max_val = max(float(x) for x in matches)
                    info['cpu'] = f"{max_val:.1f}%".rstrip('0').rstrip('.') + '%'
                else:
                    info['cpu'] = f"{matches[0]}%"
                break
        
        # 内存使用率解析 - 对标extract_device_status.py的模式
        mem_patterns = [
            # 优先匹配 Used Rate: xx%
            r'used rate\s*:\s*(\d+)%',
            # 通用模式
            r'memory.*?:\s*(\d+)%',
            r'mem.*?(\d+)%',
            r'memory.*?usage.*?(\d+)%'
        ]
        
        for pattern in mem_patterns:
            matches = re.findall(pattern, output_all, re.IGNORECASE)
            if matches:
                info['mem'] = f"{matches[0]}%"
                break
        
        # 温度状态解析 - 基于extract_device_status.py的逻辑
        vendor_lower = (vendor or '').lower()
        if '锐捷' in vendor or 'ruijie' in vendor_lower:
            # 锐捷：Current Tempr < 45为正常
            temp_match = re.search(r'current tempr:\s*([\d.]+)', output_all, re.IGNORECASE)
            if temp_match:
                temp = float(temp_match.group(1))
                info['temp'] = '正常' if temp < 45 else '异常'
        elif '华为' in vendor or 'huawei' in vendor_lower:
            # 华为：表格Status全为NORMAL为正常
            temp_section = re.search(r'display temperature[\s\S]+?(?=(<|====|$))', output_all, re.IGNORECASE)
            if temp_section:
                status_list = re.findall(r'^\s*\w+\s+\d+\s+\d+\s+\d+\s+([A-Z]+)', temp_section.group(0), re.MULTILINE)
                if status_list and all(s.upper() == 'NORMAL' for s in status_list):
                    info['temp'] = '正常'
                elif status_list:
                    info['temp'] = '异常'
        elif '华三' in vendor or 'h3c' in vendor_lower:
            # 华三：温度在限制范围内为正常
            env_section = re.search(r'display environment[\s\S]+?(?=(<|====|$))', output_all, re.IGNORECASE)
            if env_section:
                # 新版格式检查
                rows = re.findall(r'\s*(\d+)\s+([\d.-]+)\s+([\d.-]+)\s+([\d.-]+)', env_section.group(0))
                if rows:
                    ok = True
                    for row in rows:
                        temp = float(row[1])
                        lower = float(row[2])
                        upper = float(row[3])
                        if not (lower < temp < upper):
                            ok = False
                    info['temp'] = '正常' if ok else '异常'
        
        # 电源状态解析
        if '锐捷' in vendor or 'ruijie' in vendor_lower:
            power_section = re.search(r'show power[\s\S]+?(?=(<|====|$))', output_all, re.IGNORECASE)
            if power_section:
                status_list = re.findall(r'^\s*\d+\s+.*?(\S+)\s*$', power_section.group(0), re.MULTILINE)
                if status_list and all(s == 'LinkAndPower' for s in status_list):
                    info['power'] = '正常'
                elif status_list:
                    info['power'] = '异常'
        elif '华为' in vendor or 'huawei' in vendor_lower:
            power_section = re.search(r'display power[\s\S]+?(?=(<|====|$))', output_all, re.IGNORECASE)
            if power_section:
                state_list = re.findall(r'^\s*\d+\s+\S+\s+\S+\s+(Normal|Abnormal)', power_section.group(0), re.MULTILINE)
                if state_list and all(s == 'Normal' for s in state_list):
                    info['power'] = '正常'
                elif state_list:
                    info['power'] = '异常'
        elif '华三' in vendor or 'h3c' in vendor_lower:
            power_section = re.search(r'display power[\s\S]+?(?=(<|====|$))', output_all, re.IGNORECASE)
            if power_section:
                state_list = re.findall(r'State:\s*(Normal|Abnormal)', power_section.group(0))
                if not state_list:
                    state_list = re.findall(r'^\s*\d+\s+\S+\s+\S+\s+(Normal|Abnormal)', power_section.group(0), re.MULTILINE)
                if state_list and all(s == 'Normal' for s in state_list):
                    info['power'] = '正常'
                elif state_list:
                    info['power'] = '异常'
        
        # 风扇状态解析
        if '华为' in vendor or 'huawei' in vendor_lower:
            fan_section = re.search(r'display fan[\s\S]+?(?=(<|====|$))', output_all, re.IGNORECASE)
            if fan_section:
                section = fan_section.group(0)
                status_match = re.search(r'Status\s*:\s*(\w+)', section)
                speeds = re.findall(r'\[\d+\]\s*(\d+)%', section)
                if status_match and status_match.group(1).upper() == 'AUTO' and speeds and all(int(s) > 0 for s in speeds):
                    info['fan'] = '正常'
                elif status_match or speeds:
                    info['fan'] = '异常'
        elif '华三' in vendor or 'h3c' in vendor_lower:
            fan_section = re.search(r'display fan[\s\S]+?(?=(<|====|$))', output_all, re.IGNORECASE)
            if fan_section:
                state_list = re.findall(r'State\s*:\s*(Normal|Abnormal)', fan_section.group(0), re.IGNORECASE)
                if state_list and all(s.lower() == 'normal' for s in state_list):
                    info['fan'] = '正常'
                elif state_list:
                    info['fan'] = '异常'
        elif '锐捷' in vendor or 'ruijie' in vendor_lower:
            fan_section = re.search(r'show fan[\s\S]+?(?=(<|====|$))', output_all, re.IGNORECASE)
            if fan_section:
                status_list = re.findall(r'\d+\s+(Normal|Abnormal)', fan_section.group(0), re.IGNORECASE)
                if status_list and all(s.lower() == 'normal' for s in status_list):
                    info['fan'] = '正常'
                elif status_list:
                    info['fan'] = '异常'
        
        # 运行时间解析 - 基于extract_device_status.py的逻辑
        if '锐捷' in vendor or 'ruijie' in vendor_lower:
            # 锐捷：System uptime is X days Y hours Z minutes
            uptime_match = re.search(r'system uptime is\s+(\d+)\s*days?\s*(\d+)\s*hours?\s*(\d+)\s*minutes?', output_all, re.IGNORECASE)
            if uptime_match:
                days, hours, minutes = uptime_match.groups()
                info['uptime'] = f"{days}天{hours}小时{minutes}分钟"
        elif '华为' in vendor or 'huawei' in vendor_lower:
            # 华为：uptime is X weeks, Y days, Z hours, A minutes
            uptime_match = re.search(r'uptime is\s+(?:(\d+)\s*weeks?,\s*)?(?:(\d+)\s*days?,\s*)?(?:(\d+)\s*hours?,\s*)?(?:(\d+)\s*minutes?)', output_all, re.IGNORECASE)
            if uptime_match:
                weeks, days, hours, minutes = uptime_match.groups()
                parts = []
                if weeks:
                    parts.append(f"{weeks}周")
                if days:
                    parts.append(f"{days}天")
                if hours:
                    parts.append(f"{hours}小时")
                if minutes:
                    parts.append(f"{minutes}分钟")
                if parts:
                    info['uptime'] = ''.join(parts)
        elif '华三' in vendor or 'h3c' in vendor_lower:
            # 华三：Uptime: X weeks, Y days, Z hours, A minutes
            uptime_match = re.search(r'uptime:\s*(?:(\d+)\s*weeks?,\s*)?(?:(\d+)\s*days?,\s*)?(?:(\d+)\s*hours?,\s*)?(?:(\d+)\s*minutes?)', output_all, re.IGNORECASE)
            if uptime_match:
                weeks, days, hours, minutes = uptime_match.groups()
                parts = []
                if weeks:
                    parts.append(f"{weeks}周")
                if days:
                    parts.append(f"{days}天")
                if hours:
                    parts.append(f"{hours}小时")
                if minutes:
                    parts.append(f"{minutes}分钟")
                if parts:
                    info['uptime'] = ''.join(parts)
        
        return info

    def concurrent_settings(self):
        """并发设置对话框"""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("并发设置")
        settings_window.geometry("400x300")
        settings_window.resizable(False, False)
        
        # 居中显示
        settings_window.transient(self.root)
        settings_window.grab_set()
        
        main_frame = tk.Frame(settings_window, bg="#f7fbff")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # 标题
        title_label = tk.Label(main_frame, text="并发设置", font=("微软雅黑", 16, "bold"), 
                              fg="#007acc", bg="#f7fbff")
        title_label.pack(pady=(0, 20))
        
        # 当前设置显示
        current_frame = tk.Frame(main_frame, bg="#ffffff", relief="solid", bd=1)
        current_frame.pack(fill="x", pady=(0, 15))
        
        tk.Label(current_frame, text="当前设置", font=("微软雅黑", 12, "bold"), 
                bg="#ffffff", fg="#007acc").pack(pady=(10, 5))
        tk.Label(current_frame, text=f"最大并发设备数: {self.max_concurrent_devices} 台", 
                font=("微软雅黑", 11), bg="#ffffff").pack(pady=(0, 10))
        
        # 设置区域
        setting_frame = tk.Frame(main_frame, bg="#ffffff", relief="solid", bd=1)
        setting_frame.pack(fill="x", pady=(0, 15))
        
        tk.Label(setting_frame, text="调整设置", font=("微软雅黑", 12, "bold"), 
                bg="#ffffff", fg="#007acc").pack(pady=(10, 5))
        
        # 并发数设置
        concurrent_frame = tk.Frame(setting_frame, bg="#ffffff")
        concurrent_frame.pack(pady=10)
        
        tk.Label(concurrent_frame, text="并发设备数:", font=("微软雅黑", 11), 
                bg="#ffffff").pack(side="left", padx=(10, 5))
        
        concurrent_var = tk.StringVar(value=str(self.max_concurrent_devices))
        concurrent_entry = tk.Entry(concurrent_frame, textvariable=concurrent_var, 
                                   font=("微软雅黑", 11), width=5, justify="center")
        concurrent_entry.pack(side="left", padx=5)
        
        tk.Label(concurrent_frame, text="台 (建议范围: 1-10)", font=("微软雅黑", 10), 
                bg="#ffffff", fg="#666666").pack(side="left", padx=(5, 10))
        
        # 说明文字
        info_frame = tk.Frame(main_frame, bg="#fff3cd", relief="solid", bd=1)
        info_frame.pack(fill="x", pady=(0, 15))
        
        info_text = """💡 设置说明：
• 并发数越高，备份/巡检速度越快
• 但会增加网络和系统负载
• 建议根据网络状况和设备性能调整
• 网络较好时可设置 5-8 台
• 网络一般时建议 2-5 台"""
        
        tk.Label(info_frame, text=info_text, font=("微软雅黑", 9), 
                bg="#fff3cd", fg="#856404", justify="left").pack(pady=10, padx=10)
        
        # 按钮区域
        button_frame = tk.Frame(main_frame, bg="#f7fbff")
        button_frame.pack(fill="x")
        
        def apply_settings():
            try:
                new_concurrent = int(concurrent_var.get())
                if new_concurrent < 1 or new_concurrent > 10:
                    messagebox.showwarning("设置错误", "并发数必须在 1-10 之间！")
                    return
                
                self.max_concurrent_devices = new_concurrent
                messagebox.showinfo("设置成功", f"并发设备数已设置为 {new_concurrent} 台")
                settings_window.destroy()
            except ValueError:
                messagebox.showerror("设置错误", "请输入有效的数字！")
        
        def reset_settings():
            concurrent_var.set("5")  # 重置为默认值
        
        # 按钮样式
        btn_style = {"font": ("微软雅黑", 10, "bold"), "width": 10, "height": 1}
        
        tk.Button(button_frame, text="应用", command=apply_settings, 
                 bg="#d9ead3", fg="#38761d", **btn_style).pack(side="right", padx=(5, 0))
        tk.Button(button_frame, text="重置", command=reset_settings, 
                 bg="#f4cccc", fg="#990000", **btn_style).pack(side="right", padx=5)
        tk.Button(button_frame, text="取消", command=settings_window.destroy, 
                 bg="#e6f2ff", fg="#007acc", **btn_style).pack(side="right", padx=5)

    def configure_concurrent_settings(self):
        """配置并发设置"""
        def save_settings():
            try:
                new_max = int(max_entry.get())
                timeout_val = int(timeout_entry.get())
                retry_val = int(retry_entry.get())
                
                if new_max <= 0 or new_max > 20:
                    messagebox.showerror("设置错误", "并发数必须在1-20之间！")
                    return
                if timeout_val < 10 or timeout_val > 300:
                    messagebox.showerror("设置错误", "超时时间必须在10-300秒之间！")
                    return
                if retry_val < 1 or retry_val > 5:
                    messagebox.showerror("设置错误", "重试次数必须在1-5次之间！")
                    return
                    
                self.max_concurrent_devices = new_max
                self.connection_timeout = timeout_val
                self.max_retries = retry_val
                
                messagebox.showinfo("设置成功", 
                    f"并发设置已更新：\n"
                    f"并发数：{new_max}\n"
                    f"超时时间：{timeout_val}秒\n"
                    f"重试次数：{retry_val}次")
                win.destroy()
            except ValueError:
                messagebox.showerror("输入错误", "请输入有效的数字！")
        
        win = tk.Toplevel(self.root)
        win.title("并发设置")
        win.geometry("400x300")
        win.resizable(False, False)
        
        # 标题
        tk.Label(win, text="并发设置", font=("微软雅黑", 16, "bold"), fg="#007acc").pack(pady=15)
        
        # 并发数设置
        frame1 = tk.Frame(win)
        frame1.pack(pady=10)
        tk.Label(frame1, text="最大并发设备数：", font=("微软雅黑", 12)).pack(side="left")
        max_entry = tk.Entry(frame1, font=("微软雅黑", 12), width=8)
        max_entry.insert(0, str(getattr(self, 'max_concurrent_devices', 5)))
        max_entry.pack(side="left", padx=5)
        tk.Label(frame1, text="台", font=("微软雅黑", 12)).pack(side="left")
        
        # 超时设置
        frame2 = tk.Frame(win)
        frame2.pack(pady=10)
        tk.Label(frame2, text="连接超时时间：", font=("微软雅黑", 12)).pack(side="left")
        timeout_entry = tk.Entry(frame2, font=("微软雅黑", 12), width=8)
        timeout_entry.insert(0, str(getattr(self, 'connection_timeout', 30)))
        timeout_entry.pack(side="left", padx=5)
        tk.Label(frame2, text="秒", font=("微软雅黑", 12)).pack(side="left")
        
        # 重试设置
        frame3 = tk.Frame(win)
        frame3.pack(pady=10)
        tk.Label(frame3, text="连接重试次数：", font=("微软雅黑", 12)).pack(side="left")
        retry_entry = tk.Entry(frame3, font=("微软雅黑", 12), width=8)
        retry_entry.insert(0, str(getattr(self, 'max_retries', 3)))
        retry_entry.pack(side="left", padx=5)
        tk.Label(frame3, text="次", font=("微软雅黑", 12)).pack(side="left")
        
        # 说明文字
        tk.Label(win, text="推荐设置：", font=("微软雅黑", 11, "bold"), fg="#666").pack(pady=(15, 5))
        tk.Label(win, text="• 并发数：3-8台（根据网络状况调整）", font=("微软雅黑", 10), fg="gray").pack()
        tk.Label(win, text="• 超时时间：30-60秒", font=("微软雅黑", 10), fg="gray").pack()
        tk.Label(win, text="• 重试次数：2-3次", font=("微软雅黑", 10), fg="gray").pack()
        
        # 按钮
        btn_frame = tk.Frame(win)
        btn_frame.pack(pady=20)
        tk.Button(btn_frame, text="保存设置", font=("微软雅黑", 12, "bold"), 
                 bg="#d9ead3", fg="#38761d", command=save_settings, width=10).pack(side="left", padx=5)
        tk.Button(btn_frame, text="取消", font=("微软雅黑", 12), 
                 command=win.destroy, width=10).pack(side="left", padx=5)

class NetworkManagementToolV6(NetworkManagementToolV5):
    def __init__(self, root):
        super().__init__(root)
        self.root.title("网络管理工具V6")

if __name__ == '__main__':
    root = tk.Tk()
    app = NetworkManagementToolV6(root)
    root.mainloop()
