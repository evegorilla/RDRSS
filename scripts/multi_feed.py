#!/usr/bin/env python3
"""여러 RSS 피드를 순회하며 아직 전송하지 않은 마그넷만 골라 RDRSS.py로 넘깁니다.

동작 순서
1. MULTI_FEED_URLS 환경변수에서 피드 주소를 읽는다.
   (한 줄에 하나, 빈 줄은 무시, '#'로 시작하는 줄은 주석 처리)
2. 각 피드를 `RDRSS.py --add` 로 등록하고, 이력 파일에 없는 새 마그넷을 찾는다.
3. 새 마그넷이 하나라도 있으면 `RDRSS.py` 를 한 번 실행한다.
4. RDRSS.py 가 성공(종료코드 0)했을 때만 새 마그넷을 이력 파일에 기록한다.
   실패하면 기록하지 않으므로 다음 실행 때 자동으로 다시 시도된다.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

import feedparser

MAGNET_FILE = Path("RDRSSconfig/sent_magnets1.txt")
RDRSS_CMD = [sys.executable, "RDRSS.py"]
FETCH_TIMEOUT = 30  # 초


def log(msg: str) -> None:
    print(msg, flush=True)


def warn(msg: str) -> None:
    print(f"::warning::{msg}", flush=True)


def error(msg: str) -> None:
    print(f"::error::{msg}", flush=True)


def normalize_url(url: str) -> str:
    """한글·한자가 섞인 쿼리를 UTF-8 퍼센트 인코딩으로 정규화한다.

    이미 인코딩된 URL을 넣어도 한 번 디코딩 후 다시 인코딩하므로 이중 인코딩되지 않는다.
    """
    parts = urlsplit(url)
    query = urlencode(parse_qsl(parts.query, keep_blank_values=True))
    path = quote(parts.path, safe="/%")
    return urlunsplit((parts.scheme, parts.netloc, path, query, parts.fragment))


def load_feeds() -> list[str]:
    feeds: list[str] = []
    for line in os.environ.get("MULTI_FEED_URLS", "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        url = normalize_url(line)
        if url not in feeds:
            feeds.append(url)
    return feeds


def load_sent() -> set[str]:
    MAGNET_FILE.parent.mkdir(parents=True, exist_ok=True)
    MAGNET_FILE.touch(exist_ok=True)
    with MAGNET_FILE.open(encoding="utf-8") as f:
        return {line.strip().lower() for line in f if line.strip()}


def record(links: list[str]) -> None:
    """이력 파일 끝에 마그넷을 추가한다. 마지막 줄에 개행이 없어도 안전하게 이어 붙인다."""
    prefix = ""
    if MAGNET_FILE.exists() and MAGNET_FILE.stat().st_size > 0:
        with MAGNET_FILE.open("rb") as f:
            f.seek(-1, os.SEEK_END)
            if f.read(1) != b"\n":
                prefix = "\n"
    with MAGNET_FILE.open("a", encoding="utf-8") as f:
        f.write(prefix + "".join(link + "\n" for link in links))


def run_rdrss(*args: str) -> int:
    return subprocess.run([*RDRSS_CMD, *args]).returncode


def fetch_entries(url: str):
    """피드를 읽어 항목 리스트를 돌려준다. 읽기 자체에 실패하면 None."""
    d = feedparser.parse(url)
    status = d.get("status")

    if status is not None and status >= 400:
        warn(f"피드 응답 오류 (HTTP {status}): {url[:80]}")
        return None

    if d.bozo:
        exc = d.get("bozo_exception")
        if not d.entries:
            warn(f"피드를 읽지 못했습니다 (status={status}): {exc!r}")
            return None
        log(f"  ⚠️ 파싱 경고 (항목 {len(d.entries)}건은 읽힘): {exc!r}")

    return d.entries


def main() -> int:
    socket.setdefaulttimeout(FETCH_TIMEOUT)

    feeds = load_feeds()
    if not feeds:
        error("MULTI_FEED_URLS 에 피드 주소가 없습니다.")
        return 1

    sent = load_sent()
    log(f"[스캔 시작] 피드 {len(feeds)}개, 기존 전송 이력 {len(sent)}건")

    pending: dict[str, tuple[str, str]] = {}  # 소문자 링크 -> (원본 링크, 제목)
    feeds_ok = 0

    for url in feeds:
        log(f"\n[피드 분석] {url[:80]}")

        if run_rdrss("--add", url) != 0:
            warn("RDRSS.py --add 실패 - 이 피드는 건너뜁니다.")
            continue

        entries = fetch_entries(url)
        if entries is None:
            continue
        feeds_ok += 1

        new_count = 0
        for e in entries:
            link = str(e.get("link", "")).strip()
            key = link.lower()
            if not link or key in sent or key in pending:
                continue
            title = str(e.get("title", "(제목 없음)"))
            pending[key] = (link, title)
            new_count += 1
            log(f"  [🆕 신규] {title}")

        if new_count:
            log(f"  [🚀 신규 {new_count}건 발견] (전체 {len(entries)}건 중)")
        elif entries:
            log(f"  [🛑 중복 차단] 전체 {len(entries)}건이 모두 이미 전송된 항목입니다.")
        else:
            log("  [ℹ️ 빈 피드] 피드는 정상이지만 항목이 0건입니다.")

    if feeds_ok == 0:
        error("읽을 수 있는 피드가 하나도 없습니다.")
        return 1

    if not pending:
        log("\n[🏁 최종 결과] 새로운 마그넷이 없습니다. 작업을 안전하게 마칩니다.")
        return 0

    log(f"\n[▶ RDRSS.py 실행] 새 마그넷 {len(pending)}건")
    if run_rdrss() != 0:
        error("RDRSS.py 실행 실패 - 이력에 기록하지 않으므로 다음 실행 때 다시 시도합니다.")
        return 1

    record([link for link, _title in pending.values()])
    log(f"[💾 기록 완료] {len(pending)}건을 {MAGNET_FILE} 에 저장했습니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
