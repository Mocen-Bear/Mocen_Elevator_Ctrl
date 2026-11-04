# 更新记录

本文件记录对外交付的版本要点；逐行改动以 Git 提交历史为准。

## App v12

- **悬浮呼梯按钮**：只有人主动点按才下发指令，没有任何定时器或传感器自动触发。
- BLE 扫描阶段按广播名前缀 `ELEV-` 过滤，连接后向 `FFE1` 写入 `UP` / `DOWN`。
- 订阅 `FFE2` 回执（形如 `1F|OK:UP`），用于界面二次确认。
- 楼层判断：RSSI 中位数滤波 + EMA + 滞回 + 连胜防抖，避免楼层数字来回跳。
- 双轿厢 **3D 井道**视图，井道 **B**，楼层 **1F / 2F / 3F**。
- 轿厢位置来源可切换：画面识别 / 摄像头 / 手动。
- `LocalApiServer` 提供对外最小 HTTP 接口，便于联调。
- 安装包：[`releases/android/elevator-call-v12.apk`](releases/android/elevator-call-v12.apk)

## 固件 v8

- 开发板 **ESP32 Dev Module**，分区表 **Huge APP (3MB No OTA/1MB SPIFFS)**，无第三方库依赖。
- BLE：服务 `FFE0`，特征 `FFE1`（命令，写 `UP` / `DOWN`）、`FFE2`（状态 notify）。
- 舵机：**D13 = 上行、D12 = 下行**；松开 **70°** → 按下 **130°**，行程 350 ms + 保持 600 ms + 收回 350 ms。
- 两块呼梯板只有 `FLOOR_NAME` 一行不同，广播名分别为 `ELEV-1F` / `ELEV-2F`。
- 可选到站叮声节点 `firmware/chime_node/`，不装也能完成完整演示。
- 预编译合并镜像：[`releases/firmware/`](releases/firmware/)

## 说明

- 版本号在各目录的 `_版本信息.md` 中维护（`firmware/`、`docs/android/`、`docs/项目资料/` 等）。
- 本仓库只收源码、文档与发行包；构建中间产物见 `.gitignore`。
