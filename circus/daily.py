"""Isolated Circus preview/render/direct Instagram submission. No imports from BTI or DCD."""
import datetime as dt
import io
import json
import os
from pathlib import Path
import subprocess
import re
import time
from zoneinfo import ZoneInfo

import requests
from PIL import Image, ImageDraw, ImageFont

from content import for_day

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
DAY = dt.datetime.now(ZoneInfo('America/Chicago')).date().isoformat()
OUT = Path('docs/circus-posts') / DAY
STATE = Path('circus/state') / f'{DAY}.json'
PREVIEW = Path('circus/preview')
API = 'https://graph.instagram.com/v26.0'
EXPECTED_USERNAME = 'circuspeanutsdaily'


def need(key):
    value = os.environ.get(key, '').strip()
    if not value:
        raise RuntimeError(f'Missing {key}')
    return value


def git(*args):
    # Never print command output: remote URLs and errors may contain credentials.
    result = subprocess.run(['git', *args], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f'Git operation failed: {args[0]}')
    return result.stdout.strip()


def persist(message):
    git('config', 'user.name', 'circus-peanuts-bot')
    git('config', 'user.email', 'actions@users.noreply.github.com')
    # Explicit paths only; never stage other brands or preview files.
    git('add', '--', str(OUT), str(STATE))
    if not git('diff', '--cached', '--name-only'):
        return
    git('commit', '-m', message)
    for attempt in range(3):
        git('pull', '--rebase', 'origin', 'main')
        try:
            git('push', 'origin', 'HEAD:main')
            return
        except RuntimeError:
            if attempt == 2:
                raise
            time.sleep(5)


def ig_request(method, path, token, data=None):
    # Bearer header keeps credentials out of URLs and sanitized diagnostics.
    response = requests.request(method, f'{API}/{path}',
        headers={'Authorization': f'Bearer {token}'},
        params=data if method == 'GET' else None,
        data=data if method == 'POST' else None, timeout=45,
        allow_redirects=False)
    if response.status_code != 200:
        raise RuntimeError(f'Instagram HTTP {response.status_code}')
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError('Unexpected Instagram response')
    return payload


def ig_post(path, token, data):
    payload = ig_request('POST', path, token, data)
    result = str(payload.get('id', ''))
    if not result.isdigit():
        raise RuntimeError('Instagram did not confirm the request')
    return result


def verify_account(token, user_id):
    if not user_id.isdigit():
        raise RuntimeError('Invalid configured Circus account ID')
    account = ig_request('GET', 'me', token, {'fields': 'user_id,username,id'})
    account_id = str(account.get('user_id') or account.get('id') or '')
    if account.get('username') != EXPECTED_USERNAME or account_id != user_id:
        raise RuntimeError('Credentials do not match @circuspeanutsdaily')
    print('Verified account: @circuspeanutsdaily')


def today_media(token, user_id):
    payload = ig_request('GET', f'{user_id}/media', token,
        {'fields': 'id,timestamp,permalink,caption', 'limit': 100})
    rows = payload.get('data')
    if not isinstance(rows, list):
        raise RuntimeError('Unreadable recent Instagram media')
    today = []
    for row in rows:
        stamp = dt.datetime.fromisoformat(row['timestamp'].replace('Z', '+00:00'))
        if stamp.tzinfo is None:
            raise RuntimeError('Invalid recent-media timestamp')
        if stamp.astimezone(ZoneInfo('America/Chicago')).date().isoformat() == DAY:
            today.append(row)
    return today


def verified_permalink(media_id, token):
    if not str(media_id).isdigit():
        raise RuntimeError('Invalid published media ID')
    payload = ig_request('GET', str(media_id), token,
        {'fields': 'id,permalink,username'})
    permalink = payload.get('permalink', '')
    if str(payload.get('id')) != str(media_id) or payload.get('username') != EXPECTED_USERNAME:
        raise RuntimeError('Published media identity could not be verified')
    if not re.fullmatch(r'https://www[.]instagram[.]com/(?:p|reel|tv)/[A-Za-z0-9_-]+/?', permalink):
        raise RuntimeError('Published media permalink could not be verified')
    print(f'VERIFIED_PERMALINK: {permalink}')
    return permalink


def wrapped(draw, text, font, width):
    lines, line = [], ''
    for word in text.split():
        candidate = f'{line} {word}'.strip()
        if line and draw.textlength(candidate, font=font) > width:
            lines.append(line)
            line = word
        else:
            line = candidate
    lines.append(line)
    return '\n'.join(lines)


