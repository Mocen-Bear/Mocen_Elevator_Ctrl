# iOS 导航 App · 悬浮呼梯按钮 交互规格

> 面向：**iOS 导航 App 开发者（队友）**
> 前置：请先读 [`BLE_PROTOCOL.md`](BLE_PROTOCOL.md)（BLE 怎么连、怎么发 `UP`/`DOWN`）。
> 本文只讲**产品交互**：什么时候冒出按钮、按它发生什么、向左拖出什么。

---

## 0. 结论：能做到

演示场景（**一台电梯、井道 1F–4F，呼梯装置只在 2F / 3F**）所需的一切都已具备：

| 需要的能力 | 谁来提供 |
|---|---|
| 知道"我现在靠近哪一层" | BLE 扫描 `ELEV-2F` / `ELEV-3F` 的 **RSSI**，取最近的那个 |
| 知道"要按上行还是下行" | 导航 App 自己的路线：目的地楼层 vs 当前楼层 |
| 真的按下按钮 | 向最近那块板写 `UP` / `DOWN` |
| 按下的确认 | 等 `2F\|OK:UP` 通知 |
| 看到"轿厢现在在哪层" | **不是 BLE 给的**，见 §10（安卓侧摄像头 + 一个现成的 HTTP 接口） |

一句话：**最近的那块 ESP32 决定"按哪一层"，路线决定"上还是下"。**

> 📌 **为什么装置在 2F / 3F？** 井道做成 **1F–4F 四层**，但**只有 2F、3F 装了呼梯装置**——
> 因为真实楼里 1F（底层）只有"上行"按钮、4F（顶层）只有"下行"按钮，
> 只有**中间层同时有上行 + 下行**，才能把"上行/下行"两种呼梯都演示出来。
>
> 目的地可以是 **1F / 4F**（没有装置的层也能去）：目的地**只用来算方向**。
> 例：你在 2F、要去 4F → 按【2F 的上行】；你在 3F、要去 1F → 按【3F 的下行】。
> 你只会扫到 `ELEV-2F`、`ELEV-3F` 两个节点。（上/下按钮的物理引脚见 `BLE_PROTOCOL.md` §1。）

---

## 1. 效果总览

```
  ┌──────────────────────────────────────────────────┐
  │  导航 App（地图/AR 全屏）                          │
  │                                                  │
  │                                                  │
  │                            ┌──────────┐  ◄── 靠近 ESP32
  │                            │   ▲ 2F   │      自动浮现
  │                            │  呼梯    │      （右侧边缘，
  │                            └──────────┘        可拖动）
  │                                 │
  │              向左拖 ────────────┘        （>60pt 松手即进入）
  │                                 ▼
  │   ┌────────────────────────────────────────────┐
  │   │  ← 地图        电梯呼叫              ← 全屏页 │
  │   │                                            │
  │   │      ┌────────┐  ┌──────┐                  │
  │   │      │  2F    │  │  1F  │  ← 轿厢现在在这层 │
  │   │      └────────┘  └──────┘    （甲梯 / 乙梯） │
  │   │      （两台井道并排，轿厢位置用蓝牙判层）     │
  │   │                                            │
  │   │        1F   2F   3F   4F   ← 呼叫目标楼层    │
  │   │           ▲ 上行     ▼ 下行                 │
  │   │      去 4F → 按 2F 的上行 · 在线 2/2         │
  │   └────────────────────────────────────────────┘
  └──────────────────────────────────────────────────┘
```

三种状态：

1. **未靠近** → 什么都不显示，安静。
2. **靠近某层电梯厅** → 右侧浮出一个小圆钮，标注目标层与方向（如 `▲ 2F`）。
3. **向左拖动按钮** → 进入**全屏电梯页**（就是安卓 App 主界面那一套）：
   井道（并排画两台也行）+ **轿厢现在在哪层（= 你自己的蓝牙判层）** + 楼层键 + ▲/▼ + 底部状态；
   页面上有 **`← 地图`** 退回，按系统返回键也能回地图。

---

## 2. 核心：**该按哪一层的哪个按钮**（先算清楚）

电梯厅的呼梯按钮按的是**「你所在的这一层」**，方向指向**你的目的地**：

```
正在 2F，要去 3F  →  按【2F 的上行】  → ELEV-2F 写 "UP"
正在 3F，要去 2F  →  按【3F 的下行】  → ELEV-3F 写 "DOWN"
正在 2F，要去 2F  →  不需要坐电梯（不显示按钮）
```

> ⚠️ 最容易搞错的一点：**按的层是"你当前所在层"，不是目的地层**。
> 目的地只决定"上还是下"。这正是模拟真人站在电梯厅按按钮的行为。

