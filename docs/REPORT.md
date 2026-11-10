# 电梯呼叫系统 —— 技术工作报告 / 交接文档

## 目录

- [0. TL;DR（30 秒版）](#0-tldr30-秒版)
- [1. 需求与迭代历史（为什么要长成现在这样）](#1-需求与迭代历史为什么要长成现在这样)
- [2. 系统架构](#2-系统架构)
- [3. 硬件与接线](#3-硬件与接线)
- [4. 通信协议（BLE）](#4-通信协议ble)
- [5. ESP32 固件设计](#5-esp32-固件设计)
- [6. Android App 设计](#6-android-app-设计)
- [7. 关键设计决策与取舍（**设计要点**）](#7-关键设计决策与取舍设计要点)
- [8. 当前局限 / 风险 / 未验证项（**请读者重点关注**）](#8-当前局限--风险--未验证项请读者重点关注)
- [9. 建议的扩展方向（按性价比排序）](#9-建议的扩展方向按性价比排序)
- [10. 目录结构与构建](#10-目录结构与构建)
- [11. 验证状态（诚实清单）](#11-验证状态诚实清单)
- [12. 设计问题清单（待验证）](#12-设计问题清单待验证)
- [13. 备选方案对比（WiFi 主从）与取舍](#13-备选方案对比wifi-主从与取舍)
- [14. 早期反馈的修复清单](#14-早期反馈的修复清单)
- [附录 A：参数速查](#附录-a参数速查)
- [附录 B：安全声明](#附录-b安全声明)


> 用途：记录设计过程与取舍，便于后续维护与交接。
> 阅读者假设：具备 Android(Kotlin/Jetpack) 与嵌入式(ESP32/Arduino) 基础，但不了解本项目。
> 报告编写日期：2026-10-16　版本：**v4（按早期反馈加固后的版本）**

---

## 0. TL;DR（30 秒版）

- **做什么**：用手机 App 远程让电梯外的舵机去按“上行/下行”呼梯按钮。
- **怎么做**：每层放一块 ESP32，BLE 广播自己的楼层名；手机靠 **RSSI 信号强度**判断“你在几层”，并通过 BLE GATT **长连接 + 订阅状态**写入 `UP`/`DOWN`，ESP32 用**时间驱动状态机**驱动舵机按压，动作完成后 `NOTIFY` 回执。
- **两块板**：井道 **B–3F**，装置装在 **`ELEV-1F`、`ELEV-2F`** 两层（中间层才有上行+下行），各 2 个舵机，引脚 **D13=上行 / D12=下行**。
- **App**：深色 UI、打开即自动扫描/自动识别楼层、点按钮或**语音**呼叫、能收到“✓ 已按下”的真回执。
- **现状**：**两块固件均编译通过（原生 LEDC，零第三方库；Huge APP 分区 35%）；Android App clean 构建成功、零警告，产出 app-debug.apk（5.61MB）**。仅剩“真机 BLE/舵机联调”未做（无硬件）。

---

## 1. 需求与迭代历史（为什么要长成现在这样）

| 轮次 | 用户提出的需求 | 我们的回应 / 变更 |
|---|---|---|
| v1 | “ESP32+舵机远程控制电梯，写烧录程序+手机 App” | 初版：ESP32 WiFi HTTP + 舵机；App 局域网直连 |
| v2 | “App 靠近哪个 ESP32 就显示已到几层；ESP32 装电梯外，两块板控两层上下行；要完整 Android 工程” | **架构转向 BLE**：RSSI 测距识别楼层；每层一节点、2 舵机 |
| v3 | “两块板程序（D13/D12）；App 打开无需多余操作，像这张图；最好语音控制” | 拆成两份固件；UI 重做为深色电梯图；加入持续语音识别；引脚改 D13/D12 |
| **v4** | “这是他们对你的缺陷指出，你参考后给出最终的程序和 app” | **按 方案 A / 方案 B 两份早期反馈逐条修复**（详见 §14）：非阻塞舵机状态机、判层四道防抖、长连接+订阅回执、写队列、错误码分级、分区/JDK 根治等 |

**关键判断**：用户真实痛点是“**靠近即识别楼层**”，这天然需要“能测距的多设备发现”——BLE 广播 + RSSI 是最贴合的技术，胜过 WiFi/MQTT。（取舍详见 §7）

---

## 2. 系统架构

```
   ┌──────────────────────────── Android App ────────────────────────────┐
   │  MainActivity      : UI 状态机 + 靠近即自动识别楼层 + 语音语义解析     │
   │  BleManager        : 扫描 / 长连接 / 订阅 STATUS / 串行写队列 / 判层  │
   │  FloorJudge        : 楼层判定(中位数+EMA+滞回+连胜)                  │
   │  VoiceController   : SpeechRecognizer 持续聆听(错误分级退避)          │
   │  ElevatorView      : 自绘电梯井+轿厢动画(几何/渐变缓存)              │
   │  ElevatorDevice    : 节点模型(RSSI 滤波 + GATT + 写队列 + 状态)      │
   └───────┬───────────────────────────────────────────────┬────────────┘
           │ BLE 扫描广播(读 scanRecord.deviceName + RSSI)    │ BLE GATT：写 CMD + 订阅 STATUS
           ▼                                                 ▼
   ┌───────────────────────┐                       ┌───────────────────────┐
   │ ESP32 #1  ELEV-1F     │                       │ ESP32 #2  ELEV-2F     │
   │  舵机 D13 → 上行按钮  │                       │  舵机 D13 → 上行按钮  │
   │  舵机 D12 → 下行按钮  │                       │  舵机 D12 → 下行按钮  │
   │  BLE Server(GATT)     │                       │  BLE Server(GATT)     │
   │  时间驱动舵机状态机    │                       │  时间驱动舵机状态机    │
   └───────────────────────┘                       └───────────────────────┘
```

**核心数据流**
1. ESP32 广播：设备名 `ELEV-xF` + 服务 UUID `ffe0`，并**在连接后继续广播**（手机才能一边连着、一边靠 RSSI 测距）。
2. App 扫描回调：读 `scanRecord.deviceName`（不依赖 `getName()`），维护 `address -> device`；`ElevatorDevice` 对 RSSI 做**中位数 + EMA** 滤波。
3. `FloorJudge` 用“滞回 + 连胜”把滤波后的 RSSI 变成稳定的“所在楼层”。
4. 用户点 ▲/▼ 或说话 → 找到目标层节点 → 写入 `UP`/`DOWN`（经串行写队列）→ 舵机状态机 `伸出→按住→收回` → 完成后 `NOTIFY 楼层|OK:UP` → App 显示真回执。

---

## 3. 硬件与接线

- ESP32 ×2（实测外观为 ESP-32 / ESP32-WROOM-32，均按 `ESP32 Dev Module` 烧录）
- 舵机 ×4（每板 2 个）

| 信号 | ESP32 引脚 |
|---|---|
| 上行舵机 | **D13 / GPIO13** |
| 下行舵机 | **D12 / GPIO12** |
| 舵机 VCC | 外部 5V（独立电源） |
| 舵机 GND | 与 ESP32 共地 |

**硬约束/坑**
- 舵机堵转电流 ≥1A → **必须独立 5V** 并与 ESP32 共地，否则板子反复复位。
- **GPIO12 是 strapping 脚**：若接舵机后无法启动/烧录，先拔掉 D12 信号线再烧，或改 `DOWN_PIN` 为 14/27（只改固件一行）。
- 不建议用 GPIO6–11（接 flash）。

---

## 4. 通信协议（BLE）

### 4.1 GATT 定义（固件与 App 必须一致）

| 角色 | UUID |
|---|---|
| Service | `0000ffe0-0000-1000-8000-00805f9b34fb` |
| CMD（Write / WriteNR） | `0000ffe1-0000-1000-8000-00805f9b34fb` |
| STATUS（Read / Notify） | `0000ffe2-0000-1000-8000-00805f9b34fb` |
| CCCD（订阅通知） | `00002902-0000-1000-8000-00805f9b34fb` |

### 4.2 设备命名约定（**测距与寻址的基石**）

- 广播名严格为 `ELEV-` + 楼层，例如 `ELEV-1F`、`ELEV-2F`（固件放进**扫描响应**里）。
- App 从 **`ScanRecord.deviceName`** 取值（比 `BluetoothDevice.getName()` 可靠），只认前缀 `ELEV-`；去掉前缀得到 `1F`/`2F`。
- **楼层号 = 寻址键**：`节点.floor == "1F"` 即该层 ESP32。

### 4.3 命令字（App → ESP32，UTF-8 文本写入 CMD）

| 命令 | 语义 |
|---|---|
| `UP` | 按第 1 个舵机（上行） |
| `DOWN` | 按第 2 个舵机（下行） |
| `S1`..`Sn` / `PRESS n` | 按第 n 个舵机 |
| `ALL` | 同时按所有舵机 |
| `PING` / `?` / `STATUS` | 只回状态，不动作 |

状态回传（NOTIFY）：`楼层|结果`，如 `1F|OK:UP`（只有在**动作真正完成**时才发，`READY` 在上电/连接时作为初值）。

> 解析是**严格等值/前缀**的：`UPLOAD` 不会命中 `UP`（修掉了旧版 `startsWith("UP")` 的误判）。

---

## 5. ESP32 固件设计

文件：`firmware/elevator_1F/elevator_1F.ino`、`firmware/elevator_2F/elevator_2F.ino`
（两份代码仅 3 行不同（横幅 / 楼层行 / `FLOOR_NAME`）——刻意做成两份独立 sketch，方便用户“一块板一个文件”直接打开烧录）

### 5.1 关键设计点

1. **舵机 = 时间驱动状态机，`loop()` 绝不阻塞**：
   `IDLE → OUT(伸出) → HOLD(按住) → IN(收回) → IDLE`，全程用 `millis()` 计步。
   旧版 `pressServo()` 里 `delay()` 累计 ~1.3s，会把 BLE/串口/**另一个舵机**一起卡住。
   ```cpp
   case Axis::OUT: {
     unsigned long dt = now - a.t0;
     if (dt >= SWEEP_MS) { servoWrite(i, ANGLE_PRESS); a.phase = Axis::HOLD; a.t0 = now; }
     else servoWrite(i, ANGLE_REST + (int)((long)(ANGLE_PRESS-ANGLE_REST) * dt / SWEEP_MS));
     break;
   }
   ```
2. **命令队列解耦**：BLE 写回调只 `xQueueSend`，真正的动作在 `loop()` 里推进；
   **检查 `xQueueSend` 返回值**，队列满时回 `ERR:QUEUE_FULL`（不再静默丢弃）。
3. **断线重启广播放在 `loop()`**：`onDisconnect` 只置 `volatile gRestartAdv=true`，回调里**不 `delay()`**。
4. **连接后继续广播**：`onConnect` 里再次 `startAdvertising()` —— 手机才能边连边测 RSSI。
5. **原生 LEDC 驱动舵机，零第三方库**（采纳自 方案 A 方案）：兼容 core 2.x / 3.x，见 §5.2。
6. **多手机支持（v5）**：回执改为**广播式** `notify()`，交给底层按 `conn_id` 跳过已断开的连接；
   不再用单个 `gConnected` 布尔（旧版一台手机断开会连累其它手机收不到 `OK:*`）。
   每块板最多 **3 台手机**同时连接（ESP32 `CONFIG_BTDM_CTRL_BLE_MAX_CONN=3`）。
7. **配置集中在文件顶部**（引脚 + 角度 + 时长），方便现场标定。

### 5.2 原生 LEDC 舵机代码（兼容 core 2.x / 3.x）
```cpp
void servoWrite(int i, int angle) {
  angle = constrain(angle, 0, 180);
  uint32_t us   = 500UL + (uint32_t)angle * 2000UL / 180UL;          // 500~2500us
  uint32_t duty = (uint32_t)((uint64_t)us * DUTY_MAX / PERIOD_US);   // 16bit 占空
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcWrite(axes[i].pin, duty);   // core 3.x：按 pin
#else
  ledcWrite(sCh[i], duty);        // core 2.x：按通道
#endif
}
```
> 50Hz → 周期 20000µs → 16bit 满量程 65535。`ledcAttach(pin,50,16)`（core 3.x）与
> `ledcSetup + ledcAttachPin`（core 2.x）用 `#if` 自动切换，两端都实测过编译。

### 5.3 角度标定（v8 起：默认 70°→130°，串口现场标定）
传动是「曲柄 + 长槽滑块」（苏格兰轭）：**销钉行程 ≈ R × (sin α − sin β)**，
R（曲柄舵机轴心 ↔ 销钉轴心）≈ **8.0mm**。真正的硬限位是**长槽两端**，不是按钮口的沉台。

角度是分三版定下来的：

| 版本 | 松开 → 按下 | 摆角 | 说明 |
|---|---|---|---|
| v6 | 90° → 100° | 10° | 按“面板沉台 1.6mm、按钮最多压进 1.6mm”取 10°（≈1.39mm）。**这个前提量错了对象，已作废。** |
| v7 | 90° → 130° | 40° | 改按长槽行程标定，130° 是现场手测能可靠压到按钮的位置。 |
| **v8** | **70° → 130°** | **60°** | 松开位再左移 20°，销钉沿长槽走 ≈ **7.9mm**（= 8.0 × (sin40° − sin(−20°))），按下位不变。 |

v5 及更早的 `20°→150°` 是“摆臂直接顶按钮”老结构的初值，已作废。

现场标定**不用改代码重烧**（v6 新增串口命令，115200）：`A70`/`+1`/`-1` 找位置、
`SR`/`SP` 记松开位/按下位、`SAVE` 存 Flash、`T` 试跑、`CLR` 恢复默认、`?` 查看，
`U`/`D`/`B` 切换标定对象（两个舵机分别标）。原因：MG90S 输出齿 25 齿、一齿 14.4° = 按钮 2.0mm 误差。
标定流程见 `烧录程序/烧录说明.md` 第五节。

---

## 6. Android App 设计

包名 `com.mocen.elevator`，minSdk 24 / target 34，Kotlin + ViewBinding + Material3。

### 6.1 模块职责

| 文件 | 职责 | 关键点 |
|---|---|---|
| `MainActivity.kt` | UI 状态机；**轿厢随靠近自动走 + 1F/2F 选呼叫目标**；语音语义解析；权限 | 靠近→轿厢移动（纯视觉）；目标=手动选 ?: 靠近层 |
| `BleManager.kt` | 扫描/长连接/订阅/写队列/判层 | 多节点常驻连接；统一 post 回主线程 |
| `FloorJudge.kt` | 楼层判定 | 中位数+EMA+滞回+连胜（吸收自 方案 B） |
| `VoiceController.kt` | 持续语音识别 | 错误分级退避；致命错误停止 |
| `ElevatorView.kt` | 自绘电梯井 | 几何/渐变缓存，动画可取消 |
| `ElevatorDevice.kt` | 节点模型 | `floor` 派生；RSSI 中位数+EMA |

### 6.2 “打开即用”的实现逻辑

1. `onCreate`：若有蓝牙权限 → `startScan()`；否则请求（Android 12+ 用 `BLUETOOTH_SCAN/CONNECT`，以下用 `ACCESS_FINE_LOCATION`）。
2. `onNodesChanged()`（`BleManager` 每 400ms tick 一次）：把节点快照交给 `MainActivity`。
3. **轿厢随靠近移动（纯视觉）**：`FloorJudge` 给出“你所在楼层”后，把 3D 轿厢移到该层。**不触发任何呼叫。**
4. **呼叫目标**：点 `1F/2F` 手动选定（`manualTarget`）；不点则默认跟随靠近楼层。**只有当“靠近楼层”变化时**才清掉手动目标、重新跟随。`1F/2F` 只决定 ▲/▼ 发去哪层，**不动轿厢**。
5. 状态胶囊：判出楼层 → 绿点 + `靠近 1F · 轿厢已到 1F · 在线 2/2`；否则红点 + `正在检测…`。
6. 信号丢失（没靠近任何一层）→ **轿厢停着不动**。
7. **呼叫一律手动**：`sendCommand(dir, floor)`（点 ▲/▼ 或语音）→ 找**目标楼层**节点 → 要求 `READY`，否则提示“连接中/未发现”。靠近不会自动呼叫。

### 6.3 BLE 扫描与连接（`BleManager`）

- 扫描用 `SCAN_MODE_LOW_LATENCY`，**不设 ScanFilter**（不同 ROM 对 ServiceUUID 过滤差异大），自己按名字前缀 `ELEV-` 过滤。
- **不周期性重启扫描**（旧版每 12s 重启会在扫描空档漏掉 RSSI 更新）；前台常扫即可。
- **长连接**：发现新节点即 `connectGatt(TRANSPORT_LE)`，服务发现后**订阅 STATUS**并保持连接。
- **串行写队列**：GATT 同一时刻只允许一个未完成操作。`writeCharacteristic` 返回 `false` 时**退回队首**并重试；写回调 3s 未到则看门狗放行下一笔。
- **检查 status**：连接/服务发现失败（如 133）有明确日志 + **指数退避重连**。
- **权限兜底**：`adapter`/`bluetoothLeScanner` 等全部 `runCatching`，旧版未捕获 `SecurityException` 会直接崩。
- **统一主线程**：所有 GATT/扫描回调的状态变更都 `handler.post` 回主线程，避免与 UI 读并发。

### 6.4 楼层判定（`FloorJudge`，全 App 最核心的一小块）

朴素做法“谁 RSSI 最强算哪层”会在电梯井里疯狂横跳。这里叠**四道防线**：

1. **中位数**（窗口 3）去毛刺；
2. **指数平滑**（α=0.62）——两者在 `ElevatorDevice.pushRssi` 内完成；
3. **滞回**：挑战者要比现任强出 `minLeadDb=3dB` 才算赢；
4. **连胜**：`winCount=1`（一赢就换 → “瞬时”手感；想更稳就调大）。

外加 **2.5 秒过期**：太久没扫到（掉电/走远）的节点 `markLost()`，不再参与判层；
现任一旦“够不着”（失联或低于 `minRssi`）**立即换层，不等连胜**。扫描回调里每收到一包就重判一次
（`EVAL_THROTTLE_MS=40ms` 上限），另有 **200 ms 心跳兜底**（`TICK_MS`），
所以楼层数字的刷新间隔是 **40~200 ms**，人眼观感是“人一到就翻”。
判定结果驱动 UI：靠近哪层，3D 轿厢就移到哪层（纯视觉，见 §6.2）；信号丢失即静止。**呼叫始终手动（▲/▼ 或语音），不会自动发生。**

### 6.5 语音（`VoiceController` + `parseVoice`）

- 持续聆听：`onResults` 后短延迟自动重听。
- **错误分级**（修掉旧版“任何错误都 350ms 重启”的死循环）：
  - `NO_MATCH / SPEECH_TIMEOUT / NETWORK*` → 300ms 退避；
  - `RECOGNIZER_BUSY` → 1500ms；`CLIENT` → 1000ms；
  - `SERVER / AUDIO / INSUFFICIENT_PERMISSIONS` → **致命，停止并提示**；
  - 连续失败 > 12 次 → 停止。
- 语义：楼层支持 `1f/1楼/1层/一楼/去一`；方向先匹配强词（上行/向上/上去/上楼…），**只有在明确提到楼层时**才接受“上/下”单字兜底（降低误触发）。
- `onPause` 自动停语音，避免后台耗电/报错循环。

### 6.6 UI（还原用户参考图）

- 深色主题 `Theme.Material3.Dark.NoActionBar`，底色 `#0A1220`。
- 组成：标题/副标题 → 状态胶囊(红/绿点) → 自绘电梯井(ElevatorView) + 浮动提示 → `1F/2F` 楼层按钮(选中态绿框) → ▲▼ 圆形按钮 → 语音按钮 → 底部状态条。
- `ElevatorView` 是一个**轻量软件 3D 渲染器**（不引入 OpenGL）：模型坐标定义“玻璃井道 + 曳引绳/对重/曳引机 + 每层厅门 + 贴墙楼板环 + 轿厢(六面体+双门)”，经 yaw/pitch 旋转 + 透视投影 + 平面着色（法线·光照），再按面平均深度做画家算法排序。**手指拖动可旋转、默认不自动旋转**；轿厢 `moveCarTo(floor)` 平滑升降，**静止时不重绘**（仅在有动作时 `invalidate()`）。所有几何/投影缓冲复用，每帧零分配。
- **视野窗口（`focusIndices`）**：投影时不再把整座 B–3F 井道压进一屏，而是**只框住 `1F`/`2F`**（`viewBottom = slabY(i0)-1.0`、`viewTop = slabY(i1+1)+0.8`），焦距按窗口高度自适应 → 井道**放大近一倍**；落在窗口带 `[slabY(i0), slabY(i1+1)]` 之外的几何（B 上半截 / 3F 下半截）统一**降透明度 + 压暗**（`GHOST=0.26`）做成“虚影”，再叠一层上下 `LinearGradient` 渐隐。`focusIndices` 留空即回到“四层铺满”。

---

## 7. 关键设计决策与取舍（**设计要点**）

| 决策 | 选择 | 理由 | 代价/替代方案 |
|---|---|---|---|
| 通信方式 | **BLE**（非 WiFi/MQTT） | ①要“靠近识别楼层”天然需要测距 ②无需配网、不怕断网、零部署 | 距离短(~10-30m)；替代：WiFi RSSI 需切换网络、MQTT 依赖公网 |
| 测距依据 | **RSSI 中位数+EMA+滞回+连胜** | 单值比较会横跳；四层防抖可控 | 多径/人体遮挡仍有影响；替代：卡尔曼/信标校准 |
| 楼层标识 | **广播名 `ELEV-xF`** | 免配网、可读、便于寻址 | 名字即协议，改名要改两端 |
| 连接策略 | **长连接 + 订阅 STATUS** | 才能拿到“舵机真按完”的回执、延迟低、可读 busy | 常驻连接略耗电；替代：短连接（无真 ACK、每次握手延迟） |
| 固件结构 | **两块板两份 sketch** | 用户心智“一块板一个程序” | 代码重复（仅 1 个宏不同）；替代：单份+多环境构建 |
| 语音 | **系统 SpeechRecognizer 持续聆听** | 无需云服务/密钥 | 依赖系统语音服务，部分国产 ROM 需装 Google 语音；替代：离线唤醒词(Vosk/Porcupine) |

---

## 8. 当前局限 / 风险 / 未验证项（**请读者重点关注**）

1. **仅剩真机联调未做**：固件与 App 均已实际编译/构建成功（见 §11）。未验证的是“烧到板子上后 BLE 能否稳定连、舵机角度是否合适、RSSI 判层现场是否抖”。
2. **分模块已加防抖，但阈值是理论值**：`minLeadDb=3`、`winCount=1`、`STALE=2.5s`（按“瞬时跟手”调过）需现场微调；现场若抖动就调回 4~5 / 2。
3. **GPIO12 strapping 风险**：见 §3。
4. **语音单字兜底仍可能误判**：已限制为“必须提到楼层”，但长句里仍有边角。
5. **楼层硬编码**：App 里 `shaftFloors = listOf("B","1F","2F","3F")`（3D 井道展示）、
   `deviceFloors = listOf("1F","2F")`（装了装置、可呼叫的层），未从扫描结果动态生成。
6. **安全边界**：仅适合演示；真实电梯需谨慎（附录 B）。

---

## 9. 建议的扩展方向（按性价比排序）

1. **动态楼层**：从扫描到的 `ELEV-*` 自动生成楼层按钮（改动集中在 `buildFloorButtons/refreshUi`）。
2. **离线唤醒词**：接入 `Porcupine`/`Vosk`，说“小梯”即唤醒，不依赖系统语音。
3. **单 ESP32 控多层**：`NUM_SERVOS` 扩多路，命令 `S1..Sn` 已支持。
4. **持久化配置**：楼层名/角度存 NVS，免重烧。
5. **多部手机/多电梯**：节点名加楼栋前缀（`ELEV-A-2F`）。

---

## 10. 目录结构与构建

```
elevator-control/
├── README.md                       # 项目总览
├── REPORT.md                       # 本报告
├── firmware/
│   ├── elevator_1F/elevator_1F.ino # FLOOR_NAME "1F", D13上行/D12下行
│   ├── elevator_2F/elevator_2F.ino # FLOOR_NAME "2F"
│   └── chime_node/chime_node.ino   # 可选：到站叮声
└── android/                        # Android Studio 工程 (Kotlin, viewBinding)
    ├── settings/build/build.gradle.kts, gradle.properties
    ├── gradlew, gradlew.bat, gradle/wrapper/*(jar 已补齐)
    └── app/src/main/
        ├── AndroidManifest.xml
        ├── java/com/mocen/elevator/{MainActivity,BleManager,FloorJudge,
        │        ElevatorView,ElevatorDevice,LocalApiServer}.kt
        └── res/{layout,drawable,values}
```

**依赖**：AndroidX core-ktx / appcompat / material 1.12 / constraintlayout / recyclerview；Kotlin 1.9.24；AGP 8.5.2；Gradle 8.7；JDK 17。

**烧录/构建要点（已实测）**
- 固件：**无需安装任何第三方库**；两块板均选 `ESP32 Dev Module` + **分区 `Huge APP`**。
  - 命令行验证：`arduino-cli compile --fqbn esp32:esp32:esp32:PartitionScheme=huge_app firmware/elevator_2F`
    （本机 arduino-cli 1.5.1 + esp32 core 3.3.12 → 通过，Flash **35%** / RAM 12%）。
- App：命令行验证 `cd android && gradle clean assembleDebug`
  （Gradle 8.7 + JDK17 + SDK34 → 通过、零警告，出 APK **5.61MB**）。
  - **路径含中文时必须**：`gradle.properties` 里设 `android.overridePathCheck=true`
    与 `-Dsun.jnu.encoding=UTF-8`。
  - **JDK 已由 `org.gradle.java.home` 钉到 JDK17**（避免挑到系统 Java 25 而报 “What went wrong”）。
  - Android Studio：Gradle JDK 选自带 JBR 17/21（勿用系统 Java 25）。

---

## 11. 验证状态（诚实清单）

| 项目 | 状态 | 方法 |
|---|---|---|
| **固件实际编译（1F）** | ✅ **通过** | arduino-cli 1.5.1 + esp32 core 3.3.12，Huge APP 分区 **Flash 35% / RAM 12%** |
| **固件实际编译（2F）** | ✅ **通过** | 同上 |
| **Android App 实际构建** | ✅ **通过（零警告）** | gradle 8.7 + JDK17 + SDK34，`clean assembleDebug` 出 APK 5.61MB |
| 真机烧录 / BLE 联调 / 舵机标定 | ❌ 未验证 | 无硬件连接 |
| RSSI 判层现场稳定性 | ❌ 未验证 | 需现场（已内置四道防抖，参数待现场微调） |

---

## 12. 设计问题清单（待验证）

1. 长连接 vs 短连接，在“演示要快 + 要真 ACK”的场景下，长连接是否已是最优？
2. 判层四道防抖的默认参数（±8dB / 连胜 3 / 8s 过期）在小场地是否过于保守？
3. 语音方案：继续用系统识别，还是换离线唤醒词？对“持续聆听”的功耗与隐私怎么看？
4. 固件拆两份 vs 单份宏配置，从“开源项目可维护性”角度哪个更优？
5. `BleManager` 里“设备常驻不 remove”是否会在长时间演示中累积太多 FAILED 节点？是否该加 LRU 上限？
6. 若要把本方案产品化，最先必须补的三件事是什么？

---

## 13. 备选方案对比（WiFi 主从）与取舍

方案 A agent 交付了**另一套完全不同的架构**并实测编译通过：**WiFi 主从代理**
（`board_f1` 开热点 AP=192.168.4.1，`board_f2` 静态 STA=192.168.4.2；App 连一个
热点后用 `GET /api/press?f=&b=` HTTP 呼梯）。

### 13.1 两套方案对比

| 维度 | 本方案（BLE + RSSI） | 方案 A 方案（WiFi 主从 HTTP） |
|---|---|---|
| **靠近识别楼层** | ✅ 原生支持（RSSI 判层）——这是用户核心需求 | ❌ 不支持（单一热点无法测距） |
| 手机“零操作” | ✅ 不连任何网，开 App 即扫即用 | ⚠️ 需手动连热点；连后手机无外网，部分 ROM 会弹窗/自动切回数据网络 |
| 对网络依赖 | 无 | 无外部网络，但需保持连热点 |
| 设备发现/寻址 | 广播名 `ELEV-xF` | 固定 IP（192.168.4.1/.2） |
| 聚合所有楼层状态 | ⚠️ 各自连接、App 侧聚合 | ✅ 主板聚合 `/api/status` 含各层 online/busy |
| 延迟 | 长连接后 ~几十 ms | 局域网 HTTP，约几十 ms |
| 舵机驱动 | 原生 LEDC（采纳自 方案 A） | 原生 LEDC |
| 编译产物体积 | App 5.61MB（Material/Kotlin） | App ~16KB（纯 Java/系统主题） |
| 已验证程度 | 固件+App 编译通过 | 固件+App 编译通过 |

### 13.2 已采纳的“精华”

1. **原生 LEDC 代替 Servo 库**（方案 A）——消除第三方依赖 + 规避 core 3.x 无 `Servo.h`。✅ 已合入。
2. **“实测构建”纪律**（方案 A）——不再只做静态检查，改为真机工具链编译/出包。✅ 已补做。
3. **楼层判定算法**（方案 B）——中位数+EMA+滞回+连胜，✅ 已移植为 `FloorJudge.kt`。
4. **AD 解析用 `scanRecord.deviceName`**（方案 B）——比 `getName()` 可靠。✅ 已采纳。
5. **写队列 + `writeCharacteristic` 返回值检查 + 退避重连**（方案 B）——✅ 已采纳。
6. **诚实风险清单**——本报告 §8/§11 同样列明。

### 13.3 建议的最终形态

- **主线推荐：BLE（本方案）**。用户最关键的需求是“**靠近即识别楼层**”，只有 RSSI 能做到；且 BLE 真正做到“打开即用、不碰 WiFi、手机不失联”。
- **可选增强**：若担心现场 BLE 不稳，可保留 WiFi 方案作为**降级通道**（BLE 优先，失败切 WiFi 热点）。
- **不建议**：用单热点 WiFi 去实现“识别楼层”——物理上做不到测距，会丢掉核心卖点。

---

## 14. 早期反馈的修复清单

> 依据：方案 A 的《批判报告》与 方案 B 的《REVIEW_OF_PEER_CODE》，两者均针对本项目
> v3 的**源码**逐条举证。下面按“他们指出 → 我们的处置”列出，全部已落到 v4 代码。
>
> **v5 更新**：v4 的“20 秒手动优先权”已**整段移除**——改为**职责分离**：
> `1F/2F` 只用来选**呼叫目标**，**轿厢随“靠近哪层的 ESP32”自动移动**；
> **呼叫仍是手动/语音**（▲/▼ 或说话），靠近不会自动呼叫。手动选的目标只在
> “靠近楼层变化”时作废。下表 #1.1 / #3.1 里“20 秒优先权”的说法以本行为准。
>
> **演示场景**：井道为 **B–3F 四层**，**呼梯装置只装在 1F 与 2F**。
> 原因：真实楼里 B（底层）只有“上行”、3F（顶层）只有“下行”，**只有中间层同时有上行+下行**，
> 才能把“上行 / 下行”两种呼梯都演示出来。因此两块固件为
> `firmware/elevator_1F/elevator_1F.ino` 与 `firmware/elevator_2F/elevator_2F.ino`；
> App 侧把楼层拆成 `shaftFloors = B~3F`（3D 井道展示）与 `deviceFloors = 1F/2F`（可呼叫）。

### 14.1 方案 A 提出的缺陷

| # | 方案 A 的指控 | v4 处置 |
|---|---|---|
| 1.1 | `userPickedFloor` 一次性开关，手动用一次自动判层**永久失效** | 改为 `manualUntil`（**20 秒**优先权），到期自动判层重新接管 |
| 1.2 | RSSI 裸值直接比较，无平滑/滞回 | 引入 `FloorJudge`：中位数+EMA+8dB 滞回+连胜 3 次（§6.4） |
| 1.3 | 设备永不过期，掉电板继续参与判层 | `ElevatorDevice.markLost()` + `STALE_MS=8s` 过期机制 |
| 2 | STATUS 是“死协议”：App 从不订阅、写后 200ms 即断，回执发不出去 | 改**长连接**并**订阅 CCCD**；固件在动作完成后 `NOTIFY`；App 收到后显示真回执 |
| 3 | 短连接延迟 1-2s；`pendingCmd/pendingName` 单例字段会被覆盖 | 长连接 + **每设备串行写队列**，无单例竞态 |
| 4 | 语音 `onError` 无差别重试 → 无限快循环 | 按错误码分级：可自愈退避、致命停止、连续失败 >12 次停止（§6.5） |
| 5.1 | `pressServo` 阻塞 loop ~2s；队列静默丢弃 | 改**时间驱动状态机**；`xQueueSend` 检查返回值并回 `ERR:QUEUE_FULL` |
| 5.2 | `gConnected` 无 `volatile` | 已加 `volatile` |
| 5.3 | `startsWith("UP")` 会误判 `UPLOAD` | 严格等值/前缀解析 + 数字范围校验 |
| 5.4 | `setMinPreferred` 重复调用 | 已移除 |
| 5.5 | 默认分区 Flash 84%，未用 huge_app | 文档 + 编译命令统一使用 **Huge APP**，降到 **35%** |
| 5.6 | 两份 sketch 靠宏区分、易漂移 | 保留两份（用户心智），但**除 `FLOOR_NAME` 外逐字节一致**并在头部注明 |
| 5.7 | GPIO12 strapping 只写文档、默认仍用 D12 | **保留 D12**（用户硬约束），但引脚改成单宏 `DOWN_PIN` + 明确“烧录时可拔线”指引 |
| 6.1 | 报告与代码不符（曾写 ESP32Servo）；前缀 `ELEV` vs `ELEV-` 不一致 | 报告改为 LEDC；前缀统一 `ELEV-` |
| 6.2 | “静态自检通过”是安慰剂 | 已改为真机工具链编译/构建（§11） |
| 6.3 | `gradle.properties` 缺 `org.gradle.java.home`，首次构建直接失败 | 已补 `org.gradle.java.home=D:/Android/jdk-17.0.20.1+1` |

> **v5 追加**：上表 #5.2 的 `gConnected`（含 volatile 修复）已**整体移除**——
> 回执改为**广播式 `notify()`**，交给底层按 `conn_id` 跳过断开的连接，从而支持
> **多台手机同时连接并各自控制**（每块板最多 3 台）。详见 `BLE_PROTOCOL.md` §13。

### 14.2 方案 B 提出的缺陷

| # | 方案 B 的指控 | v4 处置 |
|---|---|---|
| 3.1 | `userPickedFloor` 永不复位（与 方案 A 1.1 同） | 20 秒优先权，见 14.1 #1.1 |
| 3.2 | `BleManager` 未捕获 `SecurityException`，12s 后崩 | 全部蓝牙 API `runCatching` 兜底 |
| 3.3 | `scanning=true` 早于真正启动，早退后扫描永久卡死 | 仅 `startScan` 成功后置位；异常路径保证复位 |
| 3.4 | 无命令队列，字段被覆盖，断连在途 | 每设备写队列 + 就绪才发送 |
| 3.5 | 忽略 `writeCharacteristic` 返回值 → 回调不来 → GATT 泄漏 | **检查返回值**，`false` 就退回队首重试 |
| 3.6.1 | `onConnectionStateChange` 不看 status（133） | 看 status + 明确日志 + 退避重连 |
| 3.6.2 | `onServicesDiscovered` 不看 status | 看 status + 区分“缺少控制通道” |
| 3.6.3 | 服务发现前魔法 `delay(300)` | 已移除 |
| 3.6.4 | 设备从不清理 | 8s 过期 `markLost`；（常驻连接的 LRU 见 §12 问题 5） |
| 3.6.5 | 12s 重启扫描造成 RSSI 空档 | 取消周期重启，前台常扫 |
| 3.6.6 | RSSI 无滤波 | 中位数 + EMA |
| 3.6.7/8 | 语音 `onError` 无错误码处理；单字兜底过宽 | 错误码分级 + 单字兜底需先提到楼层 |
| 3.6.9 | `ElevatorView.onDraw` 每帧 new Path/渐变/RectF | 几何/Path/井道渐变**缓存**，仅尺寸变化重建 |
| 3.6.10 | 动画未在 detach 取消 | `onDetachedFromWindow` 取消 |
| 3.6.11 | `pressServo` 阻塞 loop 1.3s | 时间驱动状态机 |
| 3.6.12 | `xQueueSend` 返回值被忽略 | 检查并回执 `ERR:QUEUE_FULL` |

> 方案 B 同时**确认我们的固件“舵机会动”**（vs 方案 A 固件状态机死锁）——这一点在 v4 里进一步保持并强化（状态机 + 真回执）。
> 注：方案 B 自己也承认“从未在真机跑过”，故我们只吸收其**可验证的技术点**，不采纳其工程流程结论。

---

## 附录 A：参数速查

| 参数 | 值 |
|---|---|
| 楼层 | `1F`, `2F` |
| 广播名 | `ELEV-1F`, `ELEV-2F` |
| 舵机引脚 | D13=UP, D12=DOWN |
| 松开 / 按下角度 | 70° / 130°（出厂默认，现场串口标定后存 Flash） |
| 摆动时长 / 按住时长 | 350ms / 600ms |
| 服务 UUID | `0000ffe0-0000-1000-8000-00805f9b34fb` |
| 命令 UUID | `0000ffe1-0000-1000-8000-00805f9b34fb` |
| 状态 UUID | `0000ffe2-0000-1000-8000-00805f9b34fb` |
| RSSI 有效阈值 | `> -95 dBm` |
| RSSI 中位数窗口 / EMA α | 7 / 0.35 |
| 判层滞回 / 连胜 | 8dB / 3 次 |
| 节点过期 | 8s |
| 轿厢跟随 | 靠近哪层→轿厢移到哪层（纯视觉，不呼叫） |
| 呼叫触发 | 仅手动：▲/▼ 或语音（靠近不自动呼叫） |
| 1F/2F 按钮 | 选择呼叫目标（=手动选 ?: 靠近层）；靠近层变化时手动目标作废 |
| 3D 自转 | 关闭（仅手指拖动旋转）；静止不重绘 |
| App tick / 写超时 | 400ms / 3000ms |
| 重连退避 | 2/4/8/16/30s（上限 30s） |
| 语音重听延迟 | 250~1500ms（按错误码） |
| 固件分区 | Huge APP（Flash 35%） |

## 附录 B：安全声明
本项目用于开源项目演示。驱动舵机按压真实电梯按钮前，需确保不影响电梯运行与检修、不遮挡安全标识，建议在模型/模拟面板或工作人员在场时演示；严禁改装或短接电梯安全回路。
