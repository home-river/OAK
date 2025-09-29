#!/bin/bash
# OAK检测系统systemd服务安装脚本
# 适用于香橙派Ubuntu/Debian系统

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 日志函数
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# 检查是否以root权限运行
if [[ $EUID -ne 0 ]]; then
   error "此脚本需要root权限运行"
   exit 1
fi

log "开始安装OAK检测系统systemd服务..."

# 获取当前脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

log "项目目录: $PROJECT_DIR"

# 1. 清理旧服务
log "清理旧服务配置..."
systemctl stop oak-detector.service 2>/dev/null || true
systemctl disable oak-detector.service 2>/dev/null || true
systemctl stop simple_can_setup.service 2>/dev/null || true
systemctl disable simple_can_setup.service 2>/dev/null || true

# 删除旧服务文件
rm -f /etc/systemd/system/oak-detector.service
rm -f /etc/systemd/system/simple_can_setup.service

# 清理旧的软链接
rm -f /etc/systemd/system/graphical-session.target.wants/oak-detector.service
rm -f /etc/systemd/system/multi-user.target.wants/simple_can_setup.service

# 2. 修复系统权限警告
log "修复系统权限警告..."
if [ -f /lib/systemd/system/rkaiq_3A.service ]; then
    chmod 644 /lib/systemd/system/rkaiq_3A.service
fi

# 3. 安装CAN初始化服务
log "安装CAN初始化服务..."
if [ -f "$SCRIPT_DIR/simple_can_setup.service" ]; then
    # 确保CAN初始化脚本存在且可执行
    if [ -f "$SCRIPT_DIR/simple_can_setup.sh" ]; then
        chmod +x "$SCRIPT_DIR/simple_can_setup.sh"
        log "✓ CAN初始化脚本已设置为可执行"
    else
        warning "CAN初始化脚本不存在: $SCRIPT_DIR/simple_can_setup.sh"
    fi
    
    # 复制CAN服务文件
    cp "$SCRIPT_DIR/simple_can_setup.service" /etc/systemd/system/
    log "✓ simple_can_setup.service 已复制"
else
    warning "CAN服务文件不存在: $SCRIPT_DIR/simple_can_setup.service"
fi

# 4. 安装主检测服务
log "安装OAK检测服务..."
if [ -f "$SCRIPT_DIR/oak-detector.service" ]; then
    cp "$SCRIPT_DIR/oak-detector.service" /etc/systemd/system/
    log "✓ oak-detector.service 已复制"
else
    error "主服务文件不存在: $SCRIPT_DIR/oak-detector.service"
    exit 1
fi

# 5. 重新加载systemd配置
log "重新加载systemd配置..."
systemctl daemon-reload
systemctl reset-failed

# 6. 启用服务
log "启用systemd服务..."

# 启用CAN初始化服务
if [ -f /etc/systemd/system/simple_can_setup.service ]; then
    systemctl enable simple_can_setup.service
    if systemctl is-enabled simple_can_setup.service >/dev/null 2>&1; then
        log "✓ simple_can_setup.service 已启用"
    else
        error "✗ simple_can_setup.service 启用失败"
    fi
fi

# 启用主检测服务
systemctl enable oak-detector.service
if systemctl is-enabled oak-detector.service >/dev/null 2>&1; then
    log "✓ oak-detector.service 已启用"
else
    error "✗ oak-detector.service 启用失败"
fi

# 7. 验证服务配置
log "验证服务配置..."
systemd-analyze verify /etc/systemd/system/oak-detector.service 2>/dev/null || warning "oak-detector.service 配置验证有警告"

if [ -f /etc/systemd/system/simple_can_setup.service ]; then
    systemd-analyze verify /etc/systemd/system/simple_can_setup.service 2>/dev/null || warning "simple_can_setup.service 配置验证有警告"
fi

# 8. 显示服务状态
log "当前服务状态:"
if [ -f /etc/systemd/system/simple_can_setup.service ]; then
    echo "=== CAN初始化服务状态 ==="
    systemctl status simple_can_setup.service --no-pager -l
    echo ""
fi

echo "=== OAK检测服务状态 ==="
systemctl status oak-detector.service --no-pager -l

# 7. 提供使用说明
echo ""
log "安装完成！"
echo ""
echo "使用说明:"
echo "1. 重启系统后服务将自动启动"
echo "2. 手动启动服务: systemctl start oak-detector.service"
echo "3. 查看服务状态: systemctl status oak-detector.service"
echo "4. 查看服务日志: journalctl -u oak-detector.service -f"
echo "5. 停止服务: systemctl stop oak-detector.service"
echo "6. 禁用自启动: systemctl disable oak-detector.service"
echo ""
echo "注意事项:"
echo "- 确保OAK相机已连接"
echo "- CAN接口将由主程序自动配置"
echo "- 系统将以用户 '$USER_NAME' 身份运行OAK检测程序"
echo "- 主程序内置了CAN接口自动配置功能"
echo "- 程序默认全屏显示，按F键可切换窗口模式"
echo ""
warning "建议重启系统以确保所有配置生效: reboot"
