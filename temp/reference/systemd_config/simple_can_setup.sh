#!/bin/bash
# 简化的CAN接口配置脚本

# 加载CAN模块
modprobe can
modprobe can-raw

# 配置can0接口
ip link set down can0 2>/dev/null || true
ip link set can0 type can bitrate 250000
ip link set up can0

echo "CAN接口配置完成: can0 @ 250000"
