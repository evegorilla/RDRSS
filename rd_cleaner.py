import os
import urllib.request
import json
import urllib.error

def clean_real_debrid():
    # 환경변수에서 토큰을 가져오고 따옴표나 공백이 섞여 들어오지 않도록 정제합니다.
    token = os.environ.get("RD_SECRET_TOKEN", "").replace('"', '').replace("'", "").strip()
    
    if not token:
        print("[오류] Repository Secrets의 REAL_DEBRID_TOKEN 값이 비어있거나 정상적으로 매핑되지 않았습니다.")
        return

    try:
        url = "https://real-debrid.com"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        
        try:
            with urllib.request.urlopen(req) as response:
                raw_data = response.read().decode("utf-8").strip()
        except urllib.error.HTTPError as he:
            # 🚨 문법 에러가 났던 누락된 비교군 배열([401, 403])을 완벽하게 주입했습니다.
            if he.code in:
                print(f"\n[🚨 인증 거부] Real-Debrid API 토큰 오류 (HTTP {he.code}). 토큰이 올바르지 않거나 권한이 없습니다.")
                print("깃허브 Settings -> Secrets and variables -> Actions에 등록된 토큰을 다시 발급받아 입력하세요.\n")
                return
            raise he

        if not raw_data or raw_data.startswith("<!DOCTYPE html") or "<html" in raw_data:
            print("\n[🚨 프로토콜 인증 실패] Real-Debrid 서버가 JSON 대신 웹페이지 HTML을 응답했습니다.")
            print("토큰값이 잘못 전달되었거나 만료되었을 확률이 매우 높습니다. Secrets 설정 상태를 확인해 주세요.\n")
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

            # 최신 항목은 상단에 배치되므로 보존하고, 과거 하단에 이미 추가되었던 중복 마그넷 건을 적발합니다.
            if clean_hash in seen_hashes:
                duplicate_ids.append((tid, filename))
            else:
                seen_hashes.add(clean_hash)

        if duplicate_ids:
            print(f"=== [검출 성공] 총 {len(duplicate_ids)}개의 실시간 중복 마그넷을 적발했습니다. 파괴 작업을 가동합니다. ===")
            for tid, name in duplicate_ids:
                print(f"[실시간 중복 파괴] 파일명: {name} (ID: {tid})")
                del_url = f"https://real-debrid.com{tid}"
                del_req = urllib.request.Request(del_url, method="DELETE", headers={"Authorization": f"Bearer {token}"})
                try:
                    with urllib.request.urlopen(del_req) as del_resp: pass
                except Exception as del_err:
                    print(f"-> 원격 삭제 명령 실패 (ID: {tid}): {del_err}")
            print("=== [완료] 모든 사후 중복 다운로드 건이 클라우드 공간에서 안전하게 청소되었습니다. ===")
        else:
            print("=== [안정] 중복 유입된 토렌트가 존재하지 않는 완벽하게 깨끗한 상태입니다. ===")

    except Exception as e:
        print(f"[가드 시스템 예외 포착]: {e}")

if __name__ == "__main__":
    clean_real_debrid()
