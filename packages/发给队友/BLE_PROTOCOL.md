# ESP32 呼梯节点 · BLE 接口文档

> 面向：**iOS（校园室内导航 App）开发者**
> 目标：让导航 App **自动发现并连接 ESP32**，读到自己需要的楼层 / 方向信息，并下发“按下呼梯按钮”的命令。
> 本文档严格对应固件 **v5**：`firmware/elevator_2F/elevator_2F.ino`（**2F 板**）与
> `firmware/elevator_2F/elevator_2F.ino`（**2F 板**）。

---

## 0. 30 秒速览

每块 ESP32 就是电梯厅里的一个“电子手指”，它：

- 用 BLE **广播**自己的名字，如 `ELEV-2F`（代表“2F 的电梯呼叫节点”）；
- 广播里带着一个固定服务 UUID `FFE0`，你据此过滤；
- 提供一个**写特征** `FFE1`：你往里写 `UP` 或 `DOWN`，对应舵机就会真的去按“上行/下行”呼梯按钮；
- 提供一个**读/通知特征** `FFE2`：按下动作**真正做完后**，它会 NOTIFY 回一条 `2F|OK:UP` 给你确认。

```
  iOS App ──扫描──►  发现 "ELEV-2F" (RSSI -55)
          ──连接──►  服务 FFE0 → 特征 FFE1(写) / FFE2(通知)
          ──写 "UP" 到 FFE1──►  ESP32 舵机按下 2F 上行按钮
          ◄──NOTIFY "2F|OK:UP"──  （约 1.3 秒后，动作完成确认）
```

> **和“方式 B（走安卓 App 的 HTTP 中转）”的区别**：直连 BLE **不需要任何中间 App**，
> 而且你能直接拿到 **RSSI（信号强度）** 来做接近判断——这正好是导航 App 想要的。
> 如果你的导航 App 只在 iOS 上跑，**推荐用本文档的方式直连**。（HTTP 方式见 `API.md`，可两者并存。）

---

## 1. 设备 ↔ 按键对应关系（最重要的一张表）

**设备身份只由“广播名”决定**，格式固定为 `ELEV-<楼层>`：

> 📌 **本次演示部署**：井道是 **1F–4F** 四层，但只在 **2F 和 3F** 装了呼梯装置
> （这两层同时有上行+下行按钮，才能演示上下行；1F 只会有上行、4F 只会有下行）。
> 所以你只会扫到 `ELEV-2F` 和 `ELEV-3F` 两个节点，取**最近的**那个作为“你所在的层”。

| 广播名 | 楼层 | 服务 UUID | 命令 | 写特征 | 对应的物理按钮 |
|---|---|---|---|---|---|
| `ELEV-2F` | `2F` | `FFE0` | `UP` | `FFE1` | 2F 电梯厅的 **上行** 呼梯按钮 |
| `ELEV-2F` | `2F` | `FFE0` | `DOWN` | `FFE1` | 2F 电梯厅的 **下行** 呼梯按钮 |
| `ELEV-3F` | `3F` | `FFE0` | `UP` | `FFE1` | 3F 电梯厅的 **上行** 呼梯按钮 |
| `ELEV-3F` | `3F` | `FFE0` | `DOWN` | `FFE1` | 3F 电梯厅的 **下行** 呼梯按钮 |

补充对应（硬件层，供标定用）：

| 命令 | 舵机引脚 | 方向语义 |
|---|---|---|
| `UP` | GPIO13（D13） | 上行 |
| `DOWN` | GPIO12（D12） | 下行 |

所以对 iOS 来说：

