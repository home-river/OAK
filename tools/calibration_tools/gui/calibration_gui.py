"""
校准参数调整GUI

CalibrationGUI 类负责：
- 提供参数调整界面
- 与 TransformParamManager 通信
- 显示实时状态反馈
- 记录误差数据
"""

import tkinter as tk
from tkinter import ttk
from threading import Thread
from typing import Optional, Dict
import logging


class CalibrationGUI:
    """
    校准参数调整GUI
    
    职责：
    - 提供参数调整界面
    - 与 TransformParamManager 通信
    - 显示实时状态反馈
    - 记录误差数据
    """
    
    def __init__(
        self,
        param_manager,
        error_recorder
    ):
        """
        初始化GUI
        
        Args:
            param_manager: TransformParamManager 实例
            error_recorder: ErrorRecorder 实例
        
        Raises:
            ValueError: 如果不是单设备运行模式
        """
        self.param_manager = param_manager
        self.error_recorder = error_recorder
        self.logger = logging.getLogger(__name__)
        
        # 获取当前设备mxid（验证单设备运行模式）
        try:
            self.mxid = self.param_manager.get_current_mxid()
            self.logger.info(f"GUI 初始化: 设备 mxid = {self.mxid}")
        except ValueError as e:
            self.logger.error(f"GUI 初始化失败: {e}")
            raise
        
        # 获取初始参数值
        initial_params = self.param_manager.get_params_snapshot(self.mxid)
        if initial_params is None:
            raise ValueError(f"无法获取设备 {self.mxid} 的初始参数")
        
        # 创建GUI窗口
        self.root = tk.Tk()
        self.root.title(f"校准工具 - 设备: {self.mxid}")
        self.root.geometry("500x600")
        
        # 参数变量字典
        self.params: Dict[str, tk.DoubleVar] = {}
        
        # 基准位置变量
        self.ref_params: Dict[str, tk.DoubleVar] = {}
        
        # 记录计数
        self.record_count = 0
        self.record_count_label: Optional[ttk.Label] = None
        
        # 状态标签
        self.status_label: Optional[ttk.Label] = None
        
        # 初始化UI组件
        self._create_widgets()
        
        # 设置初始参数值
        self.params["tx"].set(initial_params['tx'])
        self.params["ty"].set(initial_params['ty'])
        self.params["tz"].set(initial_params['tz'])
        self.params["pitch"].set(initial_params['pitch'])
        self.params["yaw"].set(initial_params['yaw'])
        
        self.logger.info("GUI 初始化完成")
    
    def _create_widgets(self):
        """创建UI组件"""
        # 设备信息显示
        info_frame = ttk.LabelFrame(self.root, text="设备信息", padding=10)
        info_frame.pack(padx=10, pady=5, fill="x")
        
        ttk.Label(
            info_frame,
            text=f"设备ID: {self.mxid}",
            font=("Arial", 10)
        ).pack()
        
        # 参数调整区域
        params_frame = ttk.LabelFrame(
            self.root,
            text="坐标变换参数",
            padding=10
        )
        params_frame.pack(padx=10, pady=5, fill="both", expand=True)
        
        # 平移参数（步长1.0mm）
        self._create_param_row(params_frame, "Tx (mm):", "tx", 0, step=1.0)
        self._create_param_row(params_frame, "Ty (mm):", "ty", 1, step=1.0)
        self._create_param_row(params_frame, "Tz (mm):", "tz", 2, step=1.0)
        
        # 旋转参数（步长0.1度）
        self._create_param_row(params_frame, "Pitch (度):", "pitch", 3, step=0.1)
        self._create_param_row(params_frame, "Yaw (度):", "yaw", 4, step=0.1)
        
        # 按钮区域
        button_frame = ttk.Frame(params_frame)
        button_frame.grid(row=5, column=0, columnspan=4, pady=10)
        
        ttk.Button(
            button_frame,
            text="设置参数",
            command=self._on_set_params
        ).pack(side="left", padx=5)
        
        ttk.Button(
            button_frame,
            text="重置为默认",
            command=self._on_reset
        ).pack(side="left", padx=5)
        
        # 误差记录区域
        error_frame = ttk.LabelFrame(
            self.root,
            text="误差记录",
            padding=10
        )
        error_frame.pack(padx=10, pady=5, fill="both", expand=True)
        
        # 基准位置输入
        ref_x_frame = ttk.Frame(error_frame)
        ref_x_frame.pack(fill="x", pady=2)
        ttk.Label(ref_x_frame, text="基准位置 X (mm):", width=20).pack(side="left")
        self.ref_params["ref_x"] = tk.DoubleVar(value=1000.0)
        ttk.Entry(
            ref_x_frame,
            textvariable=self.ref_params["ref_x"],
            width=15
        ).pack(side="left", padx=5)
        
        ref_y_frame = ttk.Frame(error_frame)
        ref_y_frame.pack(fill="x", pady=2)
        ttk.Label(ref_y_frame, text="基准位置 Y (mm):", width=20).pack(side="left")
        self.ref_params["ref_y"] = tk.DoubleVar(value=500.0)
        ttk.Entry(
            ref_y_frame,
            textvariable=self.ref_params["ref_y"],
            width=15
        ).pack(side="left", padx=5)
        
        # 记录按钮
        ttk.Button(
            error_frame,
            text="记录误差",
            command=self._on_record_error
        ).pack(pady=10)
        
        # 记录计数显示
        self.record_count_label = ttk.Label(
            error_frame,
            text=f"已记录: {self.record_count} 条",
            font=("Arial", 10)
        )
        self.record_count_label.pack()
        
        # 状态显示
        self.status_label = ttk.Label(
            self.root,
            text="就绪",
            font=("Arial", 10),
            foreground="blue"
        )
        self.status_label.pack(padx=10, pady=5)
    
    def _create_param_row(
        self,
        parent: ttk.Frame,
        label: str,
        param_name: str,
        row: int,
        step: float
    ):
        """
        创建参数调整行
        
        Args:
            parent: 父容器
            label: 参数标签
            param_name: 参数名称
            row: 行号
            step: 步长（平移参数1.0mm，旋转参数0.1度）
        """
        # 标签
        ttk.Label(parent, text=label, width=15).grid(
            row=row, column=0, padx=5, pady=5, sticky="w"
        )
        
        # [-] 按钮
        ttk.Button(
            parent,
            text="[-]",
            width=5,
            command=lambda: self._adjust_param(param_name, -step)
        ).grid(row=row, column=1, padx=2)
        
        # 输入框
        self.params[param_name] = tk.DoubleVar(value=0.0)
        entry = ttk.Entry(
            parent,
            textvariable=self.params[param_name],
            width=12,
            justify="center"
        )
        entry.grid(row=row, column=2, padx=5)
        
        # [+] 按钮
        ttk.Button(
            parent,
            text="[+]",
            width=5,
            command=lambda: self._adjust_param(param_name, step)
        ).grid(row=row, column=3, padx=2)
    
    def _adjust_param(self, param_name: str, delta: float):
        """
        调整参数值（微调）
        
        Args:
            param_name: 参数名称
            delta: 调整量（正数增加，负数减少）
        """
        current_value = self.params[param_name].get()
        new_value = current_value + delta
        self.params[param_name].set(new_value)
    
    def _on_set_params(self):
        """设置参数按钮回调"""
        try:
            # 获取参数值
            tx = float(self.params["tx"].get())
            ty = float(self.params["ty"].get())
            tz = float(self.params["tz"].get())
            pitch = float(self.params["pitch"].get())
            yaw = float(self.params["yaw"].get())
            
            self.logger.info(
                f"设置参数: tx={tx}, ty={ty}, tz={tz}, "
                f"pitch={pitch}, yaw={yaw}"
            )
            
            # 调用 TransformParamManager 更新
            success = self.param_manager.update_params(
                self.mxid, tx, ty, tz, pitch, yaw
            )
            
            if success:
                self.status_label.config(
                    text="参数更新成功",
                    foreground="green"
                )
                self.logger.info("参数更新成功")
            else:
                self.status_label.config(
                    text="参数更新失败",
                    foreground="red"
                )
                self.logger.error("参数更新失败")
        except ValueError as e:
            self.status_label.config(
                text=f"输入错误: {e}",
                foreground="red"
            )
            self.logger.error(f"参数输入错误: {e}")
        except Exception as e:
            self.status_label.config(
                text=f"错误: {e}",
                foreground="red"
            )
            self.logger.error(f"设置参数时发生错误: {e}", exc_info=True)
    
    def _on_reset(self):
        """重置为默认按钮回调"""
        try:
            self.logger.info("重置参数为默认值")
            
            # 调用 TransformParamManager 重置到启动时的初始参数
            success = self.param_manager.reset_to_default(self.mxid)
            
            if success:
                # 更新GUI显示的参数值
                params = self.param_manager.get_params_snapshot(self.mxid)
                if params:
                    self.params["tx"].set(params['tx'])
                    self.params["ty"].set(params['ty'])
                    self.params["tz"].set(params['tz'])
                    self.params["pitch"].set(params['pitch'])
                    self.params["yaw"].set(params['yaw'])
                
                self.status_label.config(
                    text="已重置为启动时的初始参数",
                    foreground="green"
                )
                self.logger.info("参数重置成功")
            else:
                self.status_label.config(
                    text="重置失败",
                    foreground="red"
                )
                self.logger.error("参数重置失败")
        except Exception as e:
            self.status_label.config(
                text=f"错误: {e}",
                foreground="red"
            )
            self.logger.error(f"重置参数时发生错误: {e}", exc_info=True)
    
    def _on_record_error(self):
        """记录误差按钮回调"""
        try:
            # 直接从输入框读取基准位置
            ref_x = float(self.ref_params["ref_x"].get())
            ref_y = float(self.ref_params["ref_y"].get())
            
            self.logger.info(f"记录误差: 基准位置 X={ref_x}, Y={ref_y}")
            
            # 调用 ErrorRecorder 记录误差，传入基准位置
            success = self.error_recorder.record_error(ref_x, ref_y)
            
            if success:
                # 更新记录计数
                self.record_count += 1
                self.record_count_label.config(
                    text=f"已记录: {self.record_count} 条"
                )
                self.status_label.config(
                    text="误差记录成功",
                    foreground="green"
                )
                self.logger.info(f"误差记录成功 (#{self.record_count})")
            else:
                self.status_label.config(
                    text="误差记录失败（未检测到目标）",
                    foreground="red"
                )
                self.logger.warning("误差记录失败：未检测到目标")
        except ValueError as e:
            self.status_label.config(
                text=f"输入错误: {e}",
                foreground="red"
            )
            self.logger.error(f"基准位置输入错误: {e}")
        except Exception as e:
            self.status_label.config(
                text=f"错误: {e}",
                foreground="red"
            )
            self.logger.error(f"记录误差时发生错误: {e}", exc_info=True)
    
    def run(self):
        """启动GUI主循环（在独立线程中运行）"""
        self.logger.info("启动 GUI 主循环")
        self.root.mainloop()
    
    @staticmethod
    def start_in_thread(param_manager, error_recorder):
        """
        在独立线程中启动GUI
        
        Args:
            param_manager: TransformParamManager 实例
            error_recorder: ErrorRecorder 实例
        
        Returns:
            Thread: GUI 线程对象
        """
        def run_gui():
            try:
                gui = CalibrationGUI(param_manager, error_recorder)
                gui.run()
            except Exception as e:
                logging.error(f"GUI 线程异常: {e}", exc_info=True)
        
        thread = Thread(target=run_gui, daemon=True)
        thread.start()
        return thread
