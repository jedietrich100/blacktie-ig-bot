"""Isolated Circus preview/render/direct Instagram submission. No imports from BTI or DCD."""
import datetime as dt
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import textwrap
import time
from zoneinfo import ZoneInfo

import requests
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
DAY = dt.datetime.now(ZoneInfo('America/Chicago')).date().isoformat()
OUT = Path('docs/circus-posts') / DAY
STATE = Path('circus/state') / f'{DAY}.json'
PREVIEW = Path('circus/preview')
API = 'https://graph.instagram.com/v24.0'


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


def ig_post(path, token, data):
    response = requests.post(f'{API}/{path}', data={**data, 'access_token': token}, timeout=45)
    if response.status_code != 200:
        raise RuntimeError(f'Instagram HTTP {response.status_code}')
    payload = response.json()
    if not payload.get('id'):
        raise RuntimeError('Instagram did not confirm the request')
    return str(payload['id'])


def render():
    # Proposed small-joys content defaults, not a claim of approved brand direction.
    joys = ['a warm cup of coffee', 'a sky full of sunset colors', 'an unexpected smile',
            'a favorite song', 'a quiet morning', 'a walk with no agenda',
            'a good laugh', 'a fresh start', 'a kind word', 'a little breathing room']
    endings = ['No big occasion required.', 'Leave a little room for joy.',
               'The ordinary can be pretty wonderful.', 'Small things count.',
               'Take the good moment when it comes.', 'A little lighter is enough.',
               'Enjoy it before rushing to the next thing.']
    number = int(hashlib.sha256(DAY.encode()).hexdigest(), 16)
    headline = f"Today's little joy: {joys[number % len(joys)]}."
    detail = endings[(number // len(joys)) % len(endings)]
    caption = f'{headline}\n\n{detail}\n\n#CircusPeanutsDaily #LittleJoys'
    image = Image.new('RGB', (1080, 1350), '#fff1dc')
    draw = ImageDraw.Draw(image)
    font_file = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    big = ImageFont.truetype(font_file, 64)
    small = ImageFont.truetype(font_file, 30)
    draw.text((80, 120), 'CIRCUS PEANUTS DAILY', fill='#b24d32', font=small)
    draw.multiline_text((80, 400), '\n'.join(textwrap.wrap(headline, 22)),
                        fill='#432e28', font=big, spacing=24)
    draw.multiline_text((80, 1000), '\n'.join(textwrap.wrap(detail, 44)),
                        fill='#432e28', font=small, spacing=14)
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

    state = json.loads(STATE.read_text()) if STATE.exists() else None
    if state and state.get('ig_user_id') != user_id:
        raise RuntimeError('Stored Circus Instagram user differs from configured user')
    if state and state.get('phase') == 'published':
        print('Already published today; skipping.')
        return
    if state and state.get('phase') != 'prepared':
        raise RuntimeError('Uncertain prior submission: verify Instagram before retry')

    if not state:
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

    status = None
    for _ in range(12):
        check = requests.get(f'{API}/{creation_id}',
            params={'fields': 'status_code', 'access_token': token}, timeout=30)
        if check.status_code == 200:
            status = check.json().get('status_code')
            if status == 'FINISHED':
                break
            if status in ('ERROR', 'EXPIRED'):
                raise RuntimeError(f'Instagram container status {status}')
        time.sleep(5)
    if status != 'FINISHED':
        raise RuntimeError('Instagram container not ready; verify before retry')

    media_id = ig_post(f'{user_id}/media_publish', token, {'creation_id': creation_id})
    state.update(phase='published', creation_id=creation_id, instagram_media_id=media_id)
    write_state(state)
    persist(f'Circus published: {DAY}')
    print(f'Instagram published Circus media {media_id}.')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        # Suppress raw requests exceptions that can expose credentials in diagnostics.
        print('::error::Circus failed safely. Check configuration and Instagram state; do not blindly resubmit.')
        raise SystemExit(1)
