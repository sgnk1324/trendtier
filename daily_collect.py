"""Daily public YouTube comment collection for TrendTier using the official API."""
from __future__ import annotations
import os
import re
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
from collectors.youtube_comments import fetch_comment_threads

ROOT = Path(__file__).resolve().parent
VIDEOS_FILE = ROOT / "data" / "youtube_videos.txt"
TERMS_FILE = ROOT / "data" / "metrics.csv"
OUTPUT_FILE = ROOT / "data" / "comment_metrics.csv"
HISTORY_FILE = ROOT / "data" / "comment_history.csv"


def load_video_ids() -> list[str]:
    if not VIDEOS_FILE.exists():
        raise FileNotFoundError(f"영상 목록 파일이 없습니다: {VIDEOS_FILE}")
    ids = []
    for raw in VIDEOS_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = re.search(r"(?:v=|youtu\.be/|shorts/|embed/)([A-Za-z0-9_-]{11})", line)
        video_id = match.group(1) if match else line
        if re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
            ids.append(video_id)
        else:
            print(f"Skipping invalid video entry: {line}")
    return list(dict.fromkeys(ids))


def main() -> None:
    if not os.getenv("YOUTUBE_API_KEY"):
        raise RuntimeError("YOUTUBE_API_KEY secret is missing")
    video_ids = load_video_ids()
    if not video_ids:
        raise RuntimeError("data/youtube_videos.txt에 실제 YouTube 영상 URL 또는 ID를 한 줄에 하나씩 추가하세요.")
    terms_df = pd.read_csv(TERMS_FILE)
    if "term" not in terms_df.columns:
        raise ValueError("data/metrics.csv에 term 컬럼이 없습니다.")
    terms = [str(x).strip() for x in terms_df["term"].dropna().tolist() if str(x).strip()]
    if not terms:
        raise RuntimeError("분석할 유행어가 data/metrics.csv에 없습니다.")

    all_comments = []
    successful_videos = 0
    for video_id in video_ids:
        try:
            comments = fetch_comment_threads(video_id, max_pages=1, max_results=100)
            all_comments.extend(comments)
            successful_videos += 1
            print(f"{video_id}: collected {len(comments)} top-level comments")
        except Exception as exc:
            print(f"WARNING: video {video_id} failed: {exc}")
    if not all_comments:
        raise RuntimeError("댓글을 하나도 수집하지 못했습니다. 영상 댓글 공개 여부, API 키, API 할당량을 확인하세요.")

    texts = [str(c.get("text", "")) for c in all_comments]
    total = len(texts)
    today = datetime.now(timezone.utc).date().isoformat()
    collected_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows = []
    for term in terms:
        mentions = sum(1 for text in texts if term.casefold() in text.casefold())
        rows.append({
            "date": today,
            "term": term,
            "mentions": mentions,
            "total_comments": total,
            "comment_rate": round(mentions / total * 100, 4) if total else 0.0,
            "videos_requested": len(video_ids),
            "videos_collected": successful_videos,
            "collected_at_utc": collected_at,
        })
    current = pd.DataFrame(rows)
    if HISTORY_FILE.exists():
        history = pd.read_csv(HISTORY_FILE)
    else:
        history = pd.DataFrame(columns=current.columns.tolist() + ["comment_growth"])
    # Growth is the percentage-point change versus the latest previous collection for each term.
    growth_values = []
    for _, row in current.iterrows():
        previous = history[(history["term"] == row["term"]) & (history["date"] < today)] if not history.empty and {"term", "date", "comment_rate"}.issubset(history.columns) else pd.DataFrame()
        if not previous.empty:
            previous = previous.sort_values("date")
            growth_values.append(round(float(row["comment_rate"]) - float(previous.iloc[-1]["comment_rate"]), 4))
        else:
            growth_values.append(0.0)
    current["comment_growth"] = growth_values

    # Keep only one snapshot per term/date so reruns do not duplicate today's rows.
    combined = pd.concat([history, current], ignore_index=True, sort=False) if not history.empty else current.copy()
    if {"date", "term"}.issubset(combined.columns):
        combined = combined.drop_duplicates(subset=["date", "term"], keep="last")
    combined.to_csv(HISTORY_FILE, index=False, encoding="utf-8-sig")
    current.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    print(f"SUCCESS: {total} public top-level comments from {successful_videos}/{len(video_ids)} videos; wrote {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
