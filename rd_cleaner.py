import os
import urllib.request
import json

def clean_real_debrid():
    token = os.environ.get("RD_SECRET_TOKEN", "").strip()
    if not token:
        print("[오류] Real-Debrid API 토큰이 Secrets에 등록되지 않았습니다.")
        return

    try:
        # 최대 2500개 목록을 전수 조사하도록 범위를 극대화합니다.
        url = "https://real-debrid.com"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        
        with urllib.request.urlopen(req) as response:
            raw_data = response.read().decode("utf-8").strip()

        if not raw_data or raw_data.startswith("<"):
            print("[🚨 인증 오류] 응답이 비정상적입니다. 토큰 만료 여부를 확인하세요.")
            return

        torrents = json.loads(raw_data)
        seen_hashes = set()
        duplicate_ids = []

        for t in torrents:
            # 리얼디브리드가 제공하는 고유 정보(hash)를 정밀 필터링합니다.
            raw_hash = t.get("hash", "")
            tid = t.get("id", "")
            filename = t.get("filename", "Unknown")

            if not raw_hash or not tid:
                continue

            # 대소문자 차이 및 규격 오차를 없애기 위해 표준 규격으로 포맷을 통일화합니다.
            clean_hash = str(raw_hash).lower().strip()

            # 목록 상단에 배치된 가장 최신 전송 내역은 보존하고, 과거에 하단에 유입된 중복 복사본을 검출합니다.
            if clean_hash in seen_hashes:
                duplicate_ids.append((tid, filename))
            else:
                seen_hashes.add(clean_hash)

        if duplicate_ids:
            print(f"=== [검출 성공] 총 {len(duplicate_ids)}개의 실시간 중복 파일을 적발했습니다. 파괴 작업을 가동합니다. ===")
            for tid, name in duplicate_ids:
                print(f"[실시간 중복 파괴] 파일명: {name} (ID: {tid})")
                
                del_url = f"https://real-debrid.com{tid}"
                del_req = urllib.request.Request(del_url, method="DELETE", headers={"Authorization": f"Bearer {token}"})
                
                try:
                    with urllib.request.urlopen(del_req) as del_resp:
                        pass
                except Exception as del_err:
                    print(f"-> 원격 제어 기각 (ID: {tid}): {del_err}")
            print("=== [완료] 모든 사후 중복 다운로드 건이 클라우드 공간에서 안전하게 청소되었습니다. ===")
        else:
            print("=== [안정] 중복 유입된 토렌트가 존재하지 않는 완벽하게 깨끗한 상태입니다. ===")

    except Exception as e:
        print(f"[가드 시스템 시스템 에러 예외 포착]: {e}")

if __name__ == "__main__":
    clean_real_debrid()
