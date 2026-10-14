import os
import pandas as pd
import streamlit as st
import plotly.express as px
from analysis import load_metrics, score_metrics, make_demo_data

st.set_page_config(page_title="TrendTier | 유행어 트렌드", page_icon="📈", layout="wide")

st.markdown("""
<style>
.block-container {padding-top: 2rem; padding-bottom: 3rem;}
.hero {padding: 1.4rem 1.6rem; border-radius: 18px; background: linear-gradient(120deg,#191d2b,#313951); color: white;}
.small-muted {color: #777; font-size: .9rem;}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="hero"><h1>📈 TREND TIER</h1><p>한국 인터넷 유행어 트렌드 분석 · MVP</p></div>', unsafe_allow_html=True)
st.write("검색 관심도와 공개 댓글 신호를 비교해 유행어 순위를 탐색하는 초기 버전입니다.")

source_mode = os.getenv("DATA_MODE", "demo").lower()
if source_mode != "live":
    st.info("현재 데모 데이터 모드입니다. 아래 수치와 순위는 예시이며 실제 검색량·댓글 통계가 아닙니다.")
else:
    st.warning("실데이터 모드가 설정되어 있습니다. 각 데이터 소스의 연결 상태와 수집 시각을 확인하세요.")

try:
    raw = load_metrics()
except Exception as e:
    st.error(f"데이터를 불러오지 못했습니다: {e}")
    raw = make_demo_data()

df = score_metrics(raw)

with st.sidebar:
    st.header("필터")
    query = st.text_input("유행어 검색", placeholder="예: 밈, 신조어")
    tiers = st.multiselect("티어", ["S", "A", "B", "C"], default=["S", "A", "B", "C"])
    sort_by = st.selectbox("정렬 기준", ["종합 점수", "검색 관심도", "댓글 언급률", "상승 신호"])
    st.divider()
    st.caption("실데이터 연결은 API 권한·정책 및 환경변수 설정이 필요합니다.")

filtered = df[df["tier"].isin(tiers)].copy()
if query:
    filtered = filtered[filtered["term"].str.contains(query, case=False, na=False) |
                        filtered["meaning"].str.contains(query, case=False, na=False)]
sort_map = {"종합 점수":"score", "검색 관심도":"search_index", "댓글 언급률":"comment_rate", "상승 신호":"momentum"}
filtered = filtered.sort_values(sort_map[sort_by], ascending=False)

m1, m2, m3, m4 = st.columns(4)
m1.metric("분석 유행어", f"{len(df):,}개")
m2.metric("S 티어", f"{(df['tier']=='S').sum():,}개")
m3.metric("급상승 후보", f"{(df['momentum'] >= 65).sum():,}개")
m4.metric("데이터 상태", "데모" if source_mode != "live" else "실데이터 설정")

st.subheader("오늘의 유행어 티어")
if filtered.empty:
    st.warning("조건에 맞는 유행어가 없습니다.")
else:
    display = filtered[["rank", "term", "tier", "score", "search_index", "comment_rate", "momentum", "confidence", "meaning"]].copy()
    display.columns = ["순위", "유행어", "티어", "종합 점수", "검색 관심도", "댓글 언급률(%)", "상승 신호", "데이터 신뢰도", "뜻"]
    st.dataframe(display, hide_index=True, use_container_width=True,
                 column_config={
                     "종합 점수": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f"),
                     "검색 관심도": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f"),
                     "상승 신호": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f"),
                 })

left, right = st.columns(2)
with left:
    st.subheader("종합 점수 TOP 10")
    top = df.head(10).sort_values("score", ascending=True)
    fig = px.bar(top, x="score", y="term", orientation="h", labels={"score":"종합 점수","term":"유행어"})
    fig.update_layout(height=420, margin=dict(l=10,r=10,t=10,b=10))
    st.plotly_chart(fig, use_container_width=True)
with right:
    st.subheader("검색 관심도 vs 댓글 언급률")
    fig2 = px.scatter(df, x="search_index", y="comment_rate", color="tier", size="score",
                      hover_name="term", labels={"search_index":"검색 관심도 (정규화)", "comment_rate":"댓글 언급률 (%)", "tier":"티어"})
    fig2.update_layout(height=420, margin=dict(l=10,r=10,t=10,b=10))
    st.plotly_chart(fig2, use_container_width=True)

st.subheader("유행어 상세 보기")
options = df["term"].tolist()
selected = st.selectbox("유행어 선택", options)
row = df[df["term"] == selected].iloc[0]
c1, c2, c3 = st.columns(3)
c1.metric("티어", row["tier"])
c2.metric("종합 점수", f"{row['score']:.1f}/100")
c3.metric("신뢰도", row["confidence"])
st.write(f"**뜻/설명:** {row['meaning']}")
st.write(f"**검색 관심도:** {row['search_index']:.1f} / 100")
st.write(f"**댓글 언급률:** {row['comment_rate']:.3f}%")
st.write(f"**상승 신호:** {row['momentum']:.1f} / 100")
st.caption("현재 상승 신호와 신뢰도는 MVP의 예시 계산식이며, 실제 데이터가 쌓이면 백테스트로 조정해야 합니다.")

st.divider()
st.caption("TrendTier MVP · 검색 관심도는 실제 검색 횟수와 같지 않으며, 댓글 표본은 전체 SNS나 특정 연령대 전체를 대표하지 않습니다.")
