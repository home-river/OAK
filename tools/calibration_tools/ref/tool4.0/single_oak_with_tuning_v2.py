from pathlib import Path
import sys
import cv2
import depthai as dai
import numpy as np
import time
import threading
import tkinter as tk
from tkinter import ttk

# 添加reference目录到路径，以便导入模块
sys.path.append(str(Path(__file__).parent.parent / 'reference'))

from calculate_module import FilteredCalculateModule, KinematicCalibration
from can_module import CANCommunicator

"""
单OAK设备检测脚本 - 2.0版本 GUI调参界面
功能：
1. 单OAK设备检测（无需设备ID识别）
2. Tkinter GUI窗口，使用输入框和+-控件实时调整坐标变换参数
3. 显示原始坐标和变换后坐标
4. 可选CAN通信功能
5. 复用现有calculate_module和can_module
"""

class ParameterControlGUI:
    """参数控制GUI类 - 使用tkinter实现输入框和+-控件"""
    
    def __init__(self, initial_params, update_callback):
        self.params = initial_params.copy()
        self.update_callback = update_callback
        
        # 参数范围定义
        self.param_ranges = {
            'Tx': {'min': -3000.0, 'max': 1000.0, 'step': 0.1},
            'Ty': {'min': -2000.0, 'max': 1000.0, 'step': 0.1}, 
            'Tz': {'min': 0.0, 'max': 3000.0, 'step': 0.1},
            'Ry': {'min': -90.0, 'max': 90.0, 'step': 0.1},
            'Rz': {'min': -90.0, 'max': 90.0, 'step': 0.1}
        }
        
        self.setup_gui()
        
    def setup_gui(self):
        """设置GUI界面"""
        self.root = tk.Tk()
        self.root.title("坐标变换参数调整 - 2.0版本")
        self.root.geometry("400x350")
        self.root.resizable(False, False)
        
        # 设置窗口始终在最前面
        self.root.attributes('-topmost', True)
        
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 标题
        title_label = ttk.Label(main_frame, text="坐标变换参数", font=('Arial', 14, 'bold'))
        title_label.grid(row=0, column=0, columnspan=4, pady=(0, 15))
        
        # 存储输入框引用
        self.entries = {}
        
        # 创建参数控制行
        row = 1
        for param_name, value in self.params.items():
            self.create_parameter_row(main_frame, param_name, value, row)
            row += 1
        
        # 状态显示区域
        status_frame = ttk.LabelFrame(main_frame, text="当前参数值", padding="5")
        status_frame.grid(row=row, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=(15, 0))
        
        self.status_label = ttk.Label(status_frame, text="", font=('Courier', 9))
        self.status_label.grid(row=0, column=0, sticky=tk.W)
        
        # 控制按钮
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=row+1, column=0, columnspan=4, pady=(10, 0))
        
        ttk.Button(button_frame, text="重置默认值", command=self.reset_defaults).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="应用参数", command=self.apply_params).pack(side=tk.LEFT)
        
        # 更新状态显示
        self.update_status_display()
        
        # 绑定窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def create_parameter_row(self, parent, param_name, value, row):
        """创建单个参数的控制行"""
        # 参数标签
        label_text = f"{param_name}:"
        if param_name in ['Tx', 'Ty', 'Tz']:
            label_text += " (mm)"
        else:
            label_text += " (°)"
            
        ttk.Label(parent, text=label_text, width=8).grid(row=row, column=0, sticky=tk.W, padx=(0, 5))
        
        # 减少按钮
        ttk.Button(parent, text="-", width=3, 
                  command=lambda p=param_name: self.decrease_param(p)).grid(row=row, column=1, padx=(0, 2))
        
        # 输入框
        entry = ttk.Entry(parent, width=8, justify='center')
        entry.insert(0, str(value))
        entry.bind('<Return>', lambda e, p=param_name: self.on_entry_change(p))
        entry.bind('<FocusOut>', lambda e, p=param_name: self.on_entry_change(p))
        entry.grid(row=row, column=2, padx=2)
        self.entries[param_name] = entry
        
        # 增加按钮
        ttk.Button(parent, text="+", width=3,
                  command=lambda p=param_name: self.increase_param(p)).grid(row=row, column=3, padx=(2, 0))
    
    def decrease_param(self, param_name):
        """减少参数值"""
        current_value = self.get_entry_value(param_name)
        step = self.param_ranges[param_name]['step']
        new_value = current_value - step
        new_value = max(new_value, self.param_ranges[param_name]['min'])
        self.set_entry_value(param_name, new_value)
        self.on_param_change(param_name, new_value)
    
    def increase_param(self, param_name):
        """增加参数值"""
        current_value = self.get_entry_value(param_name)
        step = self.param_ranges[param_name]['step']
        new_value = current_value + step
        new_value = min(new_value, self.param_ranges[param_name]['max'])
        self.set_entry_value(param_name, new_value)
        self.on_param_change(param_name, new_value)
    
    def get_entry_value(self, param_name):
        """获取输入框的值"""
        try:
            return float(self.entries[param_name].get())
        except ValueError:
            return self.params[param_name]  # 返回当前存储的值
    
    def set_entry_value(self, param_name, value):
        """设置输入框的值"""
        entry = self.entries[param_name]
        entry.delete(0, tk.END)
        entry.insert(0, str(value))
    
    def on_entry_change(self, param_name):
        """输入框值改变时的处理"""
        try:
            new_value = float(self.entries[param_name].get())
            # 检查范围
            min_val = self.param_ranges[param_name]['min']
            max_val = self.param_ranges[param_name]['max']
            new_value = max(min_val, min(max_val, new_value))
            
            # 如果值被修正了，更新输入框显示
            if new_value != float(self.entries[param_name].get()):
                self.set_entry_value(param_name, new_value)
            
            self.on_param_change(param_name, new_value)
        except ValueError:
            # 输入无效，恢复原值
            self.set_entry_value(param_name, self.params[param_name])
    
    def on_param_change(self, param_name, new_value):
        """参数改变时的回调"""
        self.params[param_name] = new_value
        self.update_status_display()
        # 调用外部回调函数
        if self.update_callback:
            self.update_callback(self.params.copy())
    
    def update_status_display(self):
        """更新状态显示"""
        status_text = f"Tx={self.params['Tx']:+5.1f}mm  Ty={self.params['Ty']:+5.1f}mm  Tz={self.params['Tz']:5.1f}mm\n"
        status_text += f"Ry={self.params['Ry']:+3.1f}°     Rz={self.params['Rz']:+3.1f}°"
        self.status_label.config(text=status_text)
    
    def reset_defaults(self):
        """重置为默认值"""
        defaults = {
            'Tx': -1500.0,
            'Ty': -760.0,
            'Tz': 1200.0,
            'Ry': 45.0,
            'Rz': -30.0
        }
        
        for param_name, value in defaults.items():
            self.set_entry_value(param_name, value)
            self.params[param_name] = value
        
        self.update_status_display()
        if self.update_callback:
            self.update_callback(self.params.copy())
    
    def apply_params(self):
        """应用所有参数"""
        for param_name in self.params.keys():
            self.on_entry_change(param_name)
    
    def on_closing(self):
        """窗口关闭时的处理"""
        self.root.quit()
    
    def start(self):
        """启动GUI"""
        self.root.mainloop()
    
    def update_from_external(self, new_params):
        """从外部更新参数（用于同步）"""
        for param_name, value in new_params.items():
            if param_name in self.params:
                self.params[param_name] = value
                self.set_entry_value(param_name, value)
        self.update_status_display()
