import os
import re
import requests

YOUTUBE_API_URL = (
    "https://www.googleapis.com/youtube/v3/commentThreads"
)


def extract_video_id(video_url_or_id):
    """YouTube URL 또는 영상 ID에서 영상 ID를 추출한다."""
    value = video_url_or_id.strip()

    patterns = [
        r"[?&]v=([A-Za-z0-9_-]{11})",
        r"youtu\.be/([A-Za-z0-9_-]{11})",
        r"youtube\.com/embed/([A-Za-z0-9_-]{11})",
        r"youtube\.com/shorts/([A-Za-z0-9_-]{11})",
    ]

    for pattern in patterns:
        match = re.search(pattern, value)
        if match:
            return match.group(1)

    if re.fullmatch(r"[A-Za-z0-9_-]{11}", value):
        return value

    raise ValueError(f"올바른 YouTube 영상 URL 또는 ID가 아닙니다: {value}")


def fetch_comment_threads(video_id, max_results=100):
    """영상의 공개 최상위 댓글을 수집한다."""
    api_key = os.getenv("YOUTUBE_API_KEY")

    if not api_key:
        raise RuntimeError(
            "YOUTUBE_API_KEY가 설정되지 않았습니다. "
            "GitHub Actions Secrets 설정을 확인하세요."
        )

    video_id = extract_video_id(video_id)
    comments = []
    page_token = None
    limit = min(max(int(max_results), 1), 100)

    while len(comments) < limit:
        params = {
            "part": "snippet",
            "videoId": video_id,
            "maxResults": min(100, limit - len(comments)),
            "textFormat": "plainText",
            "key": api_key,
        }

        if page_token:
            params["pageToken"] = page_token

        response = requests.get(
            YOUTUBE_API_URL,
            params=params,
            timeout=30,
        )

        if not response.ok:
            try:
                error_data = response.json().get("error", {})
                error_message = error_data.get(
                    "message", "상세 오류 메시지 없음"
                )
                error_reason = ", ".join(
                    item.get("reason", "")
                    for item in error_data.get("errors", [])
                    if item.get("reason")
                )
            except (ValueError, AttributeError):
                error_message = "API 응답을 해석할 수 없습니다."
                error_reason = ""

            # API 키는 오류 메시지에 포함하지 않는다.
            detail = (
                f"YouTube API 오류: HTTP {response.status_code}; "
                f"영상 ID={video_id}; "
                f"메시지={error_message}"
            )

            if error_reason:
                detail += f"; 사유={error_reason}"

            raise RuntimeError(detail)

        try:
            data = response.json()
        except ValueError as exc:
            raise RuntimeError(
                "YouTube API 응답이 JSON 형식이 아닙니다."
            ) from exc

        for item in data.get("items", []):
            snippet = (
                item.get("snippet", {})
                .get("topLevelComment", {})
                .get("snippet", {})
            )

            text = snippet.get("textDisplay", "").strip()

            if text:
                comments.append(text)

        page_token = data.get("nextPageToken")

        if not page_token or not data.get("items"):
            break

    return comments[:limit]


def fetch_comments(video_url_or_id, max_results=100):
    """기존 호출 방식과의 호환성을 위한 함수."""
    return fetch_comment_threads(
        video_url_or_id,
        max_results=max_results,
    )
