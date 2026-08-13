from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st


APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
SOURCE_URL = "https://drive.google.com/drive/folders/1ZEBVyAv01XGK5J3L_ERc-IPH7npCM_J4?usp=drive_link"
REGION_COLORS = {"대구": "#2563EB", "경북": "#F97316"}


st.set_page_config(
    page_title="대구·경북 소상공인 상권 리포트",
    page_icon="🏪",
    layout="wide",
)

st.markdown(
    """
    <style>
    .block-container {padding-top: 1.8rem; padding-bottom: 3rem;}
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 16px 18px;
        box-shadow: 0 4px 14px rgba(15, 23, 42, 0.05);
    }
    [data-testid="stMetricLabel"] {color: #475569;}
    .report-note {
        padding: 14px 16px;
        border-radius: 12px;
        background: #eff6ff;
        border-left: 4px solid #2563eb;
        color: #1e3a8a;
        margin-bottom: 18px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def load_csv(filename: str) -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / filename, encoding="utf-8-sig")


def format_count(value: int | float) -> str:
    return f"{int(value):,}개"


def filtered_data(
    frame: pd.DataFrame,
    regions: list[str],
    districts: list[str],
    categories: list[str],
) -> pd.DataFrame:
    result = frame[frame["지역"].isin(regions)].copy()
    if districts and "시군구명" in result.columns:
        result = result[result["시군구명"].isin(districts)]
    if categories and "대분류명" in result.columns:
        result = result[result["대분류명"].isin(categories)]
    return result


try:
    overview = load_csv("overview.csv")
    district = load_csv("district.csv")
    category = load_csv("category.csv")
    district_category = load_csv("district_category.csv")
    subcategory = load_csv("subcategory.csv")
    dong_category = load_csv("dong_category.csv")
    data_quality = load_csv("data_quality.csv")
except FileNotFoundError:
    st.error("집계 데이터가 없습니다. 먼저 `prepare_data.py`를 실행해 data 폴더를 생성해 주세요.")
    st.stop()


st.title("대구·경북 소상공인 상권 리포트")
st.caption("소상공인시장진흥공단 상가(상권)정보 · 2026년 6월 기준")
st.markdown(
    '<div class="report-note"><b>분석 질문</b> — 대구와 경북의 점포는 어느 지역과 업종에 집중되어 있으며, 두 지역의 상권 구조는 어떻게 다른가?</div>',
    unsafe_allow_html=True,
)

region_options = [region for region in ["대구", "경북"] if region in district_category["지역"].unique()]
selected_regions = st.sidebar.multiselect("지역", region_options, default=region_options)
if not selected_regions:
    st.sidebar.warning("지역을 한 곳 이상 선택해 주세요.")
    st.stop()

district_options = sorted(
    district_category.loc[district_category["지역"].isin(selected_regions), "시군구명"].unique()
)
selected_districts = st.sidebar.multiselect("시군구", district_options, placeholder="전체 시군구")

category_options = sorted(
    district_category.loc[district_category["지역"].isin(selected_regions), "대분류명"].unique()
)
selected_categories = st.sidebar.multiselect("업종 대분류", category_options, placeholder="전체 업종")
st.sidebar.divider()
st.sidebar.caption("선택하지 않은 항목은 전체로 계산됩니다.")
st.sidebar.link_button("원본 데이터 폴더 열기", SOURCE_URL, use_container_width=True)

current = filtered_data(
    district_category, selected_regions, selected_districts, selected_categories
)
if current.empty:
    st.warning("선택한 조건에 해당하는 데이터가 없습니다.")
    st.stop()

total_stores = int(current["점포수"].sum())
district_count = int(current["시군구명"].nunique())
category_count = int(current["대분류명"].nunique())
top_category_row = current.groupby("대분류명", as_index=False)["점포수"].sum().nlargest(1, "점포수").iloc[0]

metric_columns = st.columns(4)
metric_columns[0].metric("선택 범위 점포", format_count(total_stores))
metric_columns[1].metric("시군구", f"{district_count}곳")
metric_columns[2].metric("업종 대분류", f"{category_count}개")
metric_columns[3].metric("가장 많은 업종", str(top_category_row["대분류명"]), format_count(top_category_row["점포수"]))

tab_overview, tab_district, tab_map, tab_method = st.tabs(
    ["한눈에 보기", "지역·업종 상세", "상권 분포 지도", "데이터·분석 기준"]
)

with tab_overview:
    region_summary = current.groupby("지역", as_index=False)["점포수"].sum()
    category_summary = (
        current.groupby("대분류명", as_index=False)["점포수"]
        .sum()
        .sort_values("점포수", ascending=False)
    )
    district_summary = (
        current.groupby(["지역", "시군구명"], as_index=False)["점포수"]
        .sum()
        .nlargest(15, "점포수")
        .sort_values("점포수")
    )

    left, right = st.columns([0.9, 1.4])
    with left:
        st.subheader("지역별 점포 비교")
        region_chart = (
            alt.Chart(region_summary)
            .mark_bar(cornerRadiusTopLeft=8, cornerRadiusTopRight=8)
            .encode(
                x=alt.X("지역:N", title=None, sort=region_options),
                y=alt.Y("점포수:Q", title="점포 수", axis=alt.Axis(format=",")),
                color=alt.Color(
                    "지역:N",
                    title=None,
                    scale=alt.Scale(domain=list(REGION_COLORS), range=list(REGION_COLORS.values())),
                    legend=None,
                ),
                tooltip=["지역:N", alt.Tooltip("점포수:Q", format=",")],
            )
            .properties(height=330)
        )
        st.altair_chart(region_chart, use_container_width=True)

    with right:
        st.subheader("상위 업종 구성")
        top_categories = category_summary.head(10)
        category_chart = (
            alt.Chart(top_categories)
            .mark_bar(cornerRadiusEnd=6, color="#0F766E")
            .encode(
                x=alt.X("점포수:Q", title="점포 수", axis=alt.Axis(format=",")),
                y=alt.Y("대분류명:N", title=None, sort="-x"),
                tooltip=["대분류명:N", alt.Tooltip("점포수:Q", format=",")],
            )
            .properties(height=330)
        )
        st.altair_chart(category_chart, use_container_width=True)

    st.subheader("점포가 많은 시군구 TOP 15")
    district_chart = (
        alt.Chart(district_summary)
        .mark_bar(cornerRadiusEnd=5)
        .encode(
            x=alt.X("점포수:Q", title="점포 수", axis=alt.Axis(format=",")),
            y=alt.Y("시군구명:N", title=None, sort=alt.EncodingSortField(field="점포수", order="descending")),
            color=alt.Color(
                "지역:N",
                title="지역",
                scale=alt.Scale(domain=list(REGION_COLORS), range=list(REGION_COLORS.values())),
            ),
            tooltip=["지역:N", "시군구명:N", alt.Tooltip("점포수:Q", format=",")],
        )
        .properties(height=460)
    )
    st.altair_chart(district_chart, use_container_width=True)

with tab_district:
    st.subheader("시군구별 업종 구조")
    heatmap_source = current.copy()
    top_district_names = (
        heatmap_source.groupby("시군구명")["점포수"].sum().nlargest(18).index
    )
    top_category_names = (
        heatmap_source.groupby("대분류명")["점포수"].sum().nlargest(10).index
    )
    heatmap_source = heatmap_source[
        heatmap_source["시군구명"].isin(top_district_names)
        & heatmap_source["대분류명"].isin(top_category_names)
    ]
    heatmap = (
        alt.Chart(heatmap_source)
        .mark_rect(cornerRadius=2)
        .encode(
            x=alt.X("대분류명:N", title=None, axis=alt.Axis(labelAngle=-35)),
            y=alt.Y("시군구명:N", title=None),
            color=alt.Color("점포수:Q", title="점포 수", scale=alt.Scale(scheme="blues")),
            tooltip=["지역:N", "시군구명:N", "대분류명:N", alt.Tooltip("점포수:Q", format=",")],
        )
        .properties(height=520)
    )
    st.altair_chart(heatmap, use_container_width=True)

    table = current.sort_values("점포수", ascending=False).copy()
    table["시군구내비중"] = table["시군구내비중"].map(lambda value: f"{value:.1%}")
    st.dataframe(
        table.rename(columns={"시군구내비중": "시군구 내 비중"}),
        use_container_width=True,
        hide_index=True,
    )
    st.download_button(
        "현재 표 CSV 내려받기",
        data=current.to_csv(index=False, encoding="utf-8-sig"),
        file_name="filtered_district_category.csv",
        mime="text/csv",
    )

with tab_map:
    map_source = filtered_data(
        dong_category, selected_regions, selected_districts, selected_categories
    )
    map_source = map_source.dropna(subset=["평균경도", "평균위도"]).copy()
    map_source["경도합"] = map_source["평균경도"] * map_source["좌표점포수"]
    map_source["위도합"] = map_source["평균위도"] * map_source["좌표점포수"]
    map_points = (
        map_source.groupby(["지역", "시군구명", "행정동명"], as_index=False)
        .agg(
            점포수=("점포수", "sum"),
            좌표점포수=("좌표점포수", "sum"),
            경도합=("경도합", "sum"),
            위도합=("위도합", "sum"),
        )
    )
    map_points["경도"] = map_points["경도합"] / map_points["좌표점포수"]
    map_points["위도"] = map_points["위도합"] / map_points["좌표점포수"]
    map_points["지도크기"] = map_points["점포수"].clip(lower=1)

    st.subheader("행정동별 점포 분포")
    st.caption("점의 크기는 선택 조건에 해당하는 점포 수를 나타냅니다. 위치는 행정동 내 점포 좌표의 평균값입니다.")
    if map_points.empty:
        st.info("표시할 좌표 데이터가 없습니다.")
    else:
        st.map(
            map_points,
            latitude="위도",
            longitude="경도",
            size="지도크기",
            color="#2563EBB8",
            use_container_width=True,
        )
        st.dataframe(
            map_points[["지역", "시군구명", "행정동명", "점포수"]]
            .sort_values("점포수", ascending=False)
            .head(20),
            use_container_width=True,
            hide_index=True,
        )

with tab_method:
    st.subheader("데이터 출처와 분석 범위")
    st.markdown(
        f"""
        - 원본: [소상공인시장진흥공단 상가(상권)정보 공유 폴더]({SOURCE_URL})
        - 기준 시점: 2026년 6월
        - 분석 지역: 대구광역시, 경상북도
        - 주요 분석 단위: 점포, 시군구, 행정동, 상권업종 대·중분류
        """
    )
    st.warning(
        "이 데이터는 상가 업소의 위치와 업종 현황을 보여 줍니다. 매출액, 유동인구, 폐업 여부가 없으므로 "
        "매출 성과나 폐업 위험을 직접 판단하는 자료로 사용하면 안 됩니다."
    )
    st.subheader("데이터 품질 점검")
    st.dataframe(data_quality, use_container_width=True, hide_index=True)
    st.subheader("업종 중분류 상위 항목")
    method_subcategory = subcategory[
        subcategory["지역"].isin(selected_regions) & (subcategory["지역순위"] <= 15)
    ]
    st.dataframe(method_subcategory, use_container_width=True, hide_index=True)

st.divider()
st.caption("교육 실습용 리포트 · 원본 대용량 파일은 GitHub가 아닌 Google Drive에서 관리합니다.")
