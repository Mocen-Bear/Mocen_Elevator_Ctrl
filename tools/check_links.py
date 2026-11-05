# -*- coding: utf-8 -*-
"""检查 Markdown 里的相对链接是否指向真实存在的文件/目录。

用法：
    python tools/check_links.py            # 检查全仓库
    python tools/check_links.py docs       # 只检查 docs/ 下

退出码 0 表示全部通过，1 表示有失效链接（可直接用于 CI）。
"""
import os
import re
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# [文字](目标) 与 ![图片](目标)；目标允许带 <> 包裹
LINK_RE = re.compile(r"!?\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
SKIP_PREFIX = ("http://", "https://", "mailto:", "tel:", "data:", "#")

# 这些目录不参与检查
SKIP_DIRS = {".git", "build", ".gradle", ".idea", "node_modules"}


def iter_markdown(base):
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if name.lower().endswith(".md"):
                yield os.path.join(dirpath, name)


def check_file(path):
    problems = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for lineno, line in enumerate(fh, 1):
            for raw in LINK_RE.findall(line):
                target = raw.strip()
                if not target or target.startswith(SKIP_PREFIX):
                    continue
                # 去掉锚点与查询串，再做 URL 解码（%20 之类）
                clean = target.split("#", 1)[0].split("?", 1)[0]
                if not clean:
                    continue
                clean = urllib.parse.unquote(clean)
                resolved = os.path.normpath(
                    os.path.join(os.path.dirname(path), clean.replace("/", os.sep))
                )
                if not os.path.exists(resolved):
                    problems.append((lineno, target))
    return problems


def main():
    base = os.path.join(ROOT, sys.argv[1]) if len(sys.argv) > 1 else ROOT
    if not os.path.isdir(base):
        print("路径不存在:", base)
        return 1

    files = sorted(iter_markdown(base))
    total_links = 0
    bad = 0
    for path in files:
        problems = check_file(path)
        for lineno, target in problems:
            bad += 1
            print("失效 %s:%d  ->  %s" % (os.path.relpath(path, ROOT), lineno, target))

    print()
    print("扫描 %d 个 Markdown 文件，发现 %d 处失效链接。" % (len(files), bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
