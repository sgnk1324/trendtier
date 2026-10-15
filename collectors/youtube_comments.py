"""
Minimal official YouTube Data API collector.
This module intentionally collects only public comments through the official API.
Set YOUTUBE_API_KEY in the environment before use.
"""
import os
import requests

API_URL = "https://www.googleapis.com/youtube/v3/commentThreads"

def fetch_comment_threads(video_id: str, max_pages: int = 1, max_results: int = 100):
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        raise RuntimeError("YOUTUBE_API_KEY가 설정되지 않았습니다.")
    results = []
    page_token = None
    for _ in range(max_pages):
        params = {
            "part": "snippet",
            "videoId": video_id,
            "maxResults": min(max(1, max_results), 100),
            "textFormat": "plainText",
            "order": "time",
            "key": api_key,
        }
        if page_token:
            params["pageToken"] = page_token
        response = requests.get(API_URL, params=params, timeout=30)
    if not response.ok:
        try:
            error_detail = response.json()
        except ValueError:
            error_detail = response.text
        raise RuntimeError(
            f"YouTube API 오류 (HTTP {response.status_code}): {error_detail}"
    )
        
    data = response.json()
        for item in data.get("items", []):
            snippet = item.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
            results.append({
                "comment_id": item.get("id"),
                "video_id": video_id,
                "published_at": snippet.get("publishedAt"),
                "text": snippet.get("textDisplay", ""),
            })
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return results

if __name__ == "__main__":
    import argparse, json
    parser = argparse.ArgumentParser()
    parser.add_argument("--video-id", required=True)
    parser.add_argument("--pages", type=int, default=1)
    args = parser.parse_args()
    print(json.dumps(fetch_comment_threads(args.video_id, args.pages), ensure_ascii=False, indent=2))

