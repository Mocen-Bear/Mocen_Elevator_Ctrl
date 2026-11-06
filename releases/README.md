# 发行包（`releases/`）

编译好的固件镜像，**下载即烧**，不需要自己构建。

> App 不在本目录：仓库只收源码，按 [`../android/README.md`](../android/README.md) 自行构建即可。

## 固件

| 文件 | 大小 | 说明 |
|---|---|---|
| [`firmware/elevator_1F.merged.bin`](firmware/elevator_1F.merged.bin) | 4.00 MB | 1F 呼梯板，广播名 `ELEV-1F` |
| [`firmware/elevator_2F.merged.bin`](firmware/elevator_2F.merged.bin) | 4.00 MB | 2F 呼梯板，广播名 `ELEV-2F` |

**合并镜像**：已包含 bootloader、分区表和应用本体，按 `../firmware/烧录说明.md` 的地址直接烧到 `0x0`，不需要先装 Arduino IDE。

## 校验值（SHA-256）

下载后可以先核对，确认文件没有损坏或被替换：

```
95436e5483c5851e9be49fda2f0a2f9debd790aafa2fc3435b7e52797525996e  firmware/elevator_1F.merged.bin
48dcb92ca73f1cb4ca38108c1fe12450028bc7f5ba339718045494d455b1fdc8  firmware/elevator_2F.merged.bin
```

或在 Git Bash / Linux 下：

```bash
sha256sum -c <(printf '%s\n' \
  "95436e5483c5851e9be49fda2f0a2f9debd790aafa2fc3435b7e52797525996e  firmware/elevator_1F.merged.bin" \
  "48dcb92ca73f1cb4ca38108c1fe12450028bc7f5ba339718045494d455b1fdc8  firmware/elevator_2F.merged.bin")
```

## 说明

- 两个 `.bin` **大小相同、哈希不同**——只有 `FLOOR_NAME` 与内置的广播名不一样，这是预期现象。
- 想改逻辑就回源码（`../firmware/`），不要直接改 bin。
- 版本要点见 [`../CHANGELOG.md`](../CHANGELOG.md)。
