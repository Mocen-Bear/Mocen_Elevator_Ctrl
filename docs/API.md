# 电梯呼叫 App —— 对外接口（给队友的导航 App 用）

> **先看这个：如果你的 App 能直接连蓝牙，请优先用 [`BLE_PROTOCOL.md`](BLE_PROTOCOL.md) 直连 ESP32。**
> 本文的 HTTP 接口适合“不想写 BLE、或想复用本 App 已算好的楼层/信号”的场景（需要一个安卓手机当前台中转）。
> 两者可同时存在。
>
> ⚠️ **现在先不做这份**：它是「**轿厢楼层改走 Wi-Fi、读安卓那台手机**」的**备选方案**
> （配套 [`IOS_INTEGRATION.md`](IOS_INTEGRATION.md)）。主路见 [`NAV_APP_UI_SPEC.md`](NAV_APP_UI_SPEC.md) §10：
> **「轿厢在哪层」就用你自己的蓝牙判层**，全程不需要联网。

本 App（Android，`com.mocen.elevator`）在局域网里开了一个**最小 HTTP 接口**，
任何设备上的任何程序都能调用它去“叫电梯”，例如你队友的 iOS 室内导航 App。

> 为什么用 HTTP：两个 App 一个 iOS 一个 Android，跑在不同手机上，没法直接进程间调用；
> HTTP + JSON 是跨平台里最省事、最通用、最好调试的方式。零第三方库，纯 `ServerSocket`。

---

## 1. 怎么连

1. **两台手机接同一个 Wi-Fi**（或同一个热点）。
2. 打开电梯 App，**保持在前台**（接口随 Activity 生命周期启停）。
3. 电梯 App 底部会显示接口地址，形如：

   ```
   外部接口 http://192.168.1.23:8899 · 未连接装置
   ```

   也可以在 logcat 里看：`adb logcat -s ElevatorApp` → `HTTP 接口已开启：http://...:8899`
4. 用这个地址访问，端口默认 **8899**。

---

## 2. 接口一览

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/api/ping` | 探活，确认是电梯 App |
| GET | `/api/floors` | 可呼叫的楼层（= 装了装置的层：`2F` / `3F`） |
| GET | `/api/status` | 当前靠近楼层 / 呼叫目标 / 各节点信号 |
| GET | `/api/call?floor=3F&dir=UP` | **叫电梯**（让该层 ESP32 的舵机按下按钮） |
| GET | `/api/target?floor=3F` | 设置“呼叫目标楼层”（等价于点 App 里的 2F/3F） |

所有响应都是 `application/json`，并带 `Access-Control-Allow-Origin: *`（网页里 `fetch()` 可直接调）。

---

## 3. 各接口详情

### `GET /api/ping`
```json
{ "ok": true, "app": "elevator-call", "api": 1, "port": 8899 }
```

### `GET /api/floors`
```json
{ "ok": true, "floors": ["2F", "3F"] }
```
> 本演示**井道是 1F–4F 四层**，但**只有 2F、3F 装了呼梯装置**（中间层才有上行+下行，
> 1F 只有上行、4F 只有下行）。所以**能呼叫的只有 `2F` / `3F`**（这里的 `floors`）。
> 四层井道本身在 `/api/status` 的 `shaftFloors` 里。

### `GET /api/status`
`near` = 手机信号判定出的“你现在靠近哪层”（= **蓝牙判层**，见下）；
`car` / `carSource` / `car2` = **轿厢实际在哪层**（见下）；`target` = 当前呼叫目标；
`nodes` 是各块 ESP32 的连接与信号；`floors` = 可呼叫楼层；`shaftFloors` = 井道展示用的全部楼层。

**轿厢位置（`car` / `carSource` / `car2`）**：

| 字段 | 含义 |
|---|---|
| `car` | **甲梯**轿厢在哪层 |
| `carSource` | `car` 这个数**怎么来的**：`camera`（摄像头读电梯厅的屏，**现已搁置**）/ `manual`（现场手动指定）/ `near`（**蓝牙判层** —— 没有真读数时，用"手机靠近哪层"当轿厢所在层） |
| `car2` | **乙梯**轿厢在哪层（厅里那块屏**右边**那位；没有就是 `null`） |

> 硬件**看不到轿厢**（板子只知道"我这层的按钮被按了"）。**现在的默认来源就是 `near` = 蓝牙判层**：
> **用户拿着手机坐在轿厢里**时，"用户靠近哪层"就是"轿厢在哪层" —— 不是猜的，是信号强弱量出来的
> （判层规则见 `BLE_PROTOCOL.md`）。装置只装在 **2F / 3F**，所以只有这两层判得出来。
> `camera` / `manual` 是"摄像头读电梯厅那块屏"那条路，**现已搁置**；真读到时会优先于 `near`，
> 而且超过 3 分钟没人更新就自动作废（退回 `near`）。

```json
{
  "ok": true,
  "api": 1,
  "near": "3F",
  "target": "3F",
  "car": "3F",
  "carSource": "camera",
  "car2": "1F",
  "floors": ["2F", "3F"],
  "shaftFloors": ["1F", "2F", "3F", "4F"],
  "nodes": [
    { "floor": "2F", "address": "AA:BB:CC:DD:EE:01", "name": "ELEV-2F", "rssi": -78, "ready": true },
    { "floor": "3F", "address": "AA:BB:CC:DD:EE:02", "name": "ELEV-3F", "rssi": -52, "ready": true }
  ]
}
```

### `GET /api/call?floor=3F&dir=UP`  ← 核心
- `dir`：`UP`（上行）/ `DOWN`（下行）。也接受 `上/下/上行/下行`。
- `floor`：可选。不传就用当前呼叫目标（`target`），再退化到你靠近的楼层。
- 成功（命令已下发，舵机开始动作）：
  ```json
  { "ok": true, "floor": "3F", "dir": "UP", "message": "已下发 上行 → 3F" }
  ```
- 失败（例如该层装置没连上 / 楼层未知）→ HTTP `409`：
  ```json
  { "ok": false, "floor": "3F", "dir": "UP", "message": "3F 装置连接中，请稍候" }
  ```

> 注意：这里是**“命令已下发”**的即时结果。舵机动作完成后的真实回执由 App 自己显示，
> 目前不通过 HTTP 回推（需要的话可以加 `/api/status` 轮询 `nodes[].ready` 或后续加推送）。

### `GET /api/target?floor=3F`
设置呼叫目标（不触发呼叫），返回：
```json
{ "ok": true, "target": "3F" }
```

---

## 4. 调用示例

### cURL
```bash
curl http://192.168.1.23:8899/api/ping
curl http://192.168.1.23:8899/api/status
curl "http://192.168.1.23:8899/api/call?floor=3F&dir=UP"
curl "http://192.168.1.23:8899/api/call?dir=DOWN"      # 用当前目标楼层
```

### Swift（队友的 iOS App，`URLSession`）
```swift
import Foundation

