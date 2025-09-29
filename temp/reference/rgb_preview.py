#!/usr/bin/env python3

import cv2
import depthai as dai
import sys

def create_rgb_preview_pipeline():
    """创建RGB预览pipeline"""
    pipeline = dai.Pipeline()

    # Define source and output
    camRgb = pipeline.create(dai.node.ColorCamera)
    xoutRgb = pipeline.create(dai.node.XLinkOut)

    xoutRgb.setStreamName("rgb")

    # Properties
    camRgb.setPreviewSize(640, 480)  # 增大预览尺寸
    camRgb.setInterleaved(False)
    camRgb.setColorOrder(dai.ColorCameraProperties.ColorOrder.RGB)
    camRgb.setFps(30)  # 设置帧率

    # Linking
    camRgb.preview.link(xoutRgb.input)
    
    return pipeline

def start_rgb_preview(mxid: str):
    """
    通过MxId启动RGB预览
    
    Args:
        mxid: 设备的MxId
    """
    try:
        # 创建pipeline
        pipeline = create_rgb_preview_pipeline()
        
        # 通过 MxId 连接设备
        print(f"正在连接设备: {mxid}")
        with dai.Device(pipeline, mxid) as device:
            print(f"✅ 已连接到设备: {mxid}")
            
            # 显示设备信息
            print('连接的相机:', device.getConnectedCameraFeatures())
            print('USB速度:', device.getUsbSpeed().name)
            
            if device.getBootloaderVersion() is not None:
                print('Bootloader版本:', device.getBootloaderVersion())
            
            print('设备名称:', device.getDeviceName())
            print('产品名称:', device.getProductName())
            print()
            print("📷 RGB预览已启动")
            print("💡 按 'q' 键退出预览")
            print("-" * 40)

            # Output queue will be used to get the rgb frames from the output defined above
            qRgb = device.getOutputQueue(name="rgb", maxSize=4, blocking=False)

            while True:
                inRgb = qRgb.get()  # blocking call, will wait until a new data has arrived

                # Retrieve 'bgr' (opencv format) frame
                frame = inRgb.getCvFrame()
                
                # 添加设备信息到图像上
                cv2.putText(frame, f"Device: {mxid}", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                cv2.putText(frame, "Press 'q' to quit", (10, frame.shape[0] - 10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                
                cv2.imshow(f"RGB Preview - {mxid}", frame)

                if cv2.waitKey(1) == ord('q'):
                    break
            
            cv2.destroyAllWindows()
            print("✅ 预览已关闭")
            
    except Exception as e:
        print(f"❌ 连接设备失败: {e}")
        return False
    
    return True


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("使用方法: python rgb_preview.py <MxId>")
        print("示例: python rgb_preview.py 18443010F105060F00")
        sys.exit(1)
    
    mxid = sys.argv[1]
    print(f"🚀 启动RGB预览工具")
    print(f"目标设备MxId: {mxid}")
    print("=" * 50)
    
    success = start_rgb_preview(mxid)
    
    if success:
        print("✅ RGB预览工具执行成功")
    else:
        print("❌ RGB预览工具执行失败")
        sys.exit(1)
