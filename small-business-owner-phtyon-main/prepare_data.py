from __future__ import annotations

import argparse
import json
import zipfile
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO, Iterator

import pandas as pd


REGION_KEYWORDS = ("대구", "경북")
REGION_LABELS = {
    "대구": "대구",
    "경북": "경북",
    "대구광역시": "대구",
    "경상북도": "경북",
}

EXPECTED_COLUMNS = [
    "상가업소번호",
    "상호명",
    "지점명",
    "상권업종대분류코드",
    "상권업종대분류명",
    "상권업종중분류코드",
    "상권업종중분류명",
    "상권업종소분류코드",
    "상권업종소분류명",
    "표준산업분류코드",
    "표준산업분류명",
    "시도코드",
    "시도명",
    "시군구코드",
    "시군구명",
    "행정동코드",
    "행정동명",
    "법정동코드",
    "법정동명",
    "지번코드",
    "대지구분코드",
    "대지구분명",
    "지번본번지",
    "지번부번지",
    "지번주소",
    "도로명코드",
    "도로명",
    "건물본번지",
    "건물부번지",
    "건물관리번호",
    "건물명",
    "도로명주소",
    "구우편번호",
    "신우편번호",
    "동정보",
    "층정보",
    "호정보",
    "경도",
    "위도",
]

ANALYSIS_COLUMNS = [
    "상가업소번호",
    "상호명",
    "상권업종대분류명",
    "상권업종중분류명",
    "상권업종소분류명",
    "시도명",
    "시군구명",
    "행정동명",
    "법정동명",
    "도로명주소",
    "경도",
    "위도",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="대구·경북 상가(상권) CSV를 Streamlit용 집계 데이터로 변환합니다."
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="원본 CSV가 있는 폴더, CSV 파일 또는 공공데이터 ZIP 파일",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "data",
        help="집계 CSV 저장 폴더(기본값: 프로젝트의 data 폴더)",
    )
    return parser.parse_args()


def _region_from_name(name: str) -> str | None:
    for keyword in REGION_KEYWORDS:
        if f"_{keyword}_" in name or keyword in name:
            return keyword
    return None


def discover_sources(input_path: Path) -> list[tuple[str, str]]:
    """Return (region keyword, source name/member) pairs."""
    if not input_path.exists():
        raise FileNotFoundError(f"입력 경로를 찾을 수 없습니다: {input_path}")

    sources: list[tuple[str, str]] = []
    if input_path.is_file() and zipfile.is_zipfile(input_path):
        with zipfile.ZipFile(input_path) as archive:
            for member in archive.namelist():
                if not member.lower().endswith(".csv"):
                    continue
                region = _region_from_name(Path(member).name)
                if region:
                    sources.append((region, member))
    elif input_path.is_dir():
        for csv_path in sorted(input_path.rglob("*.csv")):
            region = _region_from_name(csv_path.name)
            if region:
                sources.append((region, str(csv_path)))
    elif input_path.suffix.lower() == ".csv":
        region = _region_from_name(input_path.name)
        if region:
            sources.append((region, str(input_path)))

    found = {region for region, _ in sources}
    missing = [region for region in REGION_KEYWORDS if region not in found]
    if missing:
        raise ValueError(
            "대구·경북 CSV를 모두 찾지 못했습니다. 누락 지역: " + ", ".join(missing)
        )
    return sorted(sources, key=lambda item: REGION_KEYWORDS.index(item[0]))


@contextmanager
def open_source(input_path: Path, source_name: str) -> Iterator[BinaryIO]:
    if input_path.is_file() and zipfile.is_zipfile(input_path):
        with zipfile.ZipFile(input_path) as archive:
            with archive.open(source_name, "r") as stream:
                yield stream
    else:
        with open(source_name, "rb") as stream:
            yield stream


def read_source(input_path: Path, region: str, source_name: str) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    with open_source(input_path, source_name) as stream:
        sample = stream.read(65_536)
        stream.seek(0)
        try:
            sample.decode("utf-8-sig")
            encoding = "utf-8-sig"
        except UnicodeDecodeError:
            encoding = "cp949"

        chunks = pd.read_csv(
            stream,
            encoding=encoding,
            encoding_errors="replace",
            dtype=str,
            chunksize=50_000,
            usecols=range(len(EXPECTED_COLUMNS)),
            low_memory=False,
        )
        for chunk in chunks:
            # 일부 공유 CSV에는 깨진 중복 열이 뒤에 붙어 있어 앞의 정상 39개 열만 사용합니다.
            chunk.columns = EXPECTED_COLUMNS
            frames.append(chunk[ANALYSIS_COLUMNS])

    data = pd.concat(frames, ignore_index=True)
    text_columns = [column for column in ANALYSIS_COLUMNS if column not in {"경도", "위도"}]
    for column in text_columns:
        data[column] = data[column].fillna("").astype("string").str.strip()

    data["지역"] = data["시도명"].map(REGION_LABELS).fillna(region)
    data["시군구명"] = data["시군구명"].replace("", "미상")
    data["행정동명"] = data["행정동명"].replace("", "미상")
    data["상권업종대분류명"] = data["상권업종대분류명"].replace("", "기타/미분류")
    data["상권업종중분류명"] = data["상권업종중분류명"].replace("", "기타/미분류")
    data["상권업종소분류명"] = data["상권업종소분류명"].replace("", "기타/미분류")
    data["경도"] = pd.to_numeric(data["경도"], errors="coerce")
    data["위도"] = pd.to_numeric(data["위도"], errors="coerce")
    return data


