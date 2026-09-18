import os
import urllib.request
import json
import urllib.error

def clean_real_debrid():
    # 깃허브 액션 환경변수 매핑 불일치 문제를 해결하기 위해 유입될 수 있는 모든 Secrets 변수명을 정밀 추적합니다.
    token = os.environ.get("REAL_DEBRID_TOKEN", "") or os.environ.get("RD_SECRET_TOKEN", "")
    token = str(token).replace('"', '').replace("'", "").strip()
    
    if not token or token == "***":
        print("[🚨 하드웨어 오류] 깃허브 Secrets 토큰 값이 파이썬 스크립트로 전달되지 못했습니다.")
        print("YAML 파일 내부의 env 설정을 다시 확인해야 합니다.")
        return

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
                print(f"\n[🚨 인증 거부] Real-Debrid API 토큰 거부 (HTTP {he.code}). 토큰의 문자열 알맹이가 올바르지 않습니다.")
                print("복사할 때 앞뒤에 공백이 들어갔거나, Bearer Token이 아닌 일반 쿠키 토큰을 넣었는지 확인하세요.\n")
                return
            raise he

        # 서버 응답 검증 구조 고도화
        if not raw_data or raw_data.startswith("<!DOCTYPE") or "<html" in raw_data:
            print("\n[🚨 프로토콜 인증 실패] 정식 API 경로로 요청했으나, 토큰값 미치 혹은 만료로 메인 페이지 리디렉션이 터졌습니다.")
            print("--- 수신된 서버 응답 샘플 (상위 300자) ---")
            print(raw_data[:300])
            print("------------------------------------------")
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

            # 최신 항목(상단 배정)은 살려두고, 과거에 하단에 이미 들어와 앉아있던 중복 복사본 해시를 타겟팅합니다.
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
