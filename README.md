# Mocen_Elevator_Ctrl

校园电梯交互：**Android App** + **ESP32 呼梯固件**。

手机走近电梯 → BLE 发现呼梯板 → **由人主动点按** → 舵机按下墙面实体按钮；
App 同步渲染双梯井道，并给出"电梯在哪层 / 该往哪走"的指引。

> **版本**：App **v12** · 固件 **v8**
> **井道**：B / 1F / 2F / 3F　|　**呼梯装置**：装在 **1F / 2F**
> **广播名**：`ELEV-1F` / `ELEV-2F`

---

## 目录

| 路径 | 内容 |
|---|---|
| `android/` | Android App 源码（Kotlin，Android Studio / Gradle 直接打开） |
| `firmware/` | ESP32 固件源码（3 个 `.ino`）+ 烧录说明 |
| `docs/` | 协议、空间模型、接口、交接、评估与现场演示文档（入口见 [`docs/README.md`](docs/README.md)） |
| `preview/` | 纯静态原型与自测页（双击 HTML 即可，无需编译） |
| `mech/` | 增压结构件：CAD 脚本、STL 模型、渲染图 |
| `presentation/` | 项目展示 PPT（动图已替换为各自首帧静态图） |
| `media/` | 演示视频等媒体素材 |
| `packages/` | 按对象拆分的三份交接包（App 对接 / 到站检测 / 井道模型） |
| `releases/` | 预编译发行包：App APK、固件合并镜像 |
| `tools/` | 自检脚本（`preflight.ps1`） |

> 版本要点见 [`CHANGELOG.md`](CHANGELOG.md)；常见问题见 [`docs/FAQ.md`](docs/FAQ.md)。

---

## 固件

| 板子 | 文件 | 说明 |
|---|---|---|
| 1F | `firmware/elevator_1F/elevator_1F.ino` | 广播名 `ELEV-1F` |
| 2F | `firmware/elevator_2F/elevator_2F.ino` | 广播名 `ELEV-2F` |
| 到站叮声（可选） | `firmware/chime_node/chime_node.ino` | 不装也能完整演示 |

两块呼梯板**只有 `FLOOR_NAME` 一行不同**；舵机引脚 **D13 = 上行、D12 = 下行**。

- 开发板：**ESP32 Dev Module**
- 分区表：**Huge APP (3MB No OTA/1MB SPIFFS)**
- 第三方库：**无需安装**（LEDC 硬件 PWM 与 BLE 均来自 ESP32 核心）
- 舵机角度：松开 **70°** → 按下 **130°**；行程 350 ms + 保持 600 ms + 收回 350 ms
- BLE：服务 `FFE0`，特征 `FFE1`（命令，写 `UP` / `DOWN`）、`FFE2`（状态 notify，回执形如 `1F|OK:UP`）

## App

```bash
cd android
gradle assembleDebug     # 产物 app/build/outputs/apk/debug/app-debug.apk
```

或直接用 Android Studio 打开 `android/` 目录。

关键文件位于 `android/app/src/main/java/com/mocen/elevator/`：

| 文件 | 作用 |
|---|---|
| `MainActivity.kt` | 主界面、扫描/连接、悬浮呼梯按钮 |
| `BleManager.kt` | BLE 扫描与 GATT 连接（广播名前缀 `ELEV-`） |
| `FloorJudge.kt` | RSSI 判层（中位数 + EMA + 滞回 + 连胜防抖） |
| `ElevatorView.kt` | 真 3D 井道（双轿厢） |
| `CarFloorSource.kt` | "轿厢在哪层"的来源（画面 / 摄像头 / 手动，可切换） |
| `LocalApiServer.kt` | 对外最小 HTTP 接口 |

## 设计约束

- **只有人主动点按才会呼梯**，没有任何定时器自动呼梯。
- 呼梯装置**只部署在 1F / 2F**，其余楼层不做物理呼梯。
- 运行**不依赖公网**：手机与呼梯板之间是 BLE 直连。

## 文档

| 文档 | 内容 |
|---|---|
| [`docs/README.md`](docs/README.md) | **文档总索引**（协议 / 说明 / 子目录分类） |
| [`docs/FAQ.md`](docs/FAQ.md) | 常见问题：为什么只能手动呼梯、能否断网等 |
| [`docs/BLE_PROTOCOL.md`](docs/BLE_PROTOCOL.md) | BLE 广播、服务/特征与命令回执协议 |
| [`docs/API.md`](docs/API.md) | 对外接口约定 |
| [`docs/SHAFT_MODEL.md`](docs/SHAFT_MODEL.md) | 井道/楼层空间模型 |
| [`docs/NAV_APP_UI_SPEC.md`](docs/NAV_APP_UI_SPEC.md) | 导航 App 界面规格 |
| [`docs/IOS_INTEGRATION.md`](docs/IOS_INTEGRATION.md) | iOS 侧接入说明 |
| [`docs/HANDOVER.md`](docs/HANDOVER.md) | 交接说明 |
| [`docs/REPORT.md`](docs/REPORT.md) | 项目技术报告 |
| [`docs/CRITIQUE.md`](docs/CRITIQUE.md) | 设计自评与风险 |
| [`docs/搁置与待办.md`](docs/搁置与待办.md) | 搁置项与后续待办 |
| [`docs/演示材料/`](docs/演示材料/) | 现场演示手册、能力与边界、版本信息 |

## 说明

- 本仓库含**源码、文档、原型与发行包**（见 `releases/`）；构建中间产物（`build/`、`.gradle/`、`local.properties`）不入库。
- 电梯装置为自制硬件，**未在本仓库内提供实物**；楼层与角度参数以文档为准。