- **“哪一层”** = 广播名去掉前缀 `ELEV-`（`ELEV-3F` → `3F`）；
- **“上还是下”** = 你写的命令是 `UP` 还是 `DOWN`；
- **“哪个电梯”** = 目前 1 个 ESP32 = 1 台电梯的某一层。若一间楼有多台电梯，
  参见 [§12 多电梯 / 楼栋标识](#12-可选扩展多电梯--楼栋标识)。

> ⚠️ 语义注意：`UP` 指的是**“这一层的上行呼梯按钮”**，不是“让轿厢上行”。
> 也就是它模拟的是人在 2F 按了“↑”。这正好和真人在电梯厅按按钮一样。

---

## 2. 广播（怎么发现 ESP32）

| 项 | 值 |
|---|---|
| 广播名（GAP name） | `ELEV-2F` / `ELEV-3F`（放在 **scan response** 里） |
| 广播内容 | 含 **16-bit 服务 UUID `FFE0`** |
| 可连接 | 是（connectable） |
| 发射功率 | +9 dBm（`ESP_PWR_LVL_P9`） |
| 配对 / 加密 | **无**（不需要配对、不需要绑定） |
| 连接后是否继续广播 | **是**（① 让你能一边连着、一边继续用 RSSI 判层 ② 让更多手机能连进来） |

**iOS 关键点**

- 扫描时用 `withServices: [CBUUID(string: "FFE0")]` 过滤，避免扫到一堆无关设备。
- 必须开 `CBCentralManagerScanOptionAllowDuplicatesKey: true`，否则**同一个设备只会回调一次**，
  你就拿不到持续变化的 RSSI（判层就废了）。
- 名字在 **scan response** 里，从 `advertisementData[CBAdvertisementDataLocalNameKey]` 取；
  `peripheral.name` 也可作为兜底。

> 若扫得到但没有名字：确认目标设备是 `ELEV-` 开头；名字没到说明 scan response 还没收到，
> `allowDuplicates=true` 时下一包就会带上。

---

## 3. GATT 结构

服务：**`FFE0`**（完整 128 位：`0000ffe0-0000-1000-8000-00805f9b34fb`）

| 特征 | UUID | 属性 | 方向 | 用途 |
|---|---|---|---|---|
| 命令 | `FFE1` | `Write` + `Write Without Response` | App → ESP | 下发 `UP` / `DOWN` / … |
| 状态 | `FFE2` | `Read` + `Notify` | ESP → App | 读初始状态 / 接收动作回执 |

- 状态特征带标准 **CCCD 描述符**（`00002902-…`）。iOS 用 `setNotifyValue(true, for:)` 即可，
  **不需要**自己写 CCCD。
- 无需请求更大的 MTU：所有报文都很短（< 20 字节）。
- **支持多台手机同时连接（固件 v5）**：每块 ESP32 最多 **3 台手机**同时连上并**各自独立控制**，
  见 [§13](#13-多台手机--多块板子同时使用v5)。
- 一台手机可以**同时连接 2F 和 3F 两块板子**（iOS 的 CoreBluetooth 天然支持多外设）。
- 回执（`OK:*`）是**广播式**的：所有已订阅的手机都会收到同一条通知。

> iOS 里 16-bit UUID 可以简写：`CBUUID(string: "FFE0")`，CoreBluetooth 会自动补全。

---

## 4. 数据格式

### 4.1 App → ESP（写 `FFE1`）

写入的是 **UTF-8 纯文本**（不是二进制、不是 JSON）。固件会 `trim()` 并**转大写**，
所以 `up` / ` UP ` 都等价于 `UP`。

| 写入内容 | 含义 | 是否立即回执 | 动作完成后的回执 |
|---|---|---|---|
| `UP` | 按**上行**呼梯按钮（D13） | 否 | `OK:UP` |
| `DOWN` | 按**下行**呼梯按钮（D12） | 否 | `OK:DOWN` |
| `ALL` | 上下行**都**按 | 是，立即 `OK:ALL` | 之后分别补 `OK:UP`、`OK:DOWN` |
| `S1` / `PRESS 1` | 等价于 `UP`（1 号舵机 = D13） | 否 | `OK:UP` |
| `S2` / `PRESS 2` | 等价于 `DOWN`（2 号舵机 = D12） | 否 | `OK:DOWN` |
| `PING` / `?` / `STATUS` | 探活 / 查状态 | 是，立即 `OK` | — |
| 其它任意内容 | 非法命令 | 是，立即 `ERR:BADCMD` | — |

> **推荐只用 `UP` / `DOWN`**，简单可靠。`S1`/`S2` 是为多舵机预留的。

### 4.2 ESP → App（`FFE2` 读 / 通知）

格式恒为：**`<楼层>|<内容>`**（UTF-8 文本，用 `|` 分隔两段）。

| 内容 | 何时出现 | 含义 |
|---|---|---|
| `READY` | 你**读**一次 `FFE2` 时（初始值） | 节点已就绪，等待命令 |
| `OK` | 你对 `PING`/`?`/`STATUS` 的回执 | 节点在线 |
| `OK:UP` | `UP` 动作**真正完成**后 | 2F/3F 上行按钮已按下 ✅ |
| `OK:DOWN` | `DOWN` 动作**真正完成**后 | 下行按钮已按下 ✅ |
| `OK:ALL` | 收到 `ALL` 时**立即** | 已受理，双轴即将动作 |
| `ERR:BADCMD` | 收到无法识别的命令 | 命令非法（大小写已归一，通常是拼写错） |
| `ERR:QUEUE_FULL` | 命令队列（深度 8）满 | 发太快了，请降速重试 |

示例：连到 `ELEV-3F` 后写 `DOWN`，约 1.3 秒后收到 `3F|OK:DOWN`。

> **重要**：`UP`/`DOWN` **不会**立即回执，只有舵机真正按压并收回后才发 `OK:UP`/`OK:DOWN`。
> 所以这条 NOTIFY 就是你给用户的**“操作成功”确认**（而不是“已发送”）。

### 4.3 动作时序（收到 `UP` 后）

```
App                         ESP32
 │   write "UP" 到 FFE1      │
 ├──────────────────────────►│  入队 → 该轴 pending=true
 │                           │
 │                           │  OUT  350ms   舵机从 20° 转到 150°（伸出按压）
 │                           │  HOLD 600ms   保持按住
 │                           │  IN   350ms   从 150° 回到 20°（收回）
 │  NOTIFY "2F|OK:UP"        │
 │◄──────────────────────────┤  （动作完成后才发）
 │        合计 ≈ 1.3s        │
```

- 从写入到收到 `OK:*`：**约 1.3 秒**。
- 同一轴在忙时，再发同一轴命令只会把 `pending` 置位，等它空闲后再执行（**每轴只保留 1 个待办**）。
- 队列深度 8；连发超过会收到 `ERR:QUEUE_FULL`。

---

## 5. iOS 接入步骤（CoreBluetooth）

1. **权限（Info.plist）**
   ```xml
   <key>NSBluetoothAlwaysUsageDescription</key>
   <string>用于连接电梯呼梯装置并按下呼梯按钮</string>
   ```
   （若支持 iOS 12 及以下，再加 `NSBluetoothPeripheralUsageDescription`。）
   可选后台：`<key>UIBackgroundModes</key><array><string>bluetooth-central</string></array>`

2. **创建 `CBCentralManager`**，等 `state == .poweredOn`。

3. **扫描**：`scanForPeripherals(withServices: [CBUUID(string:"FFE0")], options: [CBCentralManagerScanOptionAllowDuplicatesKey: true])`

4. **过滤 + 解析**：在 `didDiscover` 里取名字，`hasPrefix("ELEV-")` → 楼层 = 去掉前缀。

5. **连接**：对每个 `ELEV-*` 都 `connect(peripheral)`（两三层都连上，发命令零等待）。

6. **发现服务/特征** → 找到 `FFE1`(写) 和 `FFE2`(通知)。

7. **订阅通知**：`setNotifyValue(true, for: statusChar)`，再 `readValue(for: statusChar)` 读初始 `READY`。

8. **发命令**：`writeValue(Data("UP".utf8), for: cmdChar, type: .withResponse)`。

9. **等待回执**：在 `didUpdateValueFor` 里解析 `2F|OK:UP` → 给用户“已按下”。

> 真机才能用 BLE（模拟器不支持）。iOS 屏幕上会弹蓝牙授权，必须允许。

---

## 6. 可直接用的 Swift 参考实现

```swift
import CoreBluetooth

// MARK: - 协议常量
enum ElevatorBLE {
    static let service    = CBUUID(string: "FFE0")   // 服务
    static let cmdChar    = CBUUID(string: "FFE1")   // 写：UP / DOWN
    static let statusChar = CBUUID(string: "FFE2")   // 读 + 通知
    static let namePrefix = "ELEV-"                  // 广播名前缀
}

// MARK: - 一个节点的本地状态
struct ElevatorNode {
    let peripheral: CBPeripheral
    let name: String            // "ELEV-2F"
    let floor: String           // "2F"
    var rssi: Int
    var ready: Bool
    var cmdChar: CBCharacteristic?
    var statusChar: CBCharacteristic?
}

// MARK: - 中心设备管理器
final class ElevatorCentral: NSObject, CBCentralManagerDelegate, CBPeripheralDelegate {

    private var central: CBCentralManager!
    private(set) var nodes: [UUID: ElevatorNode] = [:]   // key = peripheral.identifier

    /// 收到节点回执：floor 如 "2F"，body 如 "OK:UP" / "READY" / "ERR:BADCMD"
    var onStatus: ((_ floor: String, _ body: String) -> Void)?
    /// 节点列表 / RSSI / ready 有变化
    var onNodesChanged: (() -> Void)?

    override init() {
        super.init()
        central = CBCentralManager(delegate: self, queue: .main)
    }

    /// 安全地就地修改某个节点的状态（Swift 字典里放 struct 的推荐写法）
    private func withNode(_ id: UUID, _ body: (inout ElevatorNode) -> Void) {
        guard var n = nodes[id] else { return }
        body(&n)
        nodes[id] = n
    }

    func startScanning() {
        guard central.state == .poweredOn else { return }
        // ⚠️ allowDuplicates 必须为 true，否则拿不到持续 RSSI
        central.scanForPeripherals(
            withServices: [ElevatorBLE.service],
            options: [CBCentralManagerScanOptionAllowDuplicatesKey: true]
        )
    }

    // MARK: CBCentralManagerDelegate
    func centralManagerDidUpdateState(_ central: CBCentralManager) {
        if central.state == .poweredOn { startScanning() }
    }

    func centralManager(_ central: CBCentralManager,
                        didDiscover peripheral: CBPeripheral,
                        advertisementData: [String: Any],
                        rssi RSSI: NSNumber) {
        // 名字在 scan response 里 → CBAdvertisementDataLocalNameKey
        let advName = advertisementData[CBAdvertisementDataLocalNameKey] as? String
        let name = advName ?? peripheral.name ?? ""
        guard name.hasPrefix(ElevatorBLE.namePrefix) else { return }
        let floor = String(name.dropFirst(ElevatorBLE.namePrefix.count))
        guard !floor.isEmpty else { return }

        var node = nodes[peripheral.identifier]
                  ?? ElevatorNode(peripheral: peripheral, name: name, floor: floor,
                                  rssi: RSSI.intValue, ready: false,
                                  cmdChar: nil, statusChar: nil)
        node.rssi = RSSI.intValue
        if node.rssi < -95 { return }            // 太远，忽略（可自行调阈值）
        nodes[peripheral.identifier] = node

        peripheral.delegate = self
        if peripheral.state == .disconnected {
            central.connect(peripheral, options: nil)   // 自动连接
        }
        onNodesChanged?()
    }

    func centralManager(_ central: CBCentralManager, didConnect peripheral: CBPeripheral) {
        peripheral.discoverServices([ElevatorBLE.service])
    }

    func centralManager(_ central: CBCentralManager,
                        didDisconnectPeripheral peripheral: CBPeripheral,
                        error: Error?) {
        withNode(peripheral.identifier) { $0.ready = false }
        onNodesChanged?()
        central.connect(peripheral, options: nil)        // 掉线自动重连
    }

    // MARK: CBPeripheralDelegate
    func peripheral(_ peripheral: CBPeripheral, didDiscoverServices error: Error?) {
        for s in peripheral.services ?? [] {
            peripheral.discoverCharacteristics(nil, for: s)
        }
    }

    func peripheral(_ peripheral: CBPeripheral,
                    didDiscoverCharacteristicsFor service: CBService,
                    error: Error?) {
        for c in service.characteristics ?? [] {
            switch c.uuid {
            case ElevatorBLE.cmdChar:
                withNode(peripheral.identifier) { $0.cmdChar = c }
            case ElevatorBLE.statusChar:
                withNode(peripheral.identifier) { $0.statusChar = c }
                peripheral.setNotifyValue(true, for: c)   // 订阅回执（自动写 CCCD）
                peripheral.readValue(for: c)              // 读初始 "<FLOOR>|READY"
            default:
                break
            }
        }
    }

    func peripheral(_ peripheral: CBPeripheral,
                    didUpdateValueFor characteristic: CBCharacteristic,
                    error: Error?) {
        guard characteristic.uuid == ElevatorBLE.statusChar,
              let data = characteristic.value,
              let text = String(data: data, encoding: .utf8) else { return }

        let parts = text.split(separator: "|", maxSplits: 1).map(String.init)
        let floor = parts.first ?? ""
        let body  = parts.count > 1 ? parts[1] : ""

        if body == "READY" { withNode(peripheral.identifier) { $0.ready = true } }
        onStatus?(floor, body)
        onNodesChanged?()
    }

    func peripheral(_ peripheral: CBPeripheral, didReadRSSI RSSI: NSNumber, error: Error?) {
        withNode(peripheral.identifier) { $0.rssi = RSSI.intValue }
        onNodesChanged?()
    }

    // MARK: 业务：叫电梯
    /// 让某层的某方向按钮被按下。返回是否成功下发（不等于“已按下”，看 onStatus 的 OK:*）。
    @discardableResult
    func call(floor: String, up: Bool) -> Bool {
        guard let node = nodes.values.first(where: { $0.floor == floor }),
              let ch = node.cmdChar,
              node.peripheral.state == .connected else { return false }
        let cmd = up ? "UP" : "DOWN"
        node.peripheral.writeValue(Data(cmd.utf8), for: ch, type: .withResponse)
        return true
    }

    /// 连接状态下主动刷新 RSSI（后台扫不到广播时很有用）
    func refreshRSSI() {
        for n in nodes.values where n.peripheral.state == .connected {
            n.peripheral.readRSSI()
        }
    }

    /// 最省事的判层：RSSI 最大的那层就是“你所在的层”
    func nearestFloor() -> String? {
        nodes.values.max(by: { $0.rssi < $1.rssi })?.floor
    }

    /// 最强信号值（用于“靠近到多少才浮出按钮”的判断，见 NAV_APP_UI_SPEC.md §3）
    func nearestRssi() -> Int {
        nodes.values.map { $0.rssi }.max() ?? -127
    }
}
```

使用：

```swift
let elev = ElevatorCentral()

elev.onNodesChanged = { [weak elev] in
    print("最近楼层 =", elev?.nearestFloor() ?? "?")
}

elev.onStatus = { floor, body in
    switch body {
    case "OK:UP":   print("✅ \(floor) 上行按钮已按下")
    case "OK:DOWN": print("✅ \(floor) 下行按钮已按下")
    case "ERR:BADCMD": print("⚠️ 命令非法")
    default: print("\(floor) → \(body)")
    }
}

// 用户点“呼叫电梯”
elev.call(floor: "3F", up: true)
```

---

## 7. 自动连接 / 重连 / 判层建议

- **自动连接**：`didDiscover` 里一看到 `ELEV-*` 就 `connect()`（参考实现已含）。
- **自动重连**：`didDisconnectPeripheral` 里再 `connect()`；固件断线后会**重新广播**，所以一定能连回来。
- **判层（你在哪一层）**：直接用 RSSI——**信号最强的那块 ESP32 所在的层 = 你所在的层**。
  - 建议对 RSSI 做**中位数 + 指数平滑**，再叠加 **3~5 dB 滞回**，避免两层间横跳；
  - 采样要密（`allowDuplicates=true`），否则反应迟钝；
  - 具体参数可参考本仓库安卓端的 `FloorJudge.kt` / `ElevatorDevice.kt`。
- **后台**：iOS 后台扫描会被系统降频、且 `allowDuplicates` 失效。后台想持续拿 RSSI，
  用**保持连接 + 定时 `readRSSI()`**（参考实现里的 `refreshRSSI()`）。
- **不要高频轮询**：命令走队列，发太快会 `ERR:QUEUE_FULL`。建议一次呼叫一次即可，
  收到 `OK:*` 再允许下一次。

---

## 8. 边界情况与坑

| 情况 | 表现 | 处理 |
|---|---|---|
| 命令拼写错误 | 收到 `ERR:BADCMD` | 只能是 `UP`/`DOWN`/`ALL`/`S1`/`S2`/`PING`/`?`/`STATUS` |
| 发太快 | `ERR:QUEUE_FULL` | 降速；等 `OK:*` 再发下一条 |
| 舵机正忙时又发同轴命令 | 不报错，稍后执行 | 每轴仅保留 1 个待办 |
| 走远/掉线 | `didDisconnectPeripheral` | 重新 `connect()`，等重新广播 |
| 信号 < -95 的节点 | 仍会被发现 | 自己按阈值忽略（参考代码用 -95） |
| 只看到名字看不到服务 | 服务 UUID 不在广播里？ | 本固件**广播里含 `FFE0`**，用 `withServices` 过滤即可 |
| 收不到通话 | 忘记 `setNotifyValue` | 必须先订阅 `FFE2` 的通知 |
| 第 4 台手机连不上 | 已达每板上限 3 台 | 断开一台，或参见 [§13](#13-多台手机--多块板子同时使用v5) |
| 模拟器 | 蓝牙不可用 | 必须真机 |

---

## 9. 用 nRF Connect / LightBlue 快速验证（5 分钟）

1. 上电 ESP32，串口 115200 应打印 `=== 电梯节点启动：ELEV-2F ===` 与 `[ble] 广播中`。
2. 手机装 **nRF Connect**（Android/iOS 都有）。
3. 扫描 → 找到 `ELEV-2F` → 点 **CONNECT**。
4. 展开服务 `FFE0`：
   - 读 `FFE2` 应得到 `2F|READY`；
   - 点 `FFE2` 的 **订阅**（三条箭头 / notify 图标）。
5. 点 `FFE1` → **写** → 输入 `UP` → 发送。
6. 约 1.3 秒后应看到 `FFE2` 弹出通知 `2F|OK:UP`；舵机摆动。
7. 发 `PING` → 立即回 `2F|OK`；发 `HELLO` → 回 `2F|ERR:BADCMD`。

---

## 10. 与「方式 B：HTTP 中转」的关系

| | 方式 A：**直连 BLE（本文档）** | 方式 B：走安卓 App 的 HTTP（`API.md`） |
|---|---|---|
| 平台 | iOS / Android / 任意 | 任意（但需一台安卓手机当中转） |
| 依赖 | **无**（只要 ESP 上电） | 需安卓 App 在前台 |
| 能否拿到 RSSI | ✅ 直接拿到 | ✅ 由 App 提供 |
| 判层/接近 | ✅ 自己算 | 由 App 算好给你 |
| 适合 | 导航 App 自己控呼梯 | 快速集成、不想写 BLE |

两者可以**同时用**。固件 **v5 已支持多台手机同时连接**（每块 ESP32 最多 3 台），
安卓 App 和 iOS App 可以同时连着同一块板子、互不影响。

---

## 11. 常量速查

```
广播名前缀      ELEV-           例：ELEV-2F / ELEV-3F
服务(UUID)      FFE0   (0000ffe0-0000-1000-8000-00805f9b34fb)
命令特征(写)    FFE1   (0000ffe1-0000-1000-8000-00805f9b34fb)   Write | WriteNR
状态特征(读+通知) FFE2 (0000ffe2-0000-1000-8000-00805f9b34fb)   Read | Notify, 带 CCCD
命令            UP | DOWN | ALL | S1 | S2 | PING | ? | STATUS
回执格式        <楼层>|<内容>     例：2F|READY 2F|OK:UP 2F|ERR:BADCMD
动作耗时        ≈1300 ms（OUT 350 + HOLD 600 + IN 350）
引脚            UP=D13(GPIO13)  DOWN=D12(GPIO12)
配对/加密       无
多连接          支持；每块板最多 3 台手机同时连（CONFIG_BTDM_CTRL_BLE_MAX_CONN=3）
```

---

## 12. 可选扩展：多电梯 / 楼栋标识

现在的名字只编码了楼层（`ELEV-2F`），**没编码“哪栋楼 / 哪台电梯”**。
如果一间楼有多台电梯、或多栋楼，建议按下述任一方式扩展（需改固件后重烧，当前未实现）：

- **方案 1（改名字）**：`ELEV-<楼栋><电梯><楼层>`，如 `ELEV-A1-3F`。
  - 好处：iOS 一眼解析出全部信息；
  - 代价：需同步通知本仓库的安卓 App 调整解析规则。
- **方案 2（不改名字，加“服务数据”）**：名字保持 `ELEV-3F`（向后兼容），
  额外在广播里塞一段自定义 service data / manufacturer data 作为设备 ID。
  - iOS 从 `advertisementData[CBAdvertisementDataServiceDataKey]` /
    `CBAdvertisementDataManufacturerDataKey` 读取，无需连接。
- **方案 3（不改广播，加 `INFO` 命令）**：连上后写 `INFO`，由 `FFE2` 回一条结构化串，
  如 `2F|INFO:ELEV=A1,FLOOR=2F,UP=1,DOWN=1`。
  - 受 ATT MTU 限制，字符串要短。

> 需要的话可以让本项目维护者实现其中一种；文档与固件会同步更新。

---

## 13. 多台手机 / 多块板子同时使用（v5）

**目标**：任意多台手机都能连上任意一块 ESP32、各自独立叫电梯；同一台手机可以同时连着 2F 和 3F。

### 13.1 能力与上限

| 能力 | 是否支持 | 说明 |
|---|---|---|
| 一台手机同时连 2F + 3F 两块板 | ✅ | iOS CoreBluetooth 天然支持多外设，`connect()` 两次即可 |
| 多台手机同时连同一块板 | ✅ | 固件 v5 已支持，回执广播给所有已订阅的手机 |
| 每块板上的手机数上限 | **3 台** | 硬上限，来自 ESP32 BLE 控制器 `CONFIG_BTDM_CTRL_BLE_MAX_CONN=3` |

> ⚠️ **3 台是硬上限**：想再多，需要**重新编译 ESP32 核心**（把
> `CONFIG_BTDM_CTRL_BLE_MAX_CONN` 调大），**光改这份 .ino 无效**（该值编译进了预编译库）。
> 演示场景（几台手机）用 3 台通常够；要更多请提前告知。

### 13.2 固件 v5 相对 v4 的改动（为什么之前不行的）

- **旧版（v4）**：用一个 `gConnected` 布尔记录“有没有人连着”。
  两台手机连着时，其中一台一断开就把这个布尔置 `false`，
  **另一台手机就再也收不到 `OK:*` 回执**了。
- **新版（v5）**：回执改为**广播式**——直接 `notify()` 给所有已订阅的客户端，
  由底层按 `conn_id` 自动跳过已断开的连接。任何一台手机的连/断都不再影响其它手机。
- 另外 v5 会在串口打印 `当前连接手机数：N`，方便现场确认到底连上了几台。

### 13.3 对 iOS 客户端的建议

- 对**每一块**需要控制的板子各 `connect()` 一次；在 `didDiscover` 里对每个 `ELEV-*` 都发起连接。
- 回执是**广播**的：如果你连着两块板，会分别收到 `2F|OK:UP` 和 `3F|OK:UP`——
  请**按通知里的楼层前缀区分**是哪块板回的，不要只看内容。
- 不要假设“只有我一个客户端”。**别用“发完命令就立刻假设成功”**的写法，
  以收到的 `OK:*` 通知为准。
- 多台手机同时操作同一块板时，固件的命令队列（深度 8）可能会满 → 会回 `ERR:QUEUE_FULL`，重试即可。

### 13.4 现场验证

1. 手机 A 连上 `ELEV-2F`，写 `UP` → 收到 `2F|OK:UP`。
2. **保持 A 连着**，手机 B 也连 `ELEV-2F`，写 `DOWN` → A、B **都应**收到 `2F|OK:DOWN`。
3. 手机 A 断开 → 手机 B 再写 `UP` → 手机 B **仍应**收到 `2F|OK:UP`（这是 v4 会失败、v5 已修复的关键点）。
4. 串口监视器应看到 `当前连接手机数：1 / 2 / …` 的变化。

---

*文档版本：对应固件 v5（`elevator_1F.ino` / `elevator_2F.ino`）。*
