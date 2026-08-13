# 대구·경북 소상공인 상권 분석 웹 리포트

소상공인시장진흥공단의 2026년 6월 상가(상권)정보를 이용해 대구와 경북의 점포 분포와 업종 구조를 비교하는 Streamlit 프로젝트입니다.

## 데이터

원본 CSV는 파일당 25MB를 넘어 GitHub에 직접 저장하지 않습니다.

- [Google Drive 원본 데이터 폴더](https://drive.google.com/drive/folders/1ZEBVyAv01XGK5J3L_ERc-IPH7npCM_J4?usp=drive_link)
- 분석 지역: 대구광역시, 경상북도
- 기준 시점: 2026년 6월
- GitHub에는 `prepare_data.py`로 만든 작은 집계 파일만 저장합니다.

## 주요 기능

- 대구·경북 점포 수 비교
- 시군구별 점포 순위
- 업종 대분류 구성 비교
- 시군구와 업종 교차 분석
- 행정동별 상권 분포 지도
- 데이터 품질과 분석 한계 표시

## 현재 집계 결과

- 전체 점포: 263,324개
- 대구: 118,357개
- 경북: 144,967개
- 두 지역에서 가장 많은 업종 대분류: 음식(90,338개)

## 실행 방법

1. Python을 설치합니다.
2. 프로젝트 폴더에서 필요한 패키지를 설치합니다.

```bash
pip install -r requirements.txt
```

3. 웹 리포트를 실행합니다.

```bash
streamlit run app.py
```

## 원본 데이터를 다시 집계하는 방법

Google Drive에서 대구와 경북 CSV를 내려받아 프로젝트 안의 `raw_data` 폴더에 넣은 뒤 다음 명령을 실행합니다. `raw_data`는 GitHub 업로드에서 자동으로 제외됩니다.

```bash
python prepare_data.py --input raw_data
```

전국 원본 ZIP 파일이 있다면 압축을 풀지 않고 바로 처리할 수도 있습니다.

```bash
python prepare_data.py --input "원본 ZIP 파일 경로"
```

공유된 CSV에 깨진 중복 열이 뒤에 붙어 있어도 스크립트가 앞의 정상 39개 열만 선택해 처리합니다.

## 프로젝트 구조

```text
.
├─ app.py                 # Streamlit 웹 리포트
├─ prepare_data.py        # 원본 CSV 정제 및 집계
├─ requirements.txt       # 실행 패키지
├─ data/                  # GitHub에 올릴 소용량 집계 데이터
└─ README.md
```

## 분석 시 주의사항

이 데이터는 점포의 위치와 업종 현황을 나타냅니다. 매출액, 유동인구, 창업일, 폐업 여부는 포함하지 않으므로 매출 성과나 폐업 위험을 직접 판단할 수 없습니다.
