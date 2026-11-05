# 原型页面（`preview/`）

纯静态 HTML，**不需要编译、不需要服务器**，浏览器双击打开即可。用于方案讨论、交互走查和现场兜底演示。

## 页面一览

| 页面 | 用途 |
|---|---|
| [`index.html`](index.html) | 原型总入口，从这里跳其他页 |
| [`elevator_ui_preview.html`](elevator_ui_preview.html) | App 主界面原型（楼层、井道、呼梯按钮） |
| [`elevator_3d_model.html`](elevator_3d_model.html) | 3D 井道模型（可交互） |
| [`elevator_3d_preview.html`](elevator_3d_preview.html) | 3D 井道快速预览 |
| [`ble_console.html`](ble_console.html) | BLE 指令调试台（模拟 `FFE1` 写入与 `FFE2` 回执） |
| [`rssi_floor_sim.html`](rssi_floor_sim.html) | RSSI 判层模拟：调参看滤波、滞回与防抖效果 |
| [`chime_calib.html`](chime_calib.html) | 到站叮声的节奏校准 |
| [`floor_display_reader.html`](floor_display_reader.html) | 楼层显示屏读数练习 / 演示 |
| [`monitor_live.html`](monitor_live.html) | 实时联调监视面板 |
| [`deck.html`](deck.html) | 演示稿（翻页版） |
| [`storyboard.html`](storyboard.html) | 演示稿（故事线版） |
| [`teammate_app_mock.html`](teammate_app_mock.html) | 队友导航 App 的界面 Mock |

## 约定

- 全部为**纯前端**，不发起任何网络请求，不依赖 CDN。
- 页面里的数值是**演示用**，真实参数以 `docs/` 下的协议与规格文档为准。
- 改完随手在浏览器里刷新验证即可，没有构建步骤。
