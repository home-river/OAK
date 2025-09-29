# OAK检测系统 systemd 自启动服务

本目录包含了在香橙派上配置OAK检测系统开机自启动的完整解决方案。

## 文件说明

### 服务文件
- `simple_can_setup.service` - CAN接口配置服务
- `oak-detector.service` - OAK检测程序服务（root用户运行）

### 脚本文件
- `simple_can_setup.sh` - CAN接口自动配置脚本
- `install_systemd_services.sh` - 一键安装脚本

## 快速部署

### 1. 复制文件到香橙派
```bash
# 将整个systemd_config目录复制到香橙派
scp -r systemd_config/ root@your_orangepi_ip:/root/
```

### 2. 运行安装脚本
```bash
# 在香橙派上以root用户执行
cd /root/systemd_config
chmod +x install_systemd_services.sh
./install_systemd_services.sh
```

### 3. 重启系统
```bash
sudo reboot
```

## 手动安装步骤

如果需要手动安装，请按以下步骤操作：

### 1. 安装依赖
```bash
sudo apt-get update
sudo apt-get install -y can-utils python3-pip
pip3 install opencv-python depthai numpy
```

### 2. 配置权限
```bash
# 添加用户到相关组
sudo usermod -a -G dialout,plugdev,video $USER

# 配置USB设备权限
echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="03e7", MODE="0666", GROUP="plugdev"' | sudo tee /etc/udev/rules.d/99-oak.rules
sudo udevadm control --reload-rules
```

### 3. 安装服务文件
```bash
# 复制CAN配置脚本
sudo cp setup-can.sh /usr/local/bin/
sudo chmod +x /usr/local/bin/setup-can.sh

# 安装systemd服务文件
sudo cp can-setup.service /etc/systemd/system/
sudo cp oak-detector.service /etc/systemd/system/

# 修改oak-detector.service中的项目路径
sudo sed -i 's|/home/pi/OAK_TEST/version/temp1.0|/path/to/your/project|g' /etc/systemd/system/oak-detector.service
```

### 4. 启用服务
```bash
sudo systemctl daemon-reload
sudo systemctl enable can-setup.service
sudo systemctl enable oak-detector.service
```

## 服务管理命令

### 查看服务状态
```bash
sudo systemctl status can-setup.service
sudo systemctl status oak-detector.service
```

### 查看服务日志
```bash
# 查看CAN配置日志
sudo journalctl -u can-setup.service -f

# 查看OAK检测程序日志
sudo journalctl -u oak-detector.service -f

# 查看CAN配置脚本日志
sudo tail -f /var/log/can-setup.log
```

### 手动启动/停止服务
```bash
# 启动服务
sudo systemctl start oak-detector.service

# 停止服务
sudo systemctl stop oak-detector.service

# 重启服务
sudo systemctl restart oak-detector.service
```

### 禁用自启动
```bash
sudo systemctl disable can-setup.service
sudo systemctl disable oak-detector.service
```

## 故障排除

### 1. CAN接口问题
```bash
# 检查CAN接口状态
ip link show can0

# 手动配置CAN接口
sudo /usr/local/bin/setup-can.sh

# 检查CAN模块是否加载
lsmod | grep can
```

### 2. OAK相机问题
```bash
# 检查USB设备
lsusb | grep 03e7

# 检查设备权限
ls -l /dev/bus/usb/

# 测试OAK相机连接
python3 -c "import depthai as dai; print('OAK相机连接正常' if dai.Device.getAllAvailableDevices() else '未检测到OAK相机')"
```

### 3. 显示问题
```bash
# 检查DISPLAY环境变量
echo $DISPLAY

# 检查X11权限
xhost +local:

# 检查图形界面状态
systemctl status graphical-session.target
```

### 4. 权限问题
```bash
# 检查用户组
groups $USER

# 重新配置权限
sudo usermod -a -G dialout,plugdev,video $USER
```

## 配置说明

### CAN接口配置
- 波特率: 250000
- 接口: can0
- 自动加载内核模块: can, can-raw, can-bcm, can-gw

### OAK检测程序配置
- 默认全屏显示
- 自动启动延迟: 15秒（等待图形界面就绪）
- 自动重启: 失败后10秒重启
- 运行用户: pi（可修改）

### 分辨率配置
- 单帧: 640x360
- 全屏: 1920x1080
- 窗口: 1280x360

## 注意事项

1. **硬件要求**: 确保CAN接口硬件已正确连接
2. **用户权限**: 服务以指定用户身份运行，需要相应权限
3. **图形界面**: 需要图形界面支持，确保已安装桌面环境
4. **网络依赖**: 首次安装需要网络连接下载依赖包
5. **存储空间**: 确保有足够存储空间安装依赖包

## 自定义配置

### 修改项目路径
编辑 `/etc/systemd/system/oak-detector.service` 文件中的路径：
```ini
Environment=PYTHONPATH=/your/project/path
WorkingDirectory=/your/project/path
```

### 修改运行用户
编辑服务文件中的用户设置：
```ini
User=your_username
Group=your_username
```

### 修改CAN波特率
编辑 `/usr/local/bin/setup-can.sh` 文件中的波特率设置：
```bash
ip link set can0 type can bitrate 500000  # 修改为所需波特率
```
