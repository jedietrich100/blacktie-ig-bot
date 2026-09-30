"""Isolated Circus preview/render/Buffer submission. No imports from BTI or DCD."""
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
API = 'https://api.buffer.com'


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


def gql(key, query):
    # One attempt for mutations. Unknown outcome must never trigger a blind retry.
    response = requests.post(API, headers={'Authorization': f'Bearer {key}'},
                             json={'query': query}, timeout=45)
    if response.status_code != 200:
        raise RuntimeError(f'Buffer HTTP {response.status_code}; inspect Buffer before retry')
    payload = response.json()
    if payload.get('errors') or not payload.get('data'):
        raise RuntimeError('Buffer GraphQL error; inspect Buffer before retry')
    return payload['data']


def validate_channel(key, channel_id, organization_id, expected_name):
    query = ('query { channels(input: { organizationId: ' + json.dumps(organization_id)
             + ' }) { id name service } }')
    channels = gql(key, query)['channels']
    matches = [c for c in channels if str(c['id']) == channel_id]
    if len(matches) != 1:
        raise RuntimeError('Configured Circus channel not uniquely accessible')
    c = matches[0]
    if str(c['service']).lower() != 'instagram' or c['name'] != expected_name:
        raise RuntimeError('Circus channel identity mismatch; refusing submission')


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
        print('Preview only: no repository write and no Buffer mutation.')
        return

    key = need('CIRCUS_BUFFER_API_KEY')
    channel = need('CIRCUS_BUFFER_CHANNEL_ID')
    organization = need('CIRCUS_BUFFER_ORGANIZATION_ID')
    expected = need('CIRCUS_EXPECTED_CHANNEL_NAME')
    repository = need('CIRCUS_REPOSITORY')
    if repository != 'jedietrich100/blacktie-ig-bot':
        raise RuntimeError('Unexpected repository; refusing submission')
    validate_channel(key, channel, organization, expected)

    state = json.loads(STATE.read_text()) if STATE.exists() else None
    if state and state['channel_id'] != channel:
        raise RuntimeError('Stored Circus channel differs from configured channel')
    if state and state['phase'] == 'accepted':
        print('Already accepted by Buffer today; skipping.')
        return
    if state and state['phase'] != 'prepared':
        raise RuntimeError('Uncertain prior submission: reconcile in Buffer before retry')

    if not state:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / 'post.jpg').write_bytes(image)
        (OUT / 'caption.txt').write_text(caption)
        state = {'date': DAY, 'channel_id': channel, 'phase': 'prepared'}
        write_state(state)
        persist(f'Circus prepared: {DAY}')
    # Reuse prepared content on retry, even if generation code has changed.
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
            if hashlib.sha256(r.content).digest() != hashlib.sha256((OUT / 'post.jpg').read_bytes()).digest():
                raise RuntimeError('Public asset differs from prepared image')
            break
        except (requests.RequestException, OSError):
            if attempt == 11:
                raise RuntimeError('Public Circus JPEG unavailable') from None
            time.sleep(5)

    # Persist intent BEFORE the non-idempotent API call. A crash/timeout now
    # deliberately blocks reruns instead of risking a duplicate Instagram post.
    state.update(phase='submitting', image_url=url)
    write_state(state)
    persist(f'Circus submitting: {DAY}')
    query = '''mutation { createPost(input: {
      text: CAPTION, channelId: CHANNEL,
      schedulingType: automatic, mode: shareNow,
      assets: [{ image: { url: IMAGE } }],
      metadata: { instagram: { type: post, shouldShareToFeed: true } }
    }) {
      ... on PostActionSuccess { post { id status } }
      ... on MutationError { message }
    } }'''.replace('CAPTION', json.dumps(caption)).replace('CHANNEL', json.dumps(channel)).replace('IMAGE', json.dumps(url))
    result = gql(key, query).get('createPost') or {}
    post = result.get('post') or {}
    if not post.get('id'):
        raise RuntimeError('Buffer did not confirm acceptance; reconcile before retry')
    state.update(phase='accepted', buffer_post_id=post['id'], buffer_status=post.get('status'))
    write_state(state)
    persist(f'Circus accepted by Buffer: {DAY}')
    print(f'Buffer accepted post {post["id"]}; Instagram delivery must be verified separately.')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        # Suppress raw requests exceptions that can expose credentials in diagnostics.
        print('::error::Circus failed. Check configuration, repository state and Buffer; do not blindly resubmit.')
        raise SystemExit(1)
