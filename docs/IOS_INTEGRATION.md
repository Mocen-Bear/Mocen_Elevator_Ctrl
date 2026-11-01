# iOS 接入说明：看「轿厢在哪层」+ 复用那个真 3D 井道

> 给谁看：**iOS 导航 App 队友**（以及他用的 AI agent）。
> **按电梯**那条线（蓝牙）看 [`BLE_PROTOCOL.md`](BLE_PROTOCOL.md)；
> **悬浮按钮 / 全屏电梯页**看 [`NAV_APP_UI_SPEC.md`](NAV_APP_UI_SPEC.md)；
> 这份只管 **「轿厢现在在哪层」** 和 **「那个 3D 井道怎么复用」**。
>
> ⚠️ **现在先不做这份**：它是「**轿厢楼层改走 Wi-Fi、读安卓那台手机**」的**备选方案**
> （配套 [`API.md`](API.md) 和 `monitor_live.html`）。
> 主路见 [`NAV_APP_UI_SPEC.md`](NAV_APP_UI_SPEC.md) §10 —— **「轿厢在哪层」就用你自己的蓝牙判层**，
> 全程不需要联网、也不需要第二台手机。这份留着备用（以后可能启用）。

---

## 一、一句话

两条线**互不依赖**，可以分别做、分别坏：

