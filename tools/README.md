# tools/（自检脚本）

两个脚本都不联网，出问题就返回非 0 退出码，可以接进 CI 或提交前手动跑一遍。

| 脚本 | 作用 |
|---|---|
| `preflight.ps1` | 仓库体检：目录与关键文件是否齐全、固件与 App 里的楼层常量是否一致、文档里是否残留旧楼层叫法、Markdown 相对链接是否失效、`releases/` 里的成品镜像是否在位。PowerShell 5.1 直接跑：`powershell -ExecutionPolicy Bypass -File .\tools\preflight.ps1` |
| `check_links.py` | 只查 Markdown 相对链接（`preflight` 里也会调用同一套逻辑）：`py -3 tools/check_links.py` |

变更记录类文件（`*_版本信息.md`）里的旧楼层是历史，扫旧叫法时会跳过。
