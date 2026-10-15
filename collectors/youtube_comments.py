"""Collect public top-level YouTube comments using the official YouTube Data API v3."""
from __future__ import annotations

import os
import re
from typing import Any

import requests

API_URL = "https://www.googleapis.com/youtube/v3/commentThreads"


def extract_video_id(video_url_or_id: str) -> str:
    """Accept an 11-character video ID or a standard YouTube URL."""
    value = str(video_url_or_id).strip()
    patterns = (
        r"[?&]v=([A-Za-z0-9_-]{11})",
        r"youtu\.be/([A-Za-z0-9_-]{11})",
        r"youtube\.com/embed/([A-Za-z0-9_-]{11})",
        r"youtube\.com/shorts/([A-Za-z0-9_-]{11})",
    )
    for pattern in patterns:
        match = re.search(pattern, value)
        if match:
            return match.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", value):
        return value
    raise ValueError("올바른 YouTube 영상 URL 또는 11자리 영상 ID가 아닙니다.")


def fetch_comment_threads(
    video_id: str,
    max_pages: int = 1,
    max_results: int = 100,
) -> list[dict[str, Any]]:
    """Fetch public top-level comments; max_results is the number per page (1–100)."""
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        raise RuntimeError("YOUTUBE_API_KEY가 설정되지 않았습니다. GitHub Actions Secrets를 확인하세요.")

    video_id = extract_video_id(video_id)
    pages = max(1, int(max_pages))
    per_page = min(100, max(1, int(max_results)))
    results: list[dict[str, Any]] = []
    page_token = None

    for _ in range(pages):
        params = {
            "part": "snippet",
            "videoId": video_id,
            "maxResults": per_page,
            "textFormat": "plainText",
            "order": "time",
            "key": api_key,
        }
        if page_token:
            params["pageToken"] = page_token

        try:
            response = requests.get(API_URL, params=params, timeout=30)
        except requests.RequestException as exc:
            raise RuntimeError(f"YouTube API 요청에 실패했습니다: {type(exc).__name__}") from exc

        if not response.ok:
            try:
                payload = response.json()
                error = payload.get("error", {}) if isinstance(payload, dict) else {}
                message = error.get("message", "상세 오류 메시지 없음")
                reasons = [
                    item.get("reason", "")
                    for item in error.get("errors", [])
                    if isinstance(item, dict) and item.get("reason")
                ]
            except (ValueError, AttributeError):
                message = "Google API에서 오류 응답을 반환했습니다."
                reasons = []

            # Never include the request URL: it contains the API key as a query parameter.
            detail = f"YouTube API 오류 HTTP {response.status_code} (영상 ID {video_id}): {message}"
            if reasons:
                detail += "; reason=" + ", ".join(reasons)
            raise RuntimeError(detail)

        try:
            data = response.json()
        except ValueError as exc:
            raise RuntimeError("YouTube API 응답을 JSON으로 읽을 수 없습니다.") from exc

        for item in data.get("items", []):
            comment = item.get("snippet", {}).get("topLevelComment", {})
            snippet = comment.get("snippet", {})
            results.append(
                {
                    "comment_id": comment.get("id", item.get("id")),
                    "video_id": video_id,
                    "published_at": snippet.get("publishedAt"),
