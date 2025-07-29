#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
设备状态提取模块 - extract_device_status.py
用于从设备巡检日志中解析CPU、内存、温度、电源、风扇等状态信息
支持华为、华三、思科、锐捷等主流厂商设备
"""

import re
import datetime

def detect_vendor(output):
    """
    根据输出内容检测设备厂商
    """
    output_lower = output.lower()
    
    # 华为设备特征
    if any(keyword in output_lower for keyword in [
        'huawei', '华为', 'vrp', 'display version', 'quidway', 's5700', 's6700'
    ]):
        return 'huawei'
    
    # 华三设备特征  
    if any(keyword in output_lower for keyword in [
        'h3c', '华三', 'comware', 'hp', 'hewlett packard', '3com'
    ]):
        return 'h3c'
    
    # 思科设备特征
    if any(keyword in output_lower for keyword in [
        'cisco', 'ios', 'nx-os', 'asa', 'catalyst'
    ]):
        return 'cisco'
    
    # 锐捷设备特征
    if any(keyword in output_lower for keyword in [
        'ruijie', '锐捷', 'rgos', 'switch>'
    ]):
        return 'ruijie'
    
    # 默认返回华为（最常见）
    return 'huawei'

def extract_info(output, vendor):
    """
    根据厂商类型从输出中提取设备状态信息
    返回字典包含：cpu, mem, temp, power, fan, uptime
    """
    info = {
        'cpu': '',
        'mem': '',
        'temp': '',
        'power': '',
        'fan': '',
        'uptime': ''
    }
    
    vendor = vendor.lower()
    
    # 根据厂商调用相应的解析函数
    if vendor == 'huawei':
        return extract_huawei_info(output, info)
    elif vendor == 'h3c':
        return extract_h3c_info(output, info)
    elif vendor == 'cisco':
        return extract_cisco_info(output, info)
    elif vendor == 'ruijie':
        return extract_ruijie_info(output, info)
    else:
        # 默认尝试华为解析
        return extract_huawei_info(output, info)

def extract_huawei_info(output, info):
    """提取华为设备状态信息"""
    
    # CPU使用率解析
    cpu_patterns = [
        r'cpu usage:\s*(\d+)%',
        r'cpu utilization:\s*(\d+)%',
        r'cpu\s+usage\s+in\s+last\s+.*?:\s*(\d+)%'
    ]
    for pattern in cpu_patterns:
        matches = re.findall(pattern, output, re.IGNORECASE)
        if matches:
            info['cpu'] = f"{matches[0]}%"
            break
    
    # 内存使用率解析
    mem_patterns = [
        r'memory usage:\s*(\d+)%',
        r'memory utilization:\s*(\d+)%',
        r'used\s*:\s*\d+.*?\((\d+)%\)'
    ]
    for pattern in mem_patterns:
        matches = re.findall(pattern, output, re.IGNORECASE)
        if matches:
            info['mem'] = f"{matches[0]}%"
            break
    
    # 温度状态解析
    temp_section = re.search(r'display temperature[\s\S]+?(?=<|====|$)', output, re.IGNORECASE)
    if temp_section:
        status_list = re.findall(r'^\s*\w+\s+\d+\s+\d+\s+\d+\s+([A-Z]+)', temp_section.group(0), re.MULTILINE)
        if status_list and all(s.upper() == 'NORMAL' for s in status_list):
            info['temp'] = '正常'
        elif status_list:
            info['temp'] = '异常'
    
    # 电源状态解析
    power_section = re.search(r'display power[\s\S]+?(?=<|====|$)', output, re.IGNORECASE)
    if power_section:
        state_list = re.findall(r'^\s*\d+\s+\S+\s+\S+\s+(Normal|Abnormal)', power_section.group(0), re.MULTILINE)
        if state_list and all(s == 'Normal' for s in state_list):
            info['power'] = '正常'
        elif state_list:
            info['power'] = '异常'
    
    # 风扇状态解析
    fan_section = re.search(r'display fan[\s\S]+?(?=<|====|$)', output, re.IGNORECASE)
    if fan_section:
        section = fan_section.group(0)
        status_match = re.search(r'Status\s*:\s*(\w+)', section)
        speeds = re.findall(r'\[\d+\]\s*(\d+)%', section)
        if status_match and status_match.group(1).upper() == 'AUTO' and speeds and all(int(s) > 0 for s in speeds):
            info['fan'] = '正常'
        elif status_match or speeds:
            info['fan'] = '异常'
    
    # 运行时间解析
    uptime_match = re.search(r'uptime is\s+(?:(\d+)\s*weeks?,\s*)?(?:(\d+)\s*days?,\s*)?(?:(\d+)\s*hours?,\s*)?(?:(\d+)\s*minutes?)', output, re.IGNORECASE)
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

def extract_h3c_info(output, info):
    """提取华三设备状态信息"""
    
    # CPU使用率解析 - 华三专用
    cpu_patterns = [
        r'slot \d+ cpu usage:[^\n]*\n(?:.*\n)*?\s*([\d.]+)% in last 5 minutes',
        r'cpu utilization:\s*(\d+)%',
        r'cpu usage:\s*(\d+)%'
    ]
    
    for pattern in cpu_patterns:
        matches = re.findall(pattern, output, re.MULTILINE | re.IGNORECASE)
        if matches:
            if 'slot' in pattern:
                # 华三取最大值
                max_val = max(float(x) for x in matches)
                info['cpu'] = f"{max_val:.1f}%".rstrip('0').rstrip('.') + '%'
            else:
                info['cpu'] = f"{matches[0]}%"
            break
    
    # 内存使用率解析
    mem_patterns = [
        r'used rate\s*:\s*(\d+)%',
        r'memory usage:\s*(\d+)%',
        r'mem.*?(\d+)%'
    ]
    for pattern in mem_patterns:
        matches = re.findall(pattern, output, re.IGNORECASE)
        if matches:
            info['mem'] = f"{matches[0]}%"
            break
    
    # 温度状态解析
    env_section = re.search(r'display environment[\s\S]+?(?=<|====|$)', output, re.IGNORECASE)
    if env_section:
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
    power_section = re.search(r'display power[\s\S]+?(?=<|====|$)', output, re.IGNORECASE)
    if power_section:
        state_list = re.findall(r'State:\s*(Normal|Abnormal)', power_section.group(0))
        if not state_list:
            state_list = re.findall(r'^\s*\d+\s+\S+\s+\S+\s+(Normal|Abnormal)', power_section.group(0), re.MULTILINE)
        if state_list and all(s == 'Normal' for s in state_list):
            info['power'] = '正常'
        elif state_list:
            info['power'] = '异常'
    
    # 风扇状态解析
    fan_section = re.search(r'display fan[\s\S]+?(?=<|====|$)', output, re.IGNORECASE)
    if fan_section:
        state_list = re.findall(r'State\s*:\s*(Normal|Abnormal)', fan_section.group(0), re.IGNORECASE)
        if state_list and all(s.lower() == 'normal' for s in state_list):
            info['fan'] = '正常'
        elif state_list:
            info['fan'] = '异常'
    
    # 运行时间解析
    uptime_match = re.search(r'uptime:\s*(?:(\d+)\s*weeks?,\s*)?(?:(\d+)\s*days?,\s*)?(?:(\d+)\s*hours?,\s*)?(?:(\d+)\s*minutes?)', output, re.IGNORECASE)
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

def extract_cisco_info(output, info):
    """提取思科设备状态信息"""
    
    # CPU使用率解析
    cpu_patterns = [
        r'cpu utilization.*?(\d+)%',
        r'five seconds:\s*(\d+)%',
        r'one minute:\s*(\d+)%'
    ]
    for pattern in cpu_patterns:
        matches = re.findall(pattern, output, re.IGNORECASE)
        if matches:
            info['cpu'] = f"{matches[0]}%"
            break
    
    # 内存使用率解析
    mem_patterns = [
        r'processor pool total:\s*(\d+).*?used:\s*(\d+)',
        r'memory usage:\s*(\d+)%'
    ]
    for pattern in mem_patterns:
        matches = re.findall(pattern, output, re.IGNORECASE)
        if matches:
            if len(matches[0]) == 2:  # total and used format
                total, used = matches[0]
                percentage = int((int(used) / int(total)) * 100)
                info['mem'] = f"{percentage}%"
            else:
                info['mem'] = f"{matches[0]}%"
            break
    
    # 温度、电源、风扇状态解析（思科格式）
    if 'environment' in output.lower():
        if 'ok' in output.lower() and 'fail' not in output.lower():
            info['temp'] = '正常'
            info['power'] = '正常'
            info['fan'] = '正常'
        else:
            info['temp'] = '异常'
            info['power'] = '异常'
            info['fan'] = '异常'
    
    # 运行时间解析
    uptime_match = re.search(r'uptime is\s+(?:(\d+)\s*weeks?,\s*)?(?:(\d+)\s*days?,\s*)?(?:(\d+)\s*hours?,\s*)?(?:(\d+)\s*minutes?)', output, re.IGNORECASE)
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

def extract_ruijie_info(output, info):
    """提取锐捷设备状态信息"""
    
    # CPU使用率解析
    cpu_match = re.search(r'cpu utilization in five minutes:\s*([\d.]+)%', output, re.IGNORECASE)
    if cpu_match:
        info['cpu'] = f"{cpu_match.group(1)}%"
    
    # 内存使用率（锐捷通常不直接显示百分比）
    mem_patterns = [
        r'memory usage:\s*(\d+)%',
        r'mem.*?(\d+)%'
    ]
    for pattern in mem_patterns:
        matches = re.findall(pattern, output, re.IGNORECASE)
        if matches:
            info['mem'] = f"{matches[0]}%"
            break
    
    # 温度状态解析 - 锐捷专用
    temp_match = re.search(r'current tempr:\s*([\d.]+)', output, re.IGNORECASE)
    if temp_match:
        temp = float(temp_match.group(1))
        info['temp'] = '正常' if temp < 45 else '异常'
    
    # 电源状态解析
    power_section = re.search(r'show power[\s\S]+?(?=<|====|$)', output, re.IGNORECASE)
    if power_section:
        status_list = re.findall(r'^\s*\d+\s+.*?(\S+)\s*$', power_section.group(0), re.MULTILINE)
        if status_list and all(s == 'LinkAndPower' for s in status_list):
            info['power'] = '正常'
        elif status_list:
            info['power'] = '异常'
    
    # 风扇状态解析
    fan_section = re.search(r'show fan[\s\S]+?(?=<|====|$)', output, re.IGNORECASE)
    if fan_section:
        status_list = re.findall(r'\d+\s+(Normal|Abnormal)', fan_section.group(0), re.IGNORECASE)
        if status_list and all(s.lower() == 'normal' for s in status_list):
            info['fan'] = '正常'
        elif status_list:
            info['fan'] = '异常'
    
    # 运行时间解析
    uptime_match = re.search(r'system uptime is\s+(\d+)\s*days?\s*(\d+)\s*hours?\s*(\d+)\s*minutes?', output, re.IGNORECASE)
    if uptime_match:
        days, hours, minutes = uptime_match.groups()
        info['uptime'] = f"{days}天{hours}小时{minutes}分钟"
    
    return info

def parse_log_files(log_dir):
    """
    解析日志目录中的所有日志文件，返回设备状态列表
    """
    import os
    import glob
    
    results = []
    
    # 查找所有日志文件
    log_patterns = [
        os.path.join(log_dir, "*.log"),
        os.path.join(log_dir, "*.txt")
    ]
    
    log_files = []
    for pattern in log_patterns:
        log_files.extend(glob.glob(pattern))
    
    for log_file in log_files:
        try:
            # 从文件名提取设备信息
            filename = os.path.basename(log_file)
            device_name = filename.split('_')[0] if '_' in filename else filename.split('.')[0]
            
            # 读取日志内容
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # 检测厂商
            vendor = detect_vendor(content)
            
            # 提取状态信息
            info = extract_info(content, vendor)
            
            # 组装结果
            result = {
                '设备名': device_name,
                '时间': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                '厂商': vendor.upper(),
                'CPU使用率': info.get('cpu', 'N/A'),
                '内存使用率': info.get('mem', 'N/A'),
                '温度状态': info.get('temp', 'N/A'),
                '电源状态': info.get('power', 'N/A'),
                '风扇状态': info.get('fan', 'N/A'),
                '运行时间': info.get('uptime', 'N/A')
            }
            
            results.append(result)
            
        except Exception as e:
            print(f"解析文件 {log_file} 时出错: {e}")
            continue
    
    return results

if __name__ == '__main__':
    # 测试代码
    test_output = """
    display cpu-usage
    CPU usage in the last 5 seconds: 10%

    display memory-usage  
    Memory usage: 45%

    display temperature
    Slot    Current(C)  Lower(C)   Upper(C)   Status
    1       25          0          70         NORMAL
    """
    
    vendor = detect_vendor(test_output)
    info = extract_info(test_output, vendor)
    
    print(f"检测厂商: {vendor}")
    print(f"设备状态: {info}")