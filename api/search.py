from http.server import BaseHTTPRequestHandler
from googleapiclient.discovery import build
from datetime import datetime, timezone
import json
import re
import os


def extract_channel_id(api_key, url_or_id):
    youtube = build('youtube', 'v3', developerKey=api_key)
    handle_match     = re.search(r'@([\w\-\.]+)', url_or_id)
    channel_id_match = re.search(r'channel/(UC[\w\-]+)', url_or_id)
    custom_match     = re.search(r'(?:/c/|/user/)([\w\-\.]+)', url_or_id)
    direct_id_match  = re.match(r'^UC[\w\-]{22}$', url_or_id.strip())

    if direct_id_match:
        return url_or_id.strip()
    elif channel_id_match:
        return channel_id_match.group(1)
    elif handle_match:
        handle = handle_match.group(1)
        res = youtube.search().list(part='snippet', q=f'@{handle}', type='channel', maxResults=1).execute()
        items = res.get('items', [])
        if items:
            return items[0]['snippet']['channelId']
    elif custom_match:
        username = custom_match.group(1)
        res = youtube.channels().list(part='id', forUsername=username).execute()
        items = res.get('items', [])
        if items:
            return items[0]['id']
        res = youtube.search().list(part='snippet', q=username, type='channel', maxResults=1).execute()
        items = res.get('items', [])
        if items:
            return items[0]['snippet']['channelId']
    return None


def get_live_videos_from_channel(youtube, channel_id, published_after=None, published_before=None, max_videos=50):
    videos = []
    next_page_token = None
    params = dict(
        part='snippet', channelId=channel_id, type='video',
        eventType='completed', maxResults=50, order='date'
    )
    if published_after:
        params['publishedAfter'] = published_after
    if published_before:
        params['publishedBefore'] = published_before

    while len(videos) < max_videos:
        if next_page_token:
            params['pageToken'] = next_page_token
        res = youtube.search().list(**params).execute()
        for item in res.get('items', []):
            videos.append({
                'video_id':      item['id']['videoId'],
                'title':         item['snippet']['title'],
                'published_at':  item['snippet']['publishedAt'],
                'thumbnail':     item['snippet']['thumbnails']['medium']['url'],
                'channel_title': item['snippet']['channelTitle'],
            })
        next_page_token = res.get('nextPageToken')
        if not next_page_token or len(videos) >= max_videos:
            break
    return videos[:max_videos]


def search_comments_in_video(youtube, video_id, keyword):
    matched_comments = []
    try:
        res = youtube.commentThreads().list(
            part='snippet', videoId=video_id,
            maxResults=100, order='time', textFormat='plainText'
        ).execute()
        for item in res.get('items', []):
            top  = item['snippet']['topLevelComment']['snippet']
            text = top['textDisplay']
            if keyword.lower() in text.lower():
                matched_comments.append({
                    'author':       top['authorDisplayName'],
                    'text':         text,
                })
    except Exception:
        pass
    return matched_comments


class handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors_headers()
        self.end_headers()

    def do_GET(self):
        self._json_response(200, {'status': 'ok'})

    def do_POST(self):
        api_key = os.environ.get('YOUTUBE_API_KEY', '')
        if not api_key:
            self._json_response(500, {'error': 'サーバーにAPIキーが設定されていません。'})
            return

        length = int(self.headers.get('Content-Length', 0))
        body   = self.rfile.read(length)
        try:
            data = json.loads(body)
        except Exception:
            self._json_response(400, {'error': 'リクエストの形式が不正です。'})
            return

        channel_input = (data.get('channel_url') or '').strip()
        keyword       = (data.get('keyword')     or '').strip()
        date_from     = (data.get('date_from')   or '').strip()
        date_to       = (data.get('date_to')     or '').strip()
        max_videos    = int(data.get('max_videos', 20))

        if not channel_input or not keyword:
            self._json_response(400, {'error': 'チャンネルURLとキーワードは必須です。'})
            return

        try:
            youtube    = build('youtube', 'v3', developerKey=api_key)
            channel_id = extract_channel_id(api_key, channel_input)
            if not channel_id:
                self._json_response(404, {'error': 'チャンネルが見つかりませんでした。'})
                return

            published_after  = None
            published_before = None
            if date_from:
                published_after = datetime.strptime(date_from, '%Y-%m-%d').replace(tzinfo=timezone.utc).isoformat()
            if date_to:
                dt = datetime.strptime(date_to, '%Y-%m-%d').replace(
                    hour=23, minute=59, second=59, tzinfo=timezone.utc)
                published_before = dt.isoformat()

            videos      = get_live_videos_from_channel(youtube, channel_id, published_after, published_before, max_videos)
            matched     = []
            not_matched = []

            for v in videos:
                comments = search_comments_in_video(youtube, v['video_id'], keyword)
                if comments:
                    v['matched_comments'] = comments
                    v['match_count']      = len(comments)
                    matched.append(v)
                else:
                    not_matched.append(v)

            self._json_response(200, {
                'matched':      matched,
                'not_matched':  not_matched,
                'total_videos': len(videos),
                'keyword':      keyword,
            })

        except Exception as e:
            self._json_response(500, {'error': f'エラーが発生しました: {str(e)}'})

    def _cors_headers(self):
        self.send_header('Access-Control-Allow-Origin',  '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def _json_response(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self._cors_headers()
        self.send_header('Content-Type',   'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