def render():
    setup, punchline, caption = for_day(DAY)
    image = Image.new('RGB', (1080, 1350), '#fff1dc')
    draw = ImageDraw.Draw(image)
    regular = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    bold = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
    small = ImageFont.truetype(bold, 27)
    draw.rounded_rectangle((70, 65, 1010, 1285), radius=45, outline='#e4b99a', width=3)
    draw.text((108, 130), 'CIRCUS PEANUTS DAILY', fill='#b24d32', font=small)
    draw.line((108, 202, 972, 202), fill='#e4b99a', width=3)
    for size in range(62, 39, -2):
        big = ImageFont.truetype(bold, size)
        medium = ImageFont.truetype(regular, size - 4)
        setup_text = wrapped(draw, setup, big, 850)
        punch_text = wrapped(draw, punchline, medium, 850)
        sh = draw.multiline_textbbox((0, 0), setup_text, font=big, spacing=16)[3]
        ph = draw.multiline_textbbox((0, 0), punch_text, font=medium, spacing=16)[3]
        if sh + ph + 75 <= 680:
            break
    if sh + ph + 75 > 680:
        raise RuntimeError('Joke does not fit the card')
    y = 330 + (680 - sh - ph - 75) // 2
    draw.multiline_text((108, y), setup_text, fill='#432e28', font=big, spacing=16)
    draw.multiline_text((108, y + sh + 75), punch_text, fill='#b24d32', font=medium, spacing=16)
    draw.line((108, 1125, 972, 1125), fill='#e4b99a', width=3)
    draw.text((108, 1175), 'YOUR DAILY HANDFUL OF FUNNY.', fill='#b24d32', font=small)
    data = io.BytesIO()
    image.save(data, format='JPEG', quality=92)
    return data.getvalue(), caption


def write_state(state):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2) + '\n')


def main():
    image, caption = render()
    PREVIEW.mkdir(parents=True, exist_ok=True)
    (PREVIEW / 'post.jpg').write_bytes(image)
    (PREVIEW / 'caption.txt').write_text(caption)
    if os.environ.get('CIRCUS_PUBLISH') != 'true':
        print('Preview only: no repository write and no Instagram mutation.')
        return

    token = need('CIRCUS_IG_ACCESS_TOKEN')
    user_id = need('CIRCUS_IG_USER_ID')
    repository = need('CIRCUS_REPOSITORY')
    if repository != 'jedietrich100/blacktie-ig-bot':
        raise RuntimeError('Unexpected repository; refusing submission')

    verify_account(token, user_id)
    state = json.loads(STATE.read_text()) if STATE.exists() else None
    if STATE.exists() and (not isinstance(state, dict) or
            state.get('date') != DAY or state.get('ig_user_id') != user_id or
            state.get('phase') not in ('prepared', 'submitting', 'container_created', 'publishing', 'published')):
        raise RuntimeError('Invalid existing Circus state; refusing submission')
    if state is not None and state.get('phase') == 'published':
        verified_permalink(state.get('instagram_media_id'), token)
        print('Already published today; skipping.')
        return
    existing = today_media(token, user_id)
    if existing:
        for item in existing:
            print(f'ALREADY_LIVE_MEDIA_ID: {item.get("id")}')
            verified_permalink(item.get('id'), token)
        print('Circus already has a post today; no new submission.')
        return
    if state is not None and state.get('phase') != 'prepared':
        raise RuntimeError('Uncertain prior submission: verify Instagram before retry')

    if state is None:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / 'post.jpg').write_bytes(image)
        (OUT / 'caption.txt').write_text(caption)
        state = {'date': DAY, 'ig_user_id': user_id, 'phase': 'prepared'}
        write_state(state)
        persist(f'Circus prepared: {DAY}')

    caption = (OUT / 'caption.txt').read_text()
    url = f'https://raw.githubusercontent.com/{repository}/{git("rev-parse", "HEAD")}/{OUT}/post.jpg'
    for attempt in range(12):
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            public = Image.open(io.BytesIO(r.content))
            public.verify()
            if public.format != 'JPEG':
                raise RuntimeError('Public asset is not JPEG')
            break
        except (requests.RequestException, OSError):
            if attempt == 11:
                raise RuntimeError('Public Circus JPEG unavailable') from None
            time.sleep(5)

    state.update(phase='submitting', image_url=url)
    write_state(state)
    persist(f'Circus submitting: {DAY}')
    creation_id = ig_post(f'{user_id}/media', token, {'image_url': url, 'caption': caption})
    state.update(phase='container_created', creation_id=creation_id)
    write_state(state)
    persist(f'Circus container created: {DAY}')

    status = None
    for _ in range(12):
        check = ig_request('GET', creation_id, token, {'fields': 'status_code'})
        status = check.get('status_code')
        if status == 'FINISHED':
            break
        if status in ('ERROR', 'EXPIRED'):
            raise RuntimeError(f'Instagram container status {status}')
        time.sleep(5)
    if status != 'FINISHED':
        raise RuntimeError('Instagram container not ready; verify before retry')

    state.update(phase='publishing')
    write_state(state)
    persist(f'Circus publishing: {DAY}')
    # Never retry this POST automatically after an uncertain response.
    media_id = ig_post(f'{user_id}/media_publish', token, {'creation_id': creation_id})
    print(f'PUBLISHED_MEDIA_ID: {media_id}')
    state.update(phase='published', creation_id=creation_id, instagram_media_id=media_id)
    write_state(state)
    persist(f'Circus published: {DAY}')
    permalink = verified_permalink(media_id, token)
    state.update(permalink=permalink)
    write_state(state)
    persist(f'Circus publication verified: {DAY}')
    print(f'Instagram published Circus media {media_id}.')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        # Suppress raw requests exceptions that can expose credentials in diagnostics.
        print('::error::Circus failed safely. Check configuration and Instagram state; do not blindly resubmit.')
        raise SystemExit(1)

