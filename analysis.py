import os
import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path

DB_PATH = os.getenv("DB_PATH", "trendtier.db")

def make_demo_data():
    # Synthetic illustrative values. Never present as live platform data.
    rows = [
        ("알잘딱깔센","알아서 잘 딱 깔끔하고 센스 있게",82,0.91,78,0.83),
        ("폼 미쳤다","실력이나 분위기가 매우 좋다는 표현",74,0.74,63,0.69),
        ("억까","억지로 비난하거나 불리하게 몰아가는 상황",69,0.66,58,0.61),
        ("킹받네","매우 짜증 나지만 웃긴 상황",62,0.72,41,0.53),
        ("갓생","성실하고 계획적으로 사는 생활",57,0.38,32,0.42),
        ("중꺾마","중요한 것은 꺾이지 않는 마음",51,0.31,26,0.35),
        ("내또출","내일 또 출근",45,0.27,39,0.47),
        ("럭키비키","긍정적으로 해석하는 태도",43,0.58,48,0.74),
        ("스불재","스스로 불러온 재앙",38,0.23,21,0.29),
        ("완내스","완전 내 스타일",34,0.18,17,0.24),
        ("오히려 좋아","상황을 긍정적으로 받아들이는 말",31,0.24,13,0.18),
        ("쩐다","대단하거나 놀랍다는 표현",29,0.42,9,0.12),
    ]
    return pd.DataFrame(rows, columns=["term","meaning","search_index","comment_rate","search_growth","comment_growth"])

def load_metrics():
    csv_path = Path(os.getenv("METRICS_CSV", "data/metrics.csv"))
    if csv_path.exists():
        df = pd.read_csv(csv_path)
        required = {"term","meaning","search_index","comment_rate","search_growth","comment_growth"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError("metrics.csv 필수 컬럼 누락: " + ", ".join(sorted(missing)))
        return df
    db = Path(DB_PATH)
    if db.exists():
        with sqlite3.connect(db) as conn:
            df = pd.read_sql_query("""
                SELECT term, meaning, search_index, comment_rate, search_growth, comment_growth
                FROM daily_metrics
                WHERE date = (SELECT MAX(date) FROM daily_metrics)
            """, conn)
        if not df.empty:
            return df
    return make_demo_data()

def _pct(series):
    s = pd.to_numeric(series, errors="coerce").fillna(0)
    if s.max() == s.min():
        return pd.Series(np.full(len(s), 50.0), index=s.index)
    return (s.rank(pct=True, method="average") * 100).clip(0,100)

def score_metrics(raw):
    df = raw.copy()
    for c in ["search_index","comment_rate","search_growth","comment_growth"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    # Normalize each signal across the same candidate set.
    df["n_search"] = _pct(df["search_index"])
    df["n_search_growth"] = _pct(df["search_growth"])
    df["n_comment"] = _pct(df["comment_rate"])
    df["n_comment_growth"] = _pct(df["comment_growth"])
    df["score"] = (0.35*df["n_search"] + 0.20*df["n_search_growth"] +
                   0.30*df["n_comment"] + 0.15*df["n_comment_growth"]).round(1)
    df["momentum"] = (0.5*df["n_search_growth"] + 0.5*df["n_comment_growth"]).round(1)
    # Percentile tiers; demo set and candidate set are small, so label as provisional.
    pct = df["score"].rank(pct=True, ascending=False, method="min")
    df["tier"] = np.select([pct <= .10, pct <= .30, pct <= .70], ["S","A","B"], default="C")
    # Confidence is only a data-availability label in this MVP, not statistical certainty.
    both = (df["search_index"] > 0) & (df["comment_rate"] > 0)
    df["confidence"] = np.where(both, "교차 신호", "잠정")
    df = df.sort_values("score", ascending=False).reset_index(drop=True)
    df["rank"] = np.arange(1, len(df)+1)
    return df
