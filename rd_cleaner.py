import os
import urllib.request
import json
import urllib.error

def clean_real_debrid():
    # 깃허브 Secrets에 잘못 유입될 수 있는 공백, 줄바꿈(\n), 큰따옴표, 작은따옴표를 완벽하게 제거하여 순수 알맹이만 추출합니다.
    raw_token = os.environ.get("REAL_DEBRID_TOKEN", "") or os.environ.get("RD_SECRET_TOKEN", "")
    token = str(raw_token).replace('"', '').replace("'", "").replace("\n", "").replace("\r", "").strip()
    
    if not token or token == "***":
        print("[🚨 하드웨어 오류] 깃허브 Secrets 토큰 값이 파이썬 스크립트로 전달되지 못했습니다.")
        return

    # 💡 [전문가 디버깅 정보 출력] 토큰의 무결성 상태를 사용자가 직접 역추적할 수 있도록 정보를 서포트합니다.
    print(f"=== [토큰 무결성 검증 세션] ===")
    print(f"-> 파악된 토큰 문자열 총 길이: {len(token)} 글자")
    if len(token) > 8:
        print(f"-> 토큰 시작 부호 대조: {token[:4]}****...****{token[-4:]}")
    print(f"================================\n")

    try:
        url = "https://real-debrid.com"
        
        # Cloudflare 가드 및 봇 필터링 차단을 무력화하는 최신 크롬 브라우저 마스킹 헤더
        headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json"
        }
        
        req = urllib.request.Request(url, headers=headers)
        
        try:
            with urllib.request.urlopen(req) as response:
                raw_data = response.read().decode("utf-8").strip()
        except urllib.error.HTTPError as he:
            if he.code in (401, 403):
                print(f"[🚨 인증 거부] Real-Debrid API 서버가 토큰 인증을 즉시 거부했습니다 (HTTP {he.code}).")
                print("복사 오류가 발생했거나, 다른 계정의 토큰이거나, 만료된 토큰입니다. apitoken 페이지에서 다시 Generate 하여 넣으셔야 합니다.\n")
                return
            raise he

        # 서버 응답 검증 구조 고도화
        if not raw_data or raw_data.startswith("<!DOCTYPE") or "<html" in raw_data:
            print("[🚨 프로토콜 인증 실패] 정식 API 경로로 우회 요청했으나, 토큰 문자열 유효성 결함으로 홈페이지 리디렉션이 터졌습니다.")
            print("현재 입력된 REAL_DEBRID_TOKEN 값의 문자열 알맹이 자체에 무조건 공백이나 오타가 박혀있는 상태입니다.")
            return

        torrents = json.loads(raw_data)
        seen_hashes = set()
        duplicate_ids = []

        for t in torrents:
            raw_hash = t.get("hash", "")
            tid = t.get("id", "")
            filename = t.get("filename", "Unknown")

            if not raw_hash or not tid:
                continue

            clean_hash = str(raw_hash).lower().strip()

            if clean_hash in seen_hashes:
                duplicate_ids.append((tid, filename))
            else:
                seen_hashes.add(clean_hash)

        if duplicate_ids:
            print(f"=== [검출 성공] 총 {len(duplicate_ids)}개의 실시간 중복 유입 마그넷을 적발했습니다. 파괴 작업을 진행합니다. ===")
            for tid, name in duplicate_ids:
                print(f"[실시간 중복 원격 청소] 파일명: {name} (ID: {tid})")
                del_url = f"https://real-debrid.com{tid}"
                del_req = urllib.request.Request(del_url, method="DELETE", headers={"Authorization": f"Bearer {token}", "User-Agent": "Mozilla/5.0"})
                try:
                    with urllib.request.urlopen(del_req) as del_resp: pass
                except Exception as del_err:
                    print(f"-> 원격 삭제 거부 (ID: {tid}): {del_err}")
            print("=== [완료] 클라우드 내 모든 사후 중복 다운로드 시도가 깨끗하게 강제 파괴 정돈되었습니다. ===")
        else:
            print("=== [안정] 중복 유입된 토렌트가 존재하지 않는 완벽하게 깨끗한 상태입니다. ===")

    except Exception as e:
        print(f"[가드 시스템 예외 처리 오류 포착]: {e}")

if __name__ == "__main__":
    clean_real_debrid()
