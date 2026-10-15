import os
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

DB_PATH = os.getenv("DB_PATH", "trendtier.db")
METRICS_CSV = Path(os.getenv("METRICS_CSV", "data/metrics.csv"))
COMMENT_METRICS_CSV = Path(
    os.getenv("COMMENT_METRICS_CSV", "data/comment_metrics.csv")
)


def make_demo_data():
    """실제 데이터가 없을 때 사용하는 예시 데이터."""
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
            "term", "meaning", "search_index", "comment_rate",
            "search_growth", "comment_growth",
        ],
    )


def _normalise_comment_columns(df):
    """댓글 CSV의 컬럼명을 내부 표준 이름으로 맞춘다."""
    df = df.copy()

    aliases = {
        "유행어": "term",
        "word": "term",
        "keyword": "term",
        "언급률": "comment_rate",
        "mention_rate": "comment_rate",
        "언급수": "mention_count",
        "mentions": "mention_count",
        "date": "date",
        "수집일": "date",
        "수집일자": "date",
    }

    rename = {
        old: new
        for old, new in aliases.items()
        if old in df.columns and new not in df.columns
    }
    return df.rename(columns=rename)


def _load_comment_metrics():
    """댓글 지표 파일에서 가장 최근 날짜의 기록을 가져온다."""
    if not COMMENT_METRICS_CSV.exists():
        return None

    comments = pd.read_csv(COMMENT_METRICS_CSV)
    comments = _normalise_comment_columns(comments)

    if comments.empty or "term" not in comments.columns:
        return None

    if "date" in comments.columns:
        comments["date"] = pd.to_datetime(
            comments["date"], errors="coerce"
        )
        valid_dates = comments["date"].dropna()

        if not valid_dates.empty:
            latest_date = valid_dates.max()
            comments = comments[comments["date"] == latest_date].copy()

    # 언급 수와 댓글 수가 있으면 언급률을 계산한다.
    if "comment_rate" not in comments.columns:
        mention_col = next(
            (c for c in ["mention_count", "mentions", "count", "언급수"]
             if c in comments.columns),
            None,
        )
        total_col = next(
            (c for c in ["total_comments", "comment_count", "sample_size"]
             if c in comments.columns),
            None,
        )

        if mention_col and total_col:
            mentions = pd.to_numeric(
                comments[mention_col], errors="coerce"
            ).fillna(0)
            totals = pd.to_numeric(
                comments[total_col], errors="coerce"
            ).replace(0, np.nan)

            comments["comment_rate"] = (
                mentions / totals * 100
            ).fillna(0)

    keep = ["term"]
    for col in ["comment_rate", "comment_growth"]:
        if col in comments.columns:
            keep.append(col)

    if len(keep) == 1:
        return None

    result = comments[keep].copy()

    for col in ["comment_rate", "comment_growth"]:
        if col in result.columns:
            result[col] = pd.to_numeric(
                result[col], errors="coerce"
            ).fillna(0)

    return result.drop_duplicates(subset=["term"], keep="last")


def load_metrics():
    """기존 검색 지표와 최신 댓글 지표를 유행어 이름으로 결합한다."""
    if METRICS_CSV.exists():
        df = pd.read_csv(METRICS_CSV)
    else:
        db = Path(DB_PATH)

        if db.exists():
            with sqlite3.connect(db) as conn:
                df = pd.read_sql_query(
                    """
                    SELECT term, meaning, search_index,
                           comment_rate, search_growth, comment_growth
                    FROM daily_metrics
                    WHERE date = (SELECT MAX(date) FROM daily_metrics)
                    """,
                    conn,
                )
        else:
            df = make_demo_data()

    if "term" not in df.columns:
        raise ValueError(
            "metrics.csv에 term 컬럼이 없습니다. CSV의 첫 행을 확인하세요."
        )

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

    comment_data = _load_comment_metrics()

    if comment_data is not None:
        # 기존 댓글 지표를 제거하고 최신 수집 결과로 교체한다.
        replace_cols = [
            col for col in ["comment_rate", "comment_growth"]
            if col in comment_data.columns
        ]
        df = df.drop(columns=replace_cols, errors="ignore")
        df = df.merge(comment_data, on="term", how="left")

    for col in [
        "search_index", "comment_rate",
        "search_growth", "comment_growth",
    ]:
        df[col] = pd.to_numeric(
            df[col], errors="coerce"
        ).fillna(0)

    df["term"] = df["term"].fillna("").astype(str)
    df["meaning"] = df["meaning"].fillna("").astype(str)

    return df.drop_duplicates(subset=["term"], keep="last")


def _pct(series):
    """후보 유행어 집합 내 백분위 점수."""
    values = pd.to_numeric(series, errors="coerce").fillna(0)

    if values.empty:
        return pd.Series(dtype=float, index=values.index)

    if values.max() == values.min():
        return pd.Series(
            np.full(len(values), 50.0), index=values.index
        )

    return (values.rank(pct=True, method="average") * 100).clip(0, 100)


def score_metrics(raw):
    """검색·댓글 지표를 결합해 순위와 티어를 계산한다."""
    df = raw.copy()

    required = [
        "search_index", "comment_rate",
        "search_growth", "comment_growth",
    ]

    for col in required:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(
            df[col], errors="coerce"
        ).fillna(0)

    df["n_search"] = _pct(df["search_index"])
    df["n_search_growth"] = _pct(df["search_growth"])
    df["n_comment"] = _pct(df["comment_rate"])
    df["n_comment_growth"] = _pct(df["comment_growth"])

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
        [has_search & has_comments, has_comments, has_search],
        ["교차 신호", "댓글 신호", "검색 신호"],
        default="데이터 부족",
    )

    df = df.sort_values(
        "score", ascending=False
    ).reset_index(drop=True)

    df["rank"] = np.arange(1, len(df) + 1)

    return df
