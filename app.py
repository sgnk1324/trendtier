import os
import pandas as pd
import streamlit as st
import plotly.express as px
from analysis import load_metrics, score_metrics, make_demo_data
from collectors.youtube_comments import fetch_comment_threads
import re

st.set_page_config(page_title="TrendTier | 유행어 트렌드", page_icon="📈", layout="wide")

# Streamlit Community Cloud secrets -> environment variable used by collector.
try:
    if st.secrets.get("YOUTUBE_API_KEY"):
        os.environ["YOUTUBE_API_KEY"] = st.secrets["YOUTUBE_API_KEY"]
except Exception:
    pass

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
    st.divider()
    st.subheader("YouTube 댓글 실험")
    video_input = st.text_area(
        "YouTube 영상 URL 또는 영상 ID",
        placeholder="영상 URL/ID를 한 줄에 하나씩 입력 (최대 3개 권장)",
        help="공개 댓글이 허용된 영상만 가능합니다. API 할당량을 아끼기 위해 처음에는 1~3개로 테스트하세요."
    )
    if st.button("공개 댓글 수집 및 유행어 언급 분석", type="primary"):
        video_ids = []
        for line in video_input.splitlines():
            value = line.strip()
            if not value:
                continue
            match = re.search(r"(?:v=|youtu\.be/|shorts/|embed/)([A-Za-z0-9_-]{11})", value)
            video_id = match.group(1) if match else value
            if re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
                video_ids.append(video_id)
        video_ids = list(dict.fromkeys(video_ids))[:3]
        if not video_ids:
            st.error("유효한 YouTube 영상 URL 또는 11자리 영상 ID를 입력해 주세요.")
        elif not os.getenv("YOUTUBE_API_KEY"):
            st.error("API 키를 찾지 못했습니다. Streamlit의 Manage app → Settings → Secrets에 YOUTUBE_API_KEY를 저장했는지 확인하세요.")
        else:
            all_comments = []
            failures = []
            with st.spinner("공개 댓글을 수집하고 있습니다. 잠시 기다려 주세요..."):
                for video_id in video_ids:
                    try:
                        all_comments.extend(fetch_comment_threads(video_id, max_pages=1, max_results=100))
                    except Exception as exc:
                        failures.append(f"{video_id}: {exc}")
            if failures:
                for failure in failures:
                    st.warning(failure)
            if all_comments:
                comments_df = pd.DataFrame(all_comments)
                texts = comments_df["text"].fillna("").astype(str)
                st.success(f"댓글 {len(comments_df):,}개 수집 완료 · 영상 {len(video_ids)}개 입력")
                st.caption("표본은 입력한 영상의 최신 공개 댓글 최대 100개/영상입니다. 한국 10~20대 전체의 대표 표본은 아닙니다.")
                live_rows = []
                for _, item in raw.iterrows():
                    term = str(item["term"])
                    mentions = int(texts.str.contains(re.escape(term), case=False, regex=True, na=False).sum())
                    live_rows.append({"유행어": term, "언급 댓글 수": mentions, "수집 댓글 대비 언급률(%)": round(mentions / len(texts) * 100, 2)})
                live_df = pd.DataFrame(live_rows).sort_values(["언급 댓글 수", "유행어"], ascending=[False, True])
                st.subheader("입력한 영상의 공개 댓글 기준 언급 순위")
                st.dataframe(live_df, hide_index=True, use_container_width=True)
                st.caption("이 표만이 이번 실행에서 실제 수집한 YouTube 댓글 기반 결과입니다. 메인 대시보드의 검색 관심도와 종합 점수는 아직 데모 데이터입니다.")
            else:
                st.error("댓글을 가져오지 못했습니다. 댓글 사용 중지 여부, 영상 ID, API 활성화 및 할당량을 확인하세요.")

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