判定函数（可直接抄）：

```swift
/// 从"我在哪层 + 要去哪层"推导出"该按哪块板、哪个方向"
struct CallPlan {
    let callFloor: String   // 要发给哪块 ESP32（= 当前楼层）
    let up: Bool            // true=上行  false=下行
    let destFloor: String   // 目的地（仅用于显示）
}

func makePlan(currentFloor: String, destFloor: String) -> CallPlan? {
    func num(_ s: String) -> Int? { Int(s.replacingOccurrences(of: "F", with: "")) }
    guard let c = num(currentFloor), let d = num(destFloor), c != d else { return nil }
    return CallPlan(callFloor: currentFloor, up: d > c, destFloor: destFloor)
}
```

- **`currentFloor` 怎么来？** 优先用 BLE：`ELEV-*` 里 **RSSI 最大**的那块就是当前层（见 §3）。
  如果 BLE 暂时判不出来，可以先用导航地图已知的楼层兜底（见 §8）。
- **`destFloor` 怎么来？** 导航 App 的路线里本来就有（用户选的目的地）。
- 返回 `nil` 就表示"这趟不用坐电梯"→ 不显示按钮。

发给固件时（对应 `BLE_PROTOCOL.md`）：

```swift
elev.call(floor: plan.callFloor, up: plan.up)   // 内部写 "UP" 或 "DOWN"
```

---

## 3. 什么时候浮出按钮（接近检测）

**判据 = 最近的那块 ESP32 够近。** 用 RSSI，但**别用裸值**（抖得厉害），照下巴这套：

```
每收到一次广播：
  rssi中位数(窗口5)  →  EMA平滑(α=0.5)  →  取两层里最大的 = nearestRssi
```

然后加 **滞回**，避免按钮在边缘疯狂闪：

| 事件 | 条件（演示可调） |
|---|---|
| **浮出按钮** | `nearestRssi > -70 dBm` 持续 ≈0.5 s |
| **保持显示** | `nearestRssi > -80 dBm`（比浮出门槛低 10 dB，形成滞回） |
| **自动收起** | `nearestRssi < -80 dBm` 持续 ≈1.5 s |

（这套"中位数 + EMA + 滞回"就是安卓端 `FloorJudge.kt` 的思路，可直接照搬参数。）

**演示环境特别注意**：只连/只判 `ELEV-2F`、`ELEV-3F` 两块，取最近的即可；
不要因为扫到别的 BLE 设备而误触发 —— 一定要按 `name.hasPrefix("ELEV-")` 过滤。

> iOS 提示：`allowDuplicates: true` 才拿得到持续 RSSI（见 `BLE_PROTOCOL.md` §2）。
> 若 App 在后台，扫描会被降频，改用"保持连接 + 定时 `readRSSI()`"。

---

## 4. 悬浮按钮的状态机

```
        nearestRssi > -70 (0.5s)
  ┌─────────────┐ ─────────────────────► ┌─────────────┐
  │   HIDDEN     │                        │   ARMED      │  小圆钮显示
  │  （不显示）   │ ◄───────────────────── │  "▲ 2F 呼梯" │
  └─────────────┘  nearestRssi < -80(1.5s)└──────┬──────┘
                                                │ 点按
                                                ▼
                                          ┌─────────────┐
                                          │  CALLING     │  转圈/变灰，禁止连点
                                          └──────┬──────┘
                                    收到 "2F|OK:UP" │ 或超时(>3s)/ERR
                                                ▼
                                    ┌───────────────────────┐
                                    │ SUCCESS ✅ / FAILED ⚠️  │ 约 2s 后回到 ARMED
                                    └───────────────────────┘
```

要点：
- **点一下就发命令**，不需要二次确认（这是"一键"的意义）。
- **发送中禁止重复点击**（固件队列深度 8，连点会 `ERR:QUEUE_FULL`）。
- 成功以**收到 `OK:*` 通知**为准，不是"写出去就算成功"。
- 失败/超时给个轻提示，按钮回到可点状态。

---

## 5. 交互细节

| 手势 | 行为 |
|---|---|
| **点按**小圆钮 | 立即按计划呼叫（发 `UP`/`DOWN`），显示"正在呼叫…" |
| **向左拖** | 进入**全屏电梯页**（跟手，>60pt 松手即进入，否则弹回） |
| **全屏页里的 `← 地图` / 系统返回键** | 回到地图（退回小圆钮） |
| 全屏页里 ▲ / ▼ | 手动呼叫（用"呼叫目标楼层" + 指定方向） |
| 全屏页里楼层键 `2F` / `3F` | 切换“呼叫目标”楼层；`1F` / `4F` 无装置、置灰（本演示） |
| 全屏页里层显 | **轿厢现在在哪层**（甲梯 / 乙梯各一个；怎么来的见 §10）+ 在线数 |