struct ElevatorAPI {
    let base = URL(string: "http://192.168.1.23:8899")!

    func call(floor: String?, dir: String, completion: @escaping (Bool, String) -> Void) {
        var comps = URLComponents(url: base.appendingPathComponent("api/call"),
                                  resolvingAgainstBaseURL: false)!
        comps.queryItems = [URLQueryItem(name: "dir", value: dir)]
        if let floor { comps.queryItems?.append(URLQueryItem(name: "floor", value: floor)) }

        // ⚠️ 明文 HTTP：Info.plist 里给这台内网 IP 加 ATS 例外，或开发期开 NSAllowsArbitraryLoads
        URLSession.shared.dataTask(with: comps.url!) { data, _, _ in
            guard let data, let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
            else { completion(false, "no response"); return }
            completion(obj["ok"] as? Bool ?? false, obj["message"] as? String ?? "")
        }.resume()
    }
}
```
使用：
```swift
ElevatorAPI().call(floor: "3F", dir: "UP") { ok, msg in
    print(ok, msg)   // true 已下发 上行 → 3F
}
```

### JavaScript / 网页
```js
const r = await fetch("http://192.168.1.23:8899/api/call?floor=3F&dir=UP");
const j = await r.json();
console.log(j.ok, j.message);
```

---

## 5. 典型集成方式（建议）

导航 App 知道“用户当前在几层 / 正走向电梯”，可以：

1. 用户导航到电梯厅附近 → 调 `GET /api/call?floor=<当前层>&dir=<上行|下行>`，
   电梯提前被叫到你所在层；
2. 或先 `GET /api/target?floor=3F` 设定目标，再 `GET /api/call?dir=DOWN`；
3. 想确认电梯状态 → 轮询 `GET /api/status` 看 `near` / `nodes[].ready`。

> 建议由导航 App 在“到达某层的那一刻”调一次，而不是持续高频轮询，避免重复呼叫。

---

## 6. 已知限制

- 接口只在 **App 处于前台**时可用（没有做常驻前台服务；需要的话可以加）。
- 明文 HTTP（内网演示够用）；生产环境应加 token 鉴权 / HTTPS。
- 不做跨网段、不做公网。
- 只有“命令已下发”的即时回执；舵机动作完成的 `OK:UP` 回执目前留在 App 界面上。
