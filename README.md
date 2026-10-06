# 청약 데일리

청약홈(applyhome.co.kr)의 아파트 분양·무순위/잔여세대·오피스텔 공고를 매일 모아 보여주는 정적 페이지입니다.
GitHub Pages로 호스팅되며, 어디서든 브라우저만 있으면 열립니다.

## 구성

| 파일 | 역할 |
|---|---|
| `index.html` | 청약 공고 목록. 접수 중·예정 공고, 놓치면 아까운 공고(무순위·수도권·공공분양) 우선 표시, 청약홈 신청/상세 링크 |
| `trends.html` | 부동산 투자 흐름·정책·금리 이슈, 주목 공고와 이유, 용어 설명 |
| `data/listings.json` | 수집된 공고 데이터 (자동 갱신) |
| `data/trends.json` | 트렌드·주목 공고 요약 (자동 갱신) |
| `scripts/fetch_listings.py` | 청약홈 목록·상세 페이지를 읽어 `listings.json` 생성 (표준 라이브러리만 사용) |
| `.github/workflows/update.yml` | 매일 06:30·18:30 KST 수집 후 커밋 |
| `.github/workflows/pages.yml` | main 푸시 시 GitHub Pages 배포 |

## 갱신 흐름

1. **공고 데이터**: GitHub Actions가 하루 두 번 `fetch_listings.py`를 실행해 `data/listings.json`을 갱신합니다.
2. **트렌드·주목 공고**: Claude Code 클라우드 루틴이 매일 아침 최신 기사와 `listings.json`을 읽고 `data/trends.json`을 다시 써서 커밋합니다.
3. main에 커밋이 생기면 Pages가 자동 배포됩니다.

## 수동 실행

```bash
python3 scripts/fetch_listings.py   # data/listings.json 갱신
python3 -m http.server 8000         # http://localhost:8000 에서 확인
```

## 주목 점수(score)

`fetch_listings.py`의 `score()`가 공고마다 0~100점을 매깁니다. 무순위·잔여세대(+30), 계약취소·불법행위 재공급(+10), 서울(+30)/경기·인천(+20)/광역시(+10), 공공분양(+10), 소량 공급(+5), 임대(−20), 오피스텔 등(−10). 50점 이상이면 "놓치면 아까운 공고"에 올라갑니다. `trends.json`의 `picks`에 `pblancNo`가 있으면 점수와 무관하게 주목 공고로 표시되고 이유가 함께 보입니다.

투자 권유가 아니며, 자격·일정·금액은 반드시 입주자모집공고문으로 확인하세요.
