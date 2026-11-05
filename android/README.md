# Android App（`android/`）

Kotlin + Gradle 工程。**用 Android Studio 直接打开本目录**，或在命令行构建。

## 构建

```bash
cd android
./gradlew assembleDebug      # 产物 app/build/outputs/apk/debug/app-debug.apk
```

Windows 下用 `gradlew.bat`。工程不含 `local.properties`、`build/`、`.gradle/`，这些由工具链自动生成。

已发布的安装包见 [`../releases/android/`](../releases/android/)，安装步骤见 [`../docs/android/安装说明.md`](../docs/android/安装说明.md)。

## 目录结构

| 路径 | 作用 |
|---|---|
| `app/src/main/java/com/mocen/elevator/` | 全部业务代码 |
| `app/src/main/res/layout/` | 主界面、摄像头页、导航 Mock 页 |
| `app/src/main/res/drawable/` | 自绘背景与图标（纯 XML，无位图资源） |
| `app/src/main/res/values/` | 颜色、文案、主题 |
| `app/src/main/AndroidManifest.xml` | 权限（蓝牙、摄像头）与 Activity 声明 |

## 关键代码

| 文件 | 作用 |
|---|---|
| `MainActivity.kt` | 主界面、扫描 / 连接、悬浮呼梯按钮 |
| `BleManager.kt` | BLE 扫描与 GATT 连接（广播名前缀 `ELEV-`） |
| `FloorJudge.kt` | RSSI 判层（中位数 + EMA + 滞回 + 连胜防抖） |
| `ElevatorView.kt` | 真 3D 井道（双轿厢） |
| `CarFloorSource.kt` | 「轿厢在哪层」的来源（画面 / 摄像头 / 手动） |
| `LocalApiServer.kt` | 对外最小 HTTP 接口 |

## 注意

- BLE 与摄像头都需要**运行时权限**，首次使用要手动授予，否则扫描不到设备。
- **只有人主动点按**才会下发呼梯指令，代码里没有任何定时或传感器触发的自动呼梯。
- 运行不依赖公网：手机与呼梯板之间是 BLE 直连。
