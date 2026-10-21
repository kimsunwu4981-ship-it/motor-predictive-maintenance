# -*- coding: utf-8 -*-
"""changelog_from_log.py — SESSION_LOG.md 의 장 제목(## N. 제목 (날짜…))과 git 커밋에서 CHANGELOG.md 를 만든다 (D2, 2026-10-21). 수기 없음.

  py -3.12 -X utf8 motor_dt_viz/tools/docs/changelog_from_log.py [--repo <루트>] [--out CHANGELOG.md] [--tag v1.0-m1]
날짜는 제목 괄호 안의 YYYY-MM-DD(없으면 '날짜 미상'), 커밋은 같은 날짜의 git 커밋(해시·첫 줄)을 붙인다.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_DEFAULT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
HEAD_RE = re.compile(r"^## +(\d+)\.\s*(.+?)\s*$")
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def git_commits(repo: str) -> dict[str, list[tuple[str, str]]]:
    out = subprocess.run(["git", "-C", repo, "log", "--date=short", "--format=%h%x09%ad%x09%s", "--reverse"], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
    by: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for ln in out.splitlines():
        h, d, s = ln.split("\t", 2)
        by[d].append((h, s))
    return by


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=REPO_DEFAULT); ap.add_argument("--log", default="SESSION_LOG.md"); ap.add_argument("--out", default="CHANGELOG.md"); ap.add_argument("--tag", default="v1.0-m1")
    a = ap.parse_args()
    log_p = os.path.join(a.repo, a.log)
    chapters = []
    for ln in open(log_p, encoding="utf-8"):
        m = HEAD_RE.match(ln.rstrip())
        if m:
            title = m.group(2); dm = DATE_RE.findall(title)
            chapters.append({"n": int(m.group(1)), "title": title, "date": dm[-1] if dm else None})
    commits = git_commits(a.repo)
    used = set()
    L = [f"# CHANGELOG — {os.path.basename(os.path.abspath(a.repo))}", "",
         f"생성 {time.strftime('%Y-%m-%d %H:%M')} · `motor_dt_viz/tools/docs/changelog_from_log.py` · 출처 `{a.log}` 장 제목 + `git log`. 최신 태그 `{a.tag}`.", "",
         "| # | 날짜 | 장 제목 | 같은 날 커밋 |", "|---|---|---|---|"]
    for ch in sorted(chapters, key=lambda c: (c["date"] or "", c["n"])):
        cs = commits.get(ch["date"] or "", [])
        cell = "<br>".join(f"`{h}` {s}" for h, s in cs if (ch["date"], h) not in used) or "—"
        for h, _ in cs:
            used.add((ch["date"], h))
        L.append(f"| {ch['n']} | {ch['date'] or '날짜 미상'} | {ch['title']} | {cell} |")
    L += ["", "## 태그", "", f"- `{a.tag}` — M1 단일 모터 트윈, 학생판 2D 검증 완료 (2026-10-21)"]
    open(os.path.join(a.repo, a.out), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print(f"→ {os.path.join(a.repo, a.out)} ({len(chapters)} 장, 커밋 날짜 {len(commits)}개)")


if __name__ == "__main__":
    main()
