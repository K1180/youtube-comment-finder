from flask import Flask, render_template, request, jsonify
from googleapiclient.discovery import build
from datetime import datetime, timezone
import re

app = Flask(__name__)

def extract_channel_id(api_key, url_or_id):
    """チャンネルURL or IDからチャンネルIDを取得"""
    youtube = build('youtube', 'v3', developerKey=api_key)

    # @handle 形式
    handle_match = re.search(r'@([\w\-\.]+)', url_or_id)
    # /channel/UC... 形式
    channel_id_match = re.search(r'channel/(UC[\w\-]+)', url_or_id)
    # /c/ 形式 or /user/ 形式
    custom_match = re.search(r'(?:/c/|/user/)([\w\-\.]+)', url_or_id)
    # 直接UC...で始まる場合
    direct_id_match = re.match(r'^UC[\w\-]{22}$', url_or_id.strip())

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
        # fallback: search
        res = youtube.search().list(part='snippet', q=username, type='channel', maxResults=1).execute()
        items = res.get('items', [])
        if items:
            return items[0]['snippet']['channelId']
    return None


def get_live_videos_from_channel(youtube, channel_id, published_after=None, published_before=None, max_videos=50):
    """チャンネルの過去ライブ配信のみ取得（eventType='completed'）"""
    videos = []
    next_page_token = None

    params = dict(
        part='snippet',
        channelId=channel_id,
        type='video',
        eventType='completed',   # 終了済みライブ配信のみ
        maxResults=50,
        order='date'
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
                'video_id': item['id']['videoId'],
                'title': item['snippet']['title'],
                'published_at': item['snippet']['publishedAt'],
                'thumbnail': item['snippet']['thumbnails']['medium']['url'],
                'channel_title': item['snippet']['channelTitle'],
            })
        next_page_token = res.get('nextPageToken')
        if not next_page_token or len(videos) >= max_videos:
            break

    return videos[:max_videos]


def search_comments_in_video(youtube, video_id, keyword):
    """動画の最初のページ（最大20件）のコメントからキーワードを検索。
    1リクエスト = 1ユニット消費に抑えるため、ページネーションなし・maxResults=20固定。
    """
    matched_comments = []

    try:
        res = youtube.commentThreads().list(
            part='snippet',
            videoId=video_id,
            maxResults=100,       # 1ページのみ取得（1ユニット）
            order='relevance',   # 関連度順で主要コメントを優先
            textFormat='plainText'
        ).execute()

        for item in res.get('items', []):
            top = item['snippet']['topLevelComment']['snippet']
            text = top['textDisplay']
            if keyword.lower() in text.lower():
                matched_comments.append({
                    'author': top['authorDisplayName'],
                    'text': text,
                    'like_count': top['likeCount'],
                    'published_at': top['publishedAt'],
                })

    except Exception:
        # コメント無効・非公開など
        pass

    return matched_comments


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/search', methods=['POST'])
def search():
    data = request.json
    api_key = data.get('api_key', '').strip()
    channel_input = data.get('channel_url', '').strip()
    keyword = data.get('keyword', '').strip()
    date_from = data.get('date_from', '').strip()
    date_to = data.get('date_to', '').strip()
    max_videos = int(data.get('max_videos', 20))

    if not api_key or not channel_input or not keyword:
        return jsonify({'error': 'APIキー、チャンネルURL、キーワードは必須です'}), 400

    try:
        youtube = build('youtube', 'v3', developerKey=api_key)

        # チャンネルID取得
        channel_id = extract_channel_id(api_key, channel_input)
        if not channel_id:
            return jsonify({'error': 'チャンネルが見つかりませんでした。URLを確認してください。'}), 404

        # 日付をRFC3339に変換
        published_after = None
        published_before = None
        if date_from:
            published_after = datetime.strptime(date_from, '%Y-%m-%d').replace(tzinfo=timezone.utc).isoformat()
        if date_to:
            dt = datetime.strptime(date_to, '%Y-%m-%d').replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
            published_before = dt.isoformat()

        # ライブ配信（終了済み）のみ取得
        videos = get_live_videos_from_channel(youtube, channel_id, published_after, published_before, max_videos)

        matched = []
        not_matched = []

        for v in videos:
            comments = search_comments_in_video(youtube, v['video_id'], keyword)
            if comments:
                v['matched_comments'] = comments
                v['match_count'] = len(comments)
                matched.append(v)
            else:
                not_matched.append(v)

        return jsonify({
            'matched': matched,
            'not_matched': not_matched,
            'total_videos': len(videos),
            'keyword': keyword,
        })

    except Exception as e:
        return jsonify({'error': f'エラーが発生しました: {str(e)}'}), 500


if __name__ == '__main__':
    app.run(debug=True)
