# ESP32 固件（`firmware/`）

三个 Arduino sketch，互不依赖，可单独编译烧录。

| 目录 | 作用 | 广播名 |
|---|---|---|
| `elevator_1F/` | 1F 呼梯板 | `ELEV-1F` |
| `elevator_2F/` | 2F 呼梯板 | `ELEV-2F` |
| `chime_node/` | 到站叮声（可选，不装也能完整演示） | — |

## 两块呼梯板的唯一差别

`elevator_1F.ino` 与 `elevator_2F.ino` **只有 `FLOOR_NAME` 一行不同**，其余逻辑、引脚、参数完全一致。改这一行即可互换角色。

## 编译参数

| 项 | 值 |
|---|---|
| 开发板 | ESP32 Dev Module |
| 分区表 | Huge APP (3MB No OTA/1MB SPIFFS) |
| 第三方库 | 无（LEDC 硬件 PWM 与 BLE 均来自 ESP32 核心） |
| 舵机引脚 | **D13 = 上行**，**D12 = 下行** |
| 舵机角度 | 松开 **70°** → 按下 **130°** |
| 动作时序 | 行程 350 ms + 保持 600 ms + 收回 350 ms |

## BLE 接口

服务 `FFE0`，特征 `FFE1`（命令，写 `UP` / `DOWN`）、`FFE2`（状态 notify，回执形如 `1F|OK:UP`）。完整协议见 [`../docs/BLE_PROTOCOL.md`](../docs/BLE_PROTOCOL.md)。

## 烧录方式

| 想做什么 | 看这里 |
|---|---|
| 从源码编译烧录 | [`烧录说明.md`](烧录说明.md) |
| 直接用预编译镜像 | [`../releases/firmware/`](../releases/firmware/) |
| 查版本要点 | [`_版本信息.md`](_版本信息.md) |

> 预编译镜像是**合并镜像**，按 `烧录说明.md` 里的地址直接烧，不需要先装 Arduino IDE。