按钮上的文字建议直接写清楚，降低理解成本：

```
 ▲ 2F        往上走（目的地更高）
 ▼ 3F        往下走
 2F 呼梯      无法确定方向时的兜底
```

---

## 6. iOS 实现要点

**浮层方式**：把悬浮按钮放在 `ZStack` 最上层（或 `UIWindow` 上挂一个 `UIWindowLevel` 更高的容器），
保证它在 AR/地图之上、又不吃地图手势（只在按钮自身响应手势）。

**SwiftUI 骨架（示意，可直接改）**：

```swift
import SwiftUI

final class ElevatorViewModel: ObservableObject {
    @Published var nearestFloor: String?     // "2F" / nil
    @Published var buttonUp: Bool = true     // 按钮显示的方向
    @Published var destFloor: String?        // 来自导航路线
    @Published var phase: Phase = .hidden
    enum Phase { case hidden, armed, calling, success, failed }

    var plan: CallPlan? {
        guard let cur = nearestFloor, let dst = destFloor else { return nil }
        return makePlan(currentFloor: cur, destFloor: dst)
    }
    var shouldShow: Bool { plan != nil && (phase == .armed || phase == .calling) }
}

struct CallFloatingButton: View {
    @ObservedObject var vm: ElevatorViewModel
    let onCall: (CallPlan) -> Void          // → elev.call(floor:up:)

    @State private var dx: CGFloat = 0       // 拖动位移（只允许向左 = 负）
    @State private var expanded = false

    var body: some View {
        if vm.shouldShow || expanded {
            HStack {
                Spacer()
                Group {
                    if expanded {
                        FullScreenElevatorPage(vm: vm)    // ← 全屏电梯页（就是安卓 App 主界面那一套）
                            .transition(.move(edge: .trailing))
                    } else {
                        smallButton
                    }
                }
                .padding(.trailing, 12)
            }
            .animation(.spring(response: 0.3, dampingFraction: 0.8), value: expanded)
        }
    }

    private var smallButton: some View {
        let plan = vm.plan
        return VStack(spacing: 2) {
            Image(systemName: plan?.up == true ? "arrow.up" : "arrow.down")
                .font(.system(size: 18, weight: .bold))
            Text(plan?.callFloor ?? "--")
                .font(.system(size: 15, weight: .bold))
        }
        .frame(width: 62, height: 62)
        .background(Circle().fill(plan?.up == true ? Color.green : Color.orange))
        .foregroundColor(.white)
        .shadow(radius: 6)
        .offset(x: dx)
        // 点按 = 呼叫
        .onTapGesture { if let p = plan { onCall(p) } }
        // 向左拖 = 展开
        .gesture(
            DragGesture()
                .onChanged { v in dx = min(0, v.translation.width) }
                .onEnded { v in
                    if v.translation.width < -60 { expanded = true; dx = 0 }
                    else { withAnimation { dx = 0 } }
                }
        )
    }
}
```

**把 BLE 事件接进 ViewModel**（配合 `BLE_PROTOCOL.md` §6 的 `ElevatorCentral`）：

```swift
elev.onNodesChanged = { [weak vm] in
    let nearest = elev.nearestFloor()          // RSSI 最大的那块
    vm?.nearestFloor = nearest                 // 里面做中位数+EMA+滞回
    vm?.updatePhase(nearestRssi: elev.nearestRssi())
}
elev.onStatus = { floor, body in
    switch body {
    case "OK:UP", "OK:DOWN": vm?.phase = .success
    case "ERR:BADCMD", "ERR:QUEUE_FULL": vm?.phase = .failed
    default: break
    }
}
```

**全屏页里的 3D 井道（可选）**：安卓端那套 3D 井道是纯软件渲染，数学可以移植到
iOS（用 **SceneKit** 或 SwiftUI `Canvas` 重画）。演示不追求 3D 的话，
全屏页用"大字层显（甲/乙）+ ▲/▼ + 靠近楼层"就已经达到"像安卓 App 的界面"的效果。
（安卓端的做法是**两台井道并排**，各画各的轿厢；网页预览里井道是简化方块。）

---

## 7. 现场可调参数

| 参数 | 建议初值 | 作用 |
|---|---|---|
| 浮出门槛 | `nearestRssi > -70 dBm` | 越靠近越灵敏，越小越迟 |
| 收起门槛 | `< -80 dBm` | 与浮出门槛差 10 dB 形成滞回 |
| 保持时长 | 浮出 0.5 s / 收起 1.5 s | 防抖 |
| RSSI 窗口 | 5 | 中位数去毛刺 |
| EMA α | 0.5 | 平滑系数 |
| 拖拽展开阈值 | 60 pt | 松手判定 |
| 呼叫超时 | 3 s | 超过就判失败回到可点 |

