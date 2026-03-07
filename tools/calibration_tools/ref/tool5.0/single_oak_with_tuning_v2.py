from pathlib import Path
import sys
import cv2
import depthai as dai
import numpy as np
import time
import threading
import tkinter as tk
from tkinter import ttk



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
    
    def __init__(self, initial_params, update_callback, reference_position_callback=None, record_data_callback=None):
        self.params = initial_params.copy()
        self.update_callback = update_callback
        self.reference_position_callback = reference_position_callback
        self.record_data_callback = record_data_callback
        
        # 误差记录相关
        self.reference_position = {'x': 0.0, 'y': 0.0}
        self.record_count = 0
        
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
        self.root.geometry("450x500")  # 增加窗口高度以容纳新控件
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
        status_frame = ttk.Frame(main_frame)
        status_frame.grid(row=row, column=0, columnspan=4, pady=(15, 10), sticky=(tk.W, tk.E))
        
        self.status_label = ttk.Label(status_frame, text="", font=('Courier', 9))
        self.status_label.grid(row=0, column=0, sticky=tk.W)
        
        # 控制按钮
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=row+1, column=0, columnspan=4, pady=(10, 0))
        
        ttk.Button(button_frame, text="重置默认值", command=self.reset_defaults).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="应用参数", command=self.apply_params).pack(side=tk.LEFT)
        
        # 误差记录区域
        if self.reference_position_callback or self.record_data_callback:
            self.create_error_recording_section(main_frame, row+2)
        
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

    def create_error_recording_section(self, parent, start_row):
        """创建误差记录控件区域"""
        # 分隔线
        separator = ttk.Separator(parent, orient='horizontal')
        separator.grid(row=start_row, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=(15, 10))
        
        # 误差记录标题
        error_title = ttk.Label(parent, text="误差记录", font=('Arial', 12, 'bold'))
        error_title.grid(row=start_row+1, column=0, columnspan=4, pady=(0, 10))
        
        # 基准位置设置
        ref_frame = ttk.Frame(parent)
        ref_frame.grid(row=start_row+2, column=0, columnspan=4, pady=(0, 10), sticky=(tk.W, tk.E))
        
        ttk.Label(ref_frame, text="基准位置:").grid(row=0, column=0, sticky=tk.W)
        
        # X坐标输入
        ttk.Label(ref_frame, text="X:").grid(row=0, column=1, padx=(10, 2))
        self.ref_x_entry = ttk.Entry(ref_frame, width=8, justify='center')
        self.ref_x_entry.insert(0, "0.0")
        self.ref_x_entry.bind('<Return>', self.on_reference_change)
        self.ref_x_entry.bind('<FocusOut>', self.on_reference_change)
        self.ref_x_entry.grid(row=0, column=2, padx=2)
        
        # Y坐标输入
        ttk.Label(ref_frame, text="Y:").grid(row=0, column=3, padx=(10, 2))
        self.ref_y_entry = ttk.Entry(ref_frame, width=8, justify='center')
        self.ref_y_entry.insert(0, "0.0")
        self.ref_y_entry.bind('<Return>', self.on_reference_change)
        self.ref_y_entry.bind('<FocusOut>', self.on_reference_change)
        self.ref_y_entry.grid(row=0, column=4, padx=2)
        
        # 基准位置调整按钮
        ttk.Button(ref_frame, text="X-", width=3, command=lambda: self.adjust_reference('x', -10)).grid(row=1, column=1, pady=(5, 0))
        ttk.Button(ref_frame, text="X+", width=3, command=lambda: self.adjust_reference('x', 10)).grid(row=1, column=2, pady=(5, 0))
        ttk.Button(ref_frame, text="Y-", width=3, command=lambda: self.adjust_reference('y', -10)).grid(row=1, column=3, pady=(5, 0))
        ttk.Button(ref_frame, text="Y+", width=3, command=lambda: self.adjust_reference('y', 10)).grid(row=1, column=4, pady=(5, 0))
        
        # 记录按钮和状态
        record_frame = ttk.Frame(parent)
        record_frame.grid(row=start_row+3, column=0, columnspan=4, pady=(10, 0))
        
        self.record_button = ttk.Button(record_frame, text="记录误差数据", command=self.record_error_data)
        self.record_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.record_status_label = ttk.Label(record_frame, text="已记录: 0 条数据")
        self.record_status_label.pack(side=tk.LEFT)
    
    def on_reference_change(self, event=None):
        """基准位置改变时的处理"""
        try:
            ref_x = float(self.ref_x_entry.get())
            ref_y = float(self.ref_y_entry.get())
            self.reference_position = {'x': ref_x, 'y': ref_y}
            if self.reference_position_callback:
                self.reference_position_callback(self.reference_position)
        except ValueError:
            # 输入无效，恢复原值
            self.ref_x_entry.delete(0, tk.END)
            self.ref_x_entry.insert(0, "0.0")
            self.ref_y_entry.delete(0, tk.END)
            self.ref_y_entry.insert(0, "0.0")
    
    def adjust_reference(self, axis, delta):
        """调整基准位置"""
        if axis == 'x':
            current_value = float(self.ref_x_entry.get())
            new_value = current_value + delta
            self.ref_x_entry.delete(0, tk.END)
            self.ref_x_entry.insert(0, str(new_value))
        elif axis == 'y':
            current_value = float(self.ref_y_entry.get())
            new_value = current_value + delta
            self.ref_y_entry.delete(0, tk.END)
            self.ref_y_entry.insert(0, str(new_value))
        self.on_reference_change()
    
    def record_error_data(self):
        """记录误差数据"""
        if self.record_data_callback:
            self.record_data_callback()
            self.record_count += 1
            self.update_record_status(self.record_count)
    
    def update_record_status(self, count):
        """更新记录状态显示"""
        self.record_count = count
        if hasattr(self, 'record_status_label'):
            self.record_status_label.config(text=f"已记录: {count} 条数据")
