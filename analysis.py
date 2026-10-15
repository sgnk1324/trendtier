
"""TrendTier: daily YouTube comment collection."""

import os
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from collectors.youtube_comments import fetch_comment_threads


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"

VIDEOS_FILE = DATA_DIR / "youtube_videos.txt"
TERMS_FILE = DATA_DIR / "metrics.csv"
OUTPUT_FILE = DATA_DIR / "comment_metrics.csv"
HISTORY_FILE = DATA_DIR / "comment_history.csv"
RAW_COMMENTS_FILE = DATA_DIR / "comment_texts.csv"


def load_video_ids():
    if not VIDEOS_FILE.exists():
        raise FileNotFoundError(
            f"영상 목록 파일이 없습니다: {VIDEOS_FILE}"
        )

    ids = []

    for raw in VIDEOS_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()

        if not line or line.startswith("#"):
            continue

        match = re.search(
            r"(?:v=|youtu\.be/|shorts/|embed/)([A-Za-z0-9_-]{11})",
            line,
        )
        video_id = match.group(1) if match else line

        if re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
            ids.append(video_id)
        else:
            print(f"Skipping invalid video entry: {line}")

    return list(dict.fromkeys(ids))


def main():
    if not os.getenv("YOUTUBE_API_KEY"):
        raise RuntimeError("YOUTUBE_API_KEY secret is missing")

    video_ids = load_video_ids()

    if not video_ids:
        raise RuntimeError("유효한 YouTube 영상 URL이 없습니다.")

    terms_df = pd.read_csv(TERMS_FILE)

    if "term" not in terms_df.columns:
        raise ValueError("data/metrics.csv에 term 컬럼이 없습니다.")

    terms = [
        str(value).strip()
        for value in terms_df["term"].dropna()
        if str(value).strip()
    ]

    all_comments = []
    successful_videos = 0

    for video_id in video_ids:
        try:
            comments = fetch_comment_threads(
                video_id,
                max_pages=1,
                max_results=100,
            )

            all_comments.extend(comments)
            successful_videos += 1

            print(
                f"{video_id}: collected "
                f"{len(comments)} top-level comments"
            )

        except Exception as exc:
            print(f"WARNING: video {video_id} failed: {exc}")

    if not all_comments:
        raise RuntimeError(
            "댓글을 수집하지 못했습니다. "
            "영상 공개 여부, API 키, API 할당량을 확인하세요."
        )

    today = datetime.now(timezone.utc).date().isoformat()
    collected_at = datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    )

    # 1. 원본 댓글 저장: 이후 새로운 표현을 발굴하는 데 사용한다.
    raw_rows = []

    for comment in all_comments:
        raw_rows.append({
            "date": today,
            "video_id": comment.get("video_id", ""),
            "comment_id": comment.get("comment_id", ""),
            "published_at": comment.get("published_at", ""),
            "text": comment.get("text", ""),
            "collected_at_utc": collected_at,
        })

    raw_df = pd.DataFrame(raw_rows)

    # 기존 수집 기록을 보존하고 중복 댓글은 제거한다.
    if RAW_COMMENTS_FILE.exists():
        old_raw = pd.read_csv(
            RAW_COMMENTS_FILE,
            dtype=str,
            keep_default_na=False,
        )
        raw_df = pd.concat(
            [old_raw, raw_df],
            ignore_index=True,
        )

    if "comment_id" in raw_df.columns:
        raw_df = raw_df.drop_duplicates(
            subset=["comment_id"],
            keep="last",
        )

    raw_df.to_csv(
        RAW_COMMENTS_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    # 2. 기존 유행어 지표도 계속 계산한다.
    texts = [
        str(comment.get("text", ""))
        for comment in all_comments
    ]
    total = len(texts)
    rows = []

    for term in terms:
        mentions = sum(
            1 for text in texts
            if term.casefold() in text.casefold()
        )

        rows.append({
            "date": today,
            "term": term,
            "mentions": mentions,
            "total_comments": total,
            "comment_rate": (
                round(mentions / total * 100, 4)
                if total else 0.0
            ),
            "videos_requested": len(video_ids),
            "videos_collected": successful_videos,
            "collected_at_utc": collected_at,
        })

    current = pd.DataFrame(rows)

    if HISTORY_FILE.exists():
        history = pd.read_csv(HISTORY_FILE)
    else:
        history = pd.DataFrame(
            columns=current.columns.tolist() + ["comment_growth"]
        )

    # 이전 수집 결과와 언급률을 비교한다.
    growth_values = []

    for _, row in current.iterrows():
        if (
            not history.empty
            and {"term", "date", "comment_rate"}.issubset(
                history.columns
            )
        ):
            previous = history[
                (history["term"] == row["term"])
                & (history["date"] < today)
            ]
        else:
            previous = pd.DataFrame()

        if not previous.empty:
            previous = previous.sort_values("date")
            growth = (
                float(row["comment_rate"])
                - float(previous.iloc[-1]["comment_rate"])
            )
            growth_values.append(round(growth, 4))
        else:
            growth_values.append(0.0)

    current["comment_growth"] = growth_values

    # 날짜별 기록은 유행어마다 한 행만 유지한다.
    if not history.empty:
        combined = pd.concat(
            [history, current],
            ignore_index=True,
            sort=False,
        )
    else:
        combined = current.copy()

    combined = combined.drop_duplicates(
        subset=["date", "term"],
        keep="last",
    )

    combined.to_csv(
        HISTORY_FILE,
        index=False,
        encoding="utf-8-sig",
    )
    current.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print(
        f"SUCCESS: {total} comments from "
        f"{successful_videos}/{len(video_ids)} videos"
    )
    print(f"Saved raw comments to: {RAW_COMMENTS_FILE}")
    print(f"Saved metrics to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