> 现场如果觉得"太不灵敏"→ 把浮出门槛放宽到 `-75`；"太容易误触发"→ 收紧到 `-65`。

---

## 8. 边界情况

| 情况 | 建议行为 |
|---|---|
| 两层信号都很弱/都没扫到 | 不显示按钮 |
| 两层信号接近（难分最近） | 用**导航地图已知的当前楼层**做仲裁，避免横跳 |
| 已在目的地楼层（`c == d`） | `makePlan` 返回 `nil` → 不显示按钮 |
| 没有导航计划（用户随意走） | 可选：显示兜底"2F 呼梯"按钮，用手动 ▲/▼ |
| 发送后 3 s 没收到 `OK:*` | 判失败，提示"重试"；按钮回到可点 |
| 用户连点按钮 | 发送中禁用（`phase == .calling`） |
| 多台手机同时在用 | 正常（固件 v5 支持，见 `BLE_PROTOCOL.md` §13）；以收到的 `OK:*` 为准 |
| 走远了按钮还赖着 | 收起门槛 + 1.5 s 去抖，超时自动隐藏 |

---

## 9. 与 BLE 协议的分工

- **`BLE_PROTOCOL.md`**：怎么连板子、写 `UP`/`DOWN`、读回执、拿 RSSI。**设备层**。
- **本文档 `NAV_APP_UI_SPEC.md`**：**应用层**——什么时候显示按钮、按了发什么、拖出来什么界面。

两份合起来，队友就能把"靠近电梯 → 一键呼梯 → 进全屏电梯页"这套做到导航 App 里。

---

## 10. 全屏页里的「轿厢现在在哪层」从哪来

**就用你自己已经在读的蓝牙信号，不需要额外接口、也不需要联网。**

你的 App 本来就在靠"**哪块板最近**"判断**用户在哪一层**（见 `BLE_PROTOCOL.md` 的 RSSI 判层）。
用户**坐在轿厢里**的时候，"**用户在哪层**"就是"**轿厢在哪层**" ——
把那个楼层直接显示在全屏页上就行。

> （我们安卓版是这么做的，但 **v9 起层显框里只放一个大数字，数字下面不再写小字** ——
> "这个数是判出来的、还是摄像头读到的"只在**接口的 `carSource`**（`near` / `camera` / `manual`）里说清楚。
> 你那边怎么标随你：在数字下面标一行 `蓝牙判层` 也不会错，**只是别把它说成"摄像头读到的"**。）

规则：

- 装置只装在 **2F / 3F** → **只有这两层判得出来**；路过 1F / 4F 时保持上一次的判层结果，
  或者显示 `--`（**别编一个数**）。
- 判层要防抖（`BLE_PROTOCOL.md` 里那四条：中位数窗口 + EMA + 滞回 + 只认 `ELEV-` 前缀），
  别让数字乱跳。
- 用户没坐电梯（站在厅里）时，这个数就是"用户所在层"，一样能显示。

> 另一条路 —— **摄像头读电梯厅那块屏**（`IOS_INTEGRATION.md` + `API.md` + `monitor_live.html`，
> 一条走 Wi-Fi 的 JSON）—— **现在先搁置**。那三份留在包里备用，**现在不用做**。

---

*规格版本：v1.4（配合固件 v5）。*

*v1.3 → v1.4 的变化：**§10 更正一处和我们对不上的说法** —— 原来写"我们安卓版数字下面写 `蓝牙判层`"，
但安卓 App **v9 起层显框里只有一个大数字、下面不写小字**（"要干净"），来源改由**接口 `carSource`** 说明。*
*文里顺带说清：**标不标那一行随你，但别把它说成"摄像头读到的"**。协议、命令、判层规则一个字没动。*

*v1.0 → v1.1 的变化：「向左拖」从"展开小面板"改成"进**全屏电梯页**"（页内含甲/乙两台轿厢位置），并补上第 10 节「轿厢楼层从哪来」。*

*v1.1 → v1.2 的变化：第 10 节指向新增的 [`IOS_INTEGRATION.md`](IOS_INTEGRATION.md)（接口字段 / Swift 示例 / 苹果 `Info.plist` 两个开关 / 复用那个真 3D 井道）。*

*v1.2 → v1.3 的变化：**第 10 节改口径** —— 「轿厢在哪层」不再要求走 Wi-Fi 读安卓那台手机，
改成**用你自己的蓝牙判层**（用户坐在轿厢里时，"用户在哪层"就是"轿厢在哪层"）；摄像头那条路先搁置。*
