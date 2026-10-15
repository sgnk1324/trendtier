
import os
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd


DB_PATH = Path(os.getenv("DB_PATH", "trendtier.db"))
METRICS_CSV = Path(os.getenv("METRICS_CSV", "data/metrics.csv"))
COMMENT_METRICS_CSV = Path(
    os.getenv("COMMENT_METRICS_CSV", "data/comment_metrics.csv")
)


def make_demo_data():
    rows = [
        ("알잘딱깔센", "알아서 잘 딱 깔끔하고 센스 있게", 82, 0.91, 78, 0.83),
        ("폼 미쳤다", "실력이나 분위기가 매우 좋다는 표현", 74, 0.74, 63, 0.69),
        ("억까", "억지로 비난하거나 불리하게 몰아가는 상황", 69, 0.66, 58, 0.61),
        ("킹받네", "매우 짜증 나지만 웃긴 상황", 62, 0.72, 41, 0.53),
        ("갓생", "성실하고 계획적으로 사는 생활", 57, 0.38, 32, 0.42),
        ("중꺾마", "중요한 것은 꺾이지 않는 마음", 51, 0.31, 26, 0.35),
        ("내또출", "내일 또 출근", 45, 0.27, 39, 0.47),
        ("럭키비키", "긍정적으로 해석하는 태도", 43, 0.58, 48, 0.74),
        ("스불재", "스스로 불러온 재앙", 38, 0.23, 21, 0.29),
        ("완내스", "완전 내 스타일", 34, 0.18, 17, 0.24),
        ("오히려 좋아", "상황을 긍정적으로 받아들이는 말", 31, 0.24, 13, 0.18),
        ("쩐다", "대단하거나 놀랍다는 표현", 29, 0.42, 9, 0.12),
    ]

    return pd.DataFrame(
        rows,
        columns=[
            "term",
            "meaning",
            "search_index",
            "comment_rate",
            "search_growth",
            "comment_growth",
        ],
    )


def load_metrics():
    """검색 지표와 최신 YouTube 댓글 지표를 결합한다."""

    # 1. 검색 지표 또는 기본 데이터를 불러온다.
    if METRICS_CSV.exists():
        df = pd.read_csv(METRICS_CSV)
    elif DB_PATH.exists():
        with sqlite3.connect(DB_PATH) as conn:
            df = pd.read_sql_query(
                """
                SELECT term, meaning, search_index,
                       comment_rate, search_growth, comment_growth
                FROM daily_metrics
                WHERE date = (
                    SELECT MAX(date) FROM daily_metrics
                )
                """,
                conn,
            )
        if df.empty:
            df = make_demo_data()
    else:
        df = make_demo_data()

    if "term" not in df.columns:
        raise ValueError("데이터 파일에 term 컬럼이 없습니다.")

    defaults = {
        "meaning": "",
        "search_index": 0,
        "comment_rate": 0,
        "search_growth": 0,
        "comment_growth": 0,
    }

    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default

    # 2. 최신 댓글 지표를 읽는다.
    if COMMENT_METRICS_CSV.exists():
        comments = pd.read_csv(COMMENT_METRICS_CSV)

        if (
            not comments.empty
            and "term" in comments.columns
            and "date" in comments.columns
        ):
            comments["date"] = comments["date"].astype(str)
            latest_date = comments["date"].max()
            latest = comments.loc[
                comments["date"] == latest_date
            ].copy()

            # CSV에 이미 계산된 언급률을 사용한다.
            columns = [
                col for col in
                ["term", "comment_rate", "comment_growth"]
                if col in latest.columns
            ]

            if "term" in columns:
                latest = latest[columns].drop_duplicates(
                    subset=["term"], keep="last"
                )

                # 기존 댓글 수치를 최신 수집값으로 대체한다.
                replace_cols = [
                    col for col in
                    ["comment_rate", "comment_growth"]
                    if col in latest.columns
                ]

                df = df.drop(columns=replace_cols, errors="ignore")
                df = df.merge(latest, on="term", how="left")

    # 3. 숫자 형식과 누락값을 정리한다.
    for col in [
        "search_index",
        "comment_rate",
        "search_growth",
        "comment_growth",
    ]:
        if col not in df.columns:
            df[col] = 0

        df[col] = pd.to_numeric(
            df[col], errors="coerce"
        ).fillna(0)

    df["term"] = df["term"].fillna("").astype(str)
    df["meaning"] = df["meaning"].fillna("").astype(str)

    return df.drop_duplicates(subset=["term"], keep="last")


def _percentile_score(series):
    values = pd.to_numeric(series, errors="coerce").fillna(0)

    if values.empty:
        return pd.Series(index=values.index, dtype=float)

    if values.max() == values.min():
        return pd.Series(50.0, index=values.index)

    return values.rank(pct=True, method="average") * 100


def score_metrics(raw):
    """검색과 댓글 지표를 정규화해 종합 점수와 티어를 계산한다."""
    df = raw.copy()

    columns = [
        "search_index",
        "comment_rate",
        "search_growth",
        "comment_growth",
    ]

    for col in columns:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(
            df[col], errors="coerce"
        ).fillna(0)

    df["n_search"] = _percentile_score(df["search_index"])
    df["n_search_growth"] = _percentile_score(df["search_growth"])
    df["n_comment"] = _percentile_score(df["comment_rate"])
    df["n_comment_growth"] = _percentile_score(df["comment_growth"])

    df["score"] = (
        0.35 * df["n_search"]
        + 0.20 * df["n_search_growth"]
        + 0.30 * df["n_comment"]
        + 0.15 * df["n_comment_growth"]
    ).round(1)

    df["momentum"] = (
        0.5 * df["n_search_growth"]
        + 0.5 * df["n_comment_growth"]
    ).round(1)

    percentile = df["score"].rank(
        pct=True, ascending=False, method="min"
    )

    df["tier"] = np.select(
        [
            percentile <= 0.10,
            percentile <= 0.30,
            percentile <= 0.70,
        ],
        ["S", "A", "B"],
        default="C",
    )

    has_search = df["search_index"] > 0
    has_comments = df["comment_rate"] > 0

    df["confidence"] = np.select(
        [
            has_search & has_comments,
            has_comments,
            has_search,
        ],
        [
            "교차 신호",
            "댓글 신호",
            "검색 신호",
        ],
        default="데이터 부족",
    )

    df = df.sort_values(
        "score", ascending=False
    ).reset_index(drop=True)

    df["rank"] = np.arange(1, len(df) + 1)

    return df
