import os
import re
import requests

YOUTUBE_API_URL = "https://www.googleapis.com/youtube/v3/commentThreads"


def extract_video_id(video_url_or_id):
    """Extract an 11-character YouTube video ID from a URL or raw ID."""
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
    raise ValueError("올바른 YouTube 영상 URL 또는 ID가 아닙니다.")


def fetch_comment_threads(video_id, max_pages=1, max_results=None):
    """
    Fetch public top-level YouTube comments.
    Returns dictionaries compatible with daily_collect.py:
    comment_id, video_id, published_at, text.
    max_pages controls how many pages (up to 100 comments each) are requested.
    """
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "YOUTUBE_API_KEY가 설정되지 않았습니다. "
            "GitHub Actions Secrets를 확인하세요."
        )

    video_id = extract_video_id(video_id)
    try:
        page_limit = max(1, min(int(max_pages), 10))
    except (TypeError, ValueError):
        page_limit = 1

    if max_results is not None:
        try:
            result_limit = max(1, min(int(max_results), 1000))
            page_limit = min(page_limit, (result_limit + 99) // 100)
        except (TypeError, ValueError):
            result_limit = page_limit * 100
    else:
        result_limit = page_limit * 100

    comments = []
    page_token = None

    for _ in range(page_limit):
        params = {
            "part": "snippet",
            "videoId": video_id,
            "maxResults": min(100, result_limit - len(comments)),
            "textFormat": "plainText",
            "order": "time",
            "key": api_key,
        }
        if params["maxResults"] <= 0:
            break
        if page_token:
            params["pageToken"] = page_token

        response = requests.get(YOUTUBE_API_URL, params=params, timeout=30)

        if not response.ok:
            try:
                error_data = response.json().get("error", {})
                message = error_data.get("message", "상세 오류 메시지가 없습니다.")
                reasons = [
                    item.get("reason", "")
                    for item in error_data.get("errors", [])
                    if item.get("reason")
                ]
            except (ValueError, AttributeError):
                message = "API 응답을 해석할 수 없습니다."
                reasons = []

            detail = (
                f"YouTube API 오류 HTTP {response.status_code}; "
                f"영상 ID {video_id}; {message}"
            )
            if reasons:
                detail += "; reason=" + ", ".join(reasons)
            # Do not include the request URL, because it contains the API key.
            raise RuntimeError(detail)

        try:
            data = response.json()
        except ValueError as exc:
            raise RuntimeError("YouTube API 응답이 JSON 형식이 아닙니다.") from exc

        for item in data.get("items", []):
            comment = item.get("snippet", {}).get("topLevelComment", {})
            snippet = comment.get("snippet", {})
            text = snippet.get("textDisplay", "").strip()
            if text:
                comments.append({
                    "comment_id": comment.get("id", item.get("id")),
                    "video_id": video_id,
                    "published_at": snippet.get("publishedAt"),
                    "text": text,
                })
                if len(comments) >= result_limit:
                    break

        if len(comments) >= result_limit:
            break
        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return comments


def fetch_comments(video_url_or_id, max_results=100, max_pages=None):
    """Compatibility alias for callers using fetch_comments."""
    if max_pages is None:
        max_pages = max(1, (int(max_results) + 99) // 100)
    return fetch_comment_threads(