def _top_category(data: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    counts = (
        data.groupby(keys + ["상권업종대분류명"], observed=True)
        .size()
        .reset_index(name="대분류점포수")
        .sort_values(keys + ["대분류점포수", "상권업종대분류명"], ascending=[True] * len(keys) + [False, True])
    )
    return (
        counts.drop_duplicates(keys)
        .rename(columns={"상권업종대분류명": "최다업종"})
        [keys + ["최다업종", "대분류점포수"]]
    )


def build_outputs(data: pd.DataFrame, source_rows: dict[str, int]) -> dict[str, pd.DataFrame]:
    before_dedup = len(data)
    duplicate_mask = data["상가업소번호"].ne("") & data.duplicated("상가업소번호", keep="first")
    duplicate_counts = data.loc[duplicate_mask].groupby("지역", observed=True).size().to_dict()
    data = data.loc[~duplicate_mask].copy()

    valid_coordinates = data["경도"].between(124, 132) & data["위도"].between(33, 39)
    data.loc[~valid_coordinates, ["경도", "위도"]] = pd.NA

    overview = (
        data.groupby("지역", observed=True)
        .agg(
            점포수=("상가업소번호", "size"),
            시군구수=("시군구명", "nunique"),
            행정동수=("행정동명", "nunique"),
            대분류수=("상권업종대분류명", "nunique"),
            중분류수=("상권업종중분류명", "nunique"),
            좌표보유점포수=("경도", "count"),
        )
        .reset_index()
    )

    district = (
        data.groupby(["지역", "시군구명"], observed=True)
        .agg(점포수=("상가업소번호", "size"), 대분류수=("상권업종대분류명", "nunique"))
        .reset_index()
    )
    district["지역내비중"] = district["점포수"] / district.groupby("지역", observed=True)["점포수"].transform("sum")
    district = district.merge(_top_category(data, ["지역", "시군구명"]), on=["지역", "시군구명"], how="left")

    category = (
        data.groupby(["지역", "상권업종대분류명"], observed=True)
        .size()
        .reset_index(name="점포수")
        .rename(columns={"상권업종대분류명": "대분류명"})
    )
    category["지역내비중"] = category["점포수"] / category.groupby("지역", observed=True)["점포수"].transform("sum")

    district_category = (
        data.groupby(["지역", "시군구명", "상권업종대분류명"], observed=True)
        .size()
        .reset_index(name="점포수")
        .rename(columns={"상권업종대분류명": "대분류명"})
    )
    district_category["시군구내비중"] = district_category["점포수"] / district_category.groupby(
        ["지역", "시군구명"], observed=True
    )["점포수"].transform("sum")

    subcategory = (
        data.groupby(["지역", "상권업종중분류명"], observed=True)
        .size()
        .reset_index(name="점포수")
        .rename(columns={"상권업종중분류명": "중분류명"})
        .sort_values(["지역", "점포수"], ascending=[True, False])
    )
    subcategory["지역순위"] = subcategory.groupby("지역", observed=True)["점포수"].rank(method="first", ascending=False).astype(int)

    dong_category = (
        data.groupby(["지역", "시군구명", "행정동명", "상권업종대분류명"], observed=True)
        .agg(
            점포수=("상가업소번호", "size"),
            좌표점포수=("경도", "count"),
            평균경도=("경도", "mean"),
            평균위도=("위도", "mean"),
        )
        .reset_index()
        .rename(columns={"상권업종대분류명": "대분류명"})
    )

    quality_rows = []
    for region in REGION_KEYWORDS:
        region_data = data[data["지역"] == region]
        quality_rows.append(
            {
                "지역": region,
                "원본행수": int(source_rows.get(region, 0)),
                "중복제거후행수": int(len(region_data)),
                "중복제거행수": int(duplicate_counts.get(region, 0)),
                "주소누락행수": int(region_data["도로명주소"].eq("").sum()),
                "좌표보유행수": int(region_data["경도"].notna().sum()),
                "좌표누락또는이상행수": int(region_data["경도"].isna().sum()),
            }
        )
    quality = pd.DataFrame(quality_rows)

    return {
        "overview.csv": overview,
        "district.csv": district,
        "category.csv": category,
        "district_category.csv": district_category,
        "subcategory.csv": subcategory,
        "dong_category.csv": dong_category,
        "data_quality.csv": quality,
        "_metadata": pd.DataFrame(
            [{"정제전전체행수": before_dedup, "정제후전체행수": len(data)}]
        ),
    }


def main() -> None:
    args = parse_args()
    sources = discover_sources(args.input)
    frames: list[pd.DataFrame] = []
    source_rows: dict[str, int] = {}

    for region, source_name in sources:
        print(f"[{region}] 읽는 중: {Path(source_name).name}")
        region_data = read_source(args.input, region, source_name)
        source_rows[region] = source_rows.get(region, 0) + len(region_data)
        frames.append(region_data)

    combined = pd.concat(frames, ignore_index=True)
    outputs = build_outputs(combined, source_rows)
    args.output.mkdir(parents=True, exist_ok=True)

    metadata_frame = outputs.pop("_metadata")
    for filename, frame in outputs.items():
        destination = args.output / filename
        frame.to_csv(destination, index=False, encoding="utf-8-sig")
        print(f"저장: {destination} ({len(frame):,}행)")

    metadata = {
        "기준시점": "2026-06",
        "분석지역": list(REGION_KEYWORDS),
        "원본행수": source_rows,
        "정제전전체행수": int(metadata_frame.iloc[0]["정제전전체행수"]),
        "정제후전체행수": int(metadata_frame.iloc[0]["정제후전체행수"]),
    }
    (args.output / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("집계 데이터 생성이 완료되었습니다.")


if __name__ == "__main__":
    main()