| 你要做的事 | 走什么 | 谁提供 |
|---|---|---|
| **按电梯**（发 `UP`/`DOWN`） | **蓝牙 BLE 直连 ESP32** | 你 iPhone 自己连，见 `BLE_PROTOCOL.md` |
| **看轿厢在哪层**（**这份，现已搁置**；现在改用你自己的蓝牙判层，见 `NAV_APP_UI_SPEC.md` §10） | **Wi-Fi HTTP** 读安卓手机上的一个网址 | 我们安卓侧那台**监控手机** |
| **那个 3D 井道** | 一个现成的网页（也能塞进你 App） | 见 [第三节](#三想要那个真-3d-井道两条路) |

- **只有「用摄像头读数字」这一步必须是安卓**（安卓相机接口 + Kotlin 识别），所以现场要有一台**安卓手机**架在电梯厅前面当「监控」。
- 你 iPhone **不用装我们任何东西、不用同一套代码**：读一个普通 JSON 就行。
- **两台设备只要连同一个 Wi-Fi / 同一个热点**（不需要配对、不需要蓝牙）。
- **监控那台关掉了，按电梯照样好使**。

---

## 二、读「轿厢在哪层」

### 2.1 地址

```
http://<监控手机的IP>:8899/api/status
```

- 安卓 App **主界面最底下那行小字**写着这个地址，形如 `外部接口 http://192.168.1.23:8899`，现场抄下来。
- `GET`、无参数、**只读**。
- **1~2 秒读一次**就够（我们内部也是 1.5 秒）。

### 2.2 返回长什么样（真实例子）

```json
{
  "ok": true,
  "api": 1,
  "near": "2F",
  "target": "3F",
  "car": "3F",
  "carSource": "camera",
  "car2": "1F",
  "floors": ["2F", "3F"],
  "shaftFloors": ["1F", "2F", "3F", "4F"],
  "nodes": [
    { "floor": "2F", "address": "AA:BB:CC:DD:EE:01", "name": "ELEV-2F", "rssi": -70, "ready": true },
    { "floor": "3F", "address": "AA:BB:CC:DD:EE:02", "name": "ELEV-3F", "rssi": -55, "ready": true }
  ]
}
```

### 2.3 字段表（打 ★ 的必须看）

| 字段 | 可能的值 | 意思 / 你要怎么用 |
|---|---|---|
| ★ `car` | `"3F"` / `null` | **甲梯轿厢在哪层**（全屏页那个大数字）。`null` = 没有数 |
| ★ `carSource` | `"camera"` `"manual"` `"near"` `null` | **这个数是怎么来的** —— 见下表，**别跳过** |
| ★ `car2` | `"1F"` / `null` | **乙梯轿厢在哪层**。它**只会是真读数**（`null` = 没读到） |
| `near` | `"2F"` | 我们按蓝牙 RSSI 判的「**你**靠近哪层」—— **现在这条路就是轿厢楼层**（`car` 会等于它） |
| `target` | `"3F"` | 我们页面上选的目的层（可忽略） |
| `floors` | `["2F","3F"]` | 装了呼梯装置的楼层 |
| `shaftFloors` | `["1F","2F","3F","4F"]` | 井道有哪几层（画井道用） |
| `nodes[]` | … | 每块装置：`floor` / `address` / `name` / `rssi` / `ready`（你直连蓝牙就有，可忽略） |

`carSource` 的四种值：

| 值 | 什么意思 | 你该怎么显示 |
|---|---|---|
| `camera` | 监控手机**用摄像头真读到**电梯厅那块屏 | **真的** → 大数字显示它，可标「摄像头」 |
| `manual` | 我们现场**手动指定**的（摄像头读不准时的兜底） | 也是真的 → 显示它，可标「现场指定」 |
| `near` | **蓝牙判层**：拿「你靠近哪层」当轿厢所在层（**现在的默认口径** —— 用户坐在轿厢里时，两者是一回事） | 显示它，标「**蓝牙判层**」；别说成"摄像头读到的" |
| `null` | 没有读数 | 显示 `--` / 「未知」 |

### 2.4 三条诚实规则（很重要）

1. **没有数就显示 `--`，不要编一个数。**
2. **`carSource == "near"` = 用蓝牙判层顶上来的** —— 用户坐在轿厢里时，这就是轿厢所在层；
   显示时标「**蓝牙判层**」，**别把它说成"摄像头读到的"**（那是另一条已经搁置的路）。
3. 读数**超过 180 秒没更新就算过期**（`car` 会退回 `near` 或 `null`）—— 想更严谨就让显示变灰 / 标「旧数据」。

### 2.5 Swift 示例（每 1.5 秒读一次）

> 这是个能直接用的骨架，并发风格按你项目里那套改一下即可。

```swift
import Foundation

struct CarStatus: Decodable {
    let car: String?        // 甲梯
    let car2: String?       // 乙梯
    let carSource: String?  // camera / manual / near / nil
}

/// 每隔 1.5 秒读一次「监控手机」，把「轿厢在几层」变成能绑到 UI 的状态。
@MainActor
final class CarFloorWatcher: ObservableObject {
    @Published var carA: String?      // 甲梯（只在真读数时有值）
    @Published var carB: String?      // 乙梯
    @Published var isReal = false     // true = 摄像头 / 现场指定 的**真**读数
    @Published var note = "未连接"     // 给 UI 显示一行小字

    // ⚠️ 演示时改成监控手机的实际 IP（我们主界面底下那行小字）
    private let base = URL(string: "http://192.168.1.23:8899")!
    private var timer: Timer?

    func start() {
        guard timer == nil else { return }
        Task { await poll() }
        timer = Timer.scheduledTimer(withTimeInterval: 1.5, repeats: true) { _ in
            Task { @MainActor in await self.poll() }
        }
    }

    func stop() { timer?.invalidate(); timer = nil }

    private func poll() async {
        var req = URLRequest(url: base.appendingPathComponent("api/status"))
        req.timeoutInterval = 1.5
        req.cachePolicy = .reloadIgnoringLocalCacheData
        do {
            let (data, _) = try await URLSession.shared.data(for: req)
            let s = try JSONDecoder().decode(CarStatus.self, from: data)
            switch s.carSource {
            case "camera": carA = s.car; isReal = true;  note = "摄像头"
            case "manual": carA = s.car; isReal = true;  note = "现场指定"
            case "near":   carA = s.car; isReal = false; note = "蓝牙判层（你靠近这层）"  // 用户坐在轿厢里时 = 轿厢所在层
            default:       carA = nil;   isReal = false; note = "没读到"
            }
            carB = s.car2            // 乙梯只会是真读数；读不到就是 nil
        } catch {
            carA = nil; carB = nil; isReal = false; note = "连不上监控手机"
        }
    }
}
```

绑到全屏电梯页上（示意）：

```swift
@StateObject private var car = CarFloorWatcher()

// 全屏电梯页里那个大数字
Text(car.carA ?? "--")
    .font(.system(size: 56, weight: .bold, design: .rounded))
    .opacity(car.isReal ? 1 : 0.45)     // 不是真读数就灰一点
Text(car.note).font(.footnote).opacity(0.6)

.onAppear   { car.start() }
.onDisappear { car.stop() }
```

### 2.6 先在 iPhone 上手动验一遍（最省事的排查）

用 iPhone 的 **Safari** 直接打开：

```
http://192.168.1.23:8899/api/status          ← 换成监控手机的 IP
```

- 能看到一段 JSON → **网络这条路通了**，剩下就是你 App 的事。
- 看不到 → 先查三件事：
  1. 两台设备是不是**同一个 Wi-Fi**（路由器有 2.4G / 5G 两个名字时最容易踩）；
  2. 地址抄错没有（要带 `http://`，端口 `8899`）；
  3. 监控手机上 App 还开着吗、还在「摄像头读楼层」那一页吗。

---

## 三、想要那个「真 3D 井道」？两条路

### A. 把现成的一页塞进你 App（推荐，几乎零工作量）

这个包里给了你一份 **`monitor_live.html`**：它和安卓 App 里那两根井道**同一份数学**
（玻璃井壁、导轨、厅门框、呼梯面板、曳引机、对重、曳引绳、楼层标签，**可拖动旋转**，
1F / 4F 半截暗影，轿厢上下连续滑动）。

- 用 `WKWebView` 加载它就行（`loadFileURL(_:allowingReadAccessTo:)`）；
  **它自己每 1.5 秒轮询** `/api/status`，**你不用写轮询代码**。
- 页面上那个地址框，你可以改成默认值（改一行 JS 里的默认地址），或者让用户在页面上填。
- 已经替你处理好的：
  - 连不上 → 红点 + 数字 `--` + **井道里根本不画轿厢**（不瞎编）；
  - `carSource == "near"` → 标「**蓝牙判层**」（用户坐在轿厢里时，这就是轿厢所在层）；
  - 甲 = 左、乙 = 右；`car2` 为 `null` 时右边是 `--`。
- 它也能**纯当网页用**：安卓 / iPhone 的浏览器、电脑浏览器都能打开，不依赖你的 App
  （只依赖那台监控手机在跑）。
- ⚠️ WebView 里那条 http 请求**同样受苹果限制** —— 第四节那两个开关一样要加。

### B. 用 Swift 原生重画（更好看，但要自己写一遍）

同一份数学（尺常量、焦距/俯仰/偏航投影、面按深度排序、亮度用的光向量）写在
[`SHAFT_MODEL.md`](SHAFT_MODEL.md)（在 `发给队友_透视井道` 那个包里），
`monitor_live.html` 的源码也是同一套，可以对照着抄。

---

## 四、苹果默认会拦你的三个地方

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 地址明明对，就是连不上（日志报 ATS） | iOS 默认**只允许 https**，明文 `http://` 会被系统掐掉 | 在 `Info.plist` 里加 `NSAppTransportSecurity` → `NSAllowsLocalNetworking = true`（苹果专门给"局域网明文"准备的开关）。要是还被拦，临时再加 `NSAllowsArbitraryLoads = true` 兜底（**仅演示用，别上架**） |
| 第一次连局域网弹框 / 请求静默失败 | iOS 14 起要用户**允许访问本地网络** | `Info.plist` 加 `NSLocalNetworkUsageDescription` = 一句用途说明（比如「显示电梯轿厢楼层」），弹框时点「允许」 |
| 蓝牙一调用就崩 | 没写蓝牙用途说明 | `Info.plist` 加 `NSBluetoothAlwaysUsageDescription`（见 `BLE_PROTOCOL.md` §5） |

> WebView 里那条 http 请求**同样受第一个开关管** —— 加了才不会「页面打开是白的、数字永远 `--`」。

---

## 五、演示前 5 分钟对表

1. 两台设备**连同一个 Wi-Fi**（或同一个手机热点）。
2. **安卓监控手机**：App 开着、停在「摄像头读楼层」页、对着电梯厅那块红字屏、
   屏幕超时改成"永不"（或开发者选项"充电时屏幕不休眠"）、插着电、架着不动。
3. 抄下它的 `外部接口 http://IP:8899`。
4. **iPhone 的 Safari** 打开这个地址 → 出 JSON。
5. 你 App 里的大数字开始跟着变；读不到就 `--`（**允许空着，不可以编数**）。
6. 按电梯照旧走蓝牙 —— **监控那台关掉都不影响按电梯**。

---

## 六、边界（说清楚，免得踩）

- 这个接口**只读**，**不能叫电梯**。叫电梯永远走蓝牙：写 `UP`/`DOWN`，等回执 `2F|OK:UP`。
- **甲 / 乙 是靠摄像头画面里的「左边 / 右边」分的**（左 = 甲、右 = 乙）。
  现场牌子和我们约定反了的话，**我们现场改**（不用你动）。
- 一屏只读到一个数时，只有 `car`（甲），`car2` 是 `null`。
- 接口**没有鉴权、没有加密**（局域网演示用），**别把它暴露到公网**。
- 「我们不知道轿厢真实位置」这件事本身是硬件的限制（那两块板**看不到轿厢**）：
  有 `camera` 读数就是摄像头**真的看见了**；没读数就是**真的不知道** —— 所以才有 `--`。

---

*文档版本：v1（随 `发给队友` 这个资料包一起发）。*
