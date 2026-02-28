# 极简示例：看距离变换的效果
import numpy as np
import cv2

# 模拟粘连的二值掩码（两个矩形连在一起）
mask = np.zeros((100, 100), dtype=np.uint8)
mask[20:60, 20:40] = 255  # 第一个矩形
mask[40:80, 30:50] = 255  # 第二个矩形（和第一个粘连）

# 欧几里得距离变换
distance = cv2.distanceTransform((mask > 0).astype(np.uint8), cv2.DIST_L2, 5)

# 可视化：距离图（越亮=距离值越大）

def to_u8(x: np.ndarray) -> np.ndarray:
    x = x.astype(np.float32)
    mn, mx = float(x.min()), float(x.max())
    if mx <= mn:
        return np.zeros_like(x, dtype=np.uint8)
    y = (x - mn) / (mx - mn)
    return (y * 255).astype(np.uint8)


def stack2x2(a: np.ndarray, b: np.ndarray, c: np.ndarray, d: np.ndarray) -> np.ndarray:
    top = cv2.hconcat([a, b])
    bot = cv2.hconcat([c, d])
    return cv2.vconcat([top, bot])


mask_u8 = mask.copy()
dist_u8 = to_u8(distance)
dist_color = cv2.applyColorMap(dist_u8, cv2.COLORMAP_TURBO)

dist_thresh = float(distance.max()) * 0.45
sure_fg = (distance >= dist_thresh).astype(np.uint8) * 255
kernel = np.ones((3, 3), np.uint8)
sure_bg = cv2.dilate(mask_u8, kernel, iterations=2)
unknown = cv2.subtract(sure_bg, sure_fg)

num_labels, markers = cv2.connectedComponents((sure_fg > 0).astype(np.uint8))
markers = markers + 1
markers[unknown > 0] = 0

ws_base = cv2.cvtColor(mask_u8, cv2.COLOR_GRAY2BGR)
ws_base[mask_u8 == 0] = (0, 0, 0)
markers_ws = cv2.watershed(ws_base.copy(), markers.astype(np.int32))

vis_seg = ws_base.copy()
vis_seg[markers_ws == -1] = (0, 255, 255)

for lbl in range(2, int(markers_ws.max()) + 1):
    region = (markers_ws == lbl).astype(np.uint8)
    if region.sum() == 0:
        continue
    m = cv2.moments(region, binaryImage=True)
    if m["m00"] > 0:
        cx = int(m["m10"] / m["m00"])
        cy = int(m["m01"] / m["m00"])
        cv2.circle(vis_seg, (cx, cy), 3, (0, 255, 0), -1)

    dist_in = distance.copy()
    dist_in[region == 0] = -1
    _, _, _, max_loc = cv2.minMaxLoc(dist_in.astype(np.float32))
    cv2.circle(vis_seg, max_loc, 3, (0, 0, 255), -1)

sure_fg_bgr = cv2.cvtColor(sure_fg, cv2.COLOR_GRAY2BGR)
unknown_bgr = cv2.cvtColor(unknown, cv2.COLOR_GRAY2BGR)

panel = stack2x2(
    cv2.cvtColor(mask_u8, cv2.COLOR_GRAY2BGR),
    dist_color,
    sure_fg_bgr,
    vis_seg,
)

cv2.imshow("mask | distance  /  sure_fg | watershed+centers", panel)
cv2.waitKey(0)
cv2.destroyAllWindows()