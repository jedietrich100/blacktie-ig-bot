"""Independent Circus renderer/publisher. Stops on uncertain publish outcomes."""
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import time
from zoneinfo import ZoneInfo

import requests
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / 'circus/ledger.json'
BASE = 'https://graph.instagram.com/v26.0'
ZONE = ZoneInfo('America/Chicago')
JOKES = [
    'Life’s a circus.\nWe brought the peanuts.',
    'I finally got 8 hours of sleep.\nIt took me three days, but I got it.',
    'Being an adult is mostly wondering why you walked into a room.',
    'My to-do list has started adding things without consulting me.',
    'I put my phone somewhere safe.\nApparently, it’s safe from me too.',
    'I’m not running late.\nI’m giving everyone time to miss me.',
    'My laundry has entered its permanent residency era.',
    'I opened the fridge for inspiration.\nThe cheese understood the assignment.',
    'I made a five-year plan.\nThen I needed a snack.',
    'My coffee and I are taking this one sip at a time.',
    'I came. I saw.\nI forgot what I came for.',
    'The fitted sheet and I have agreed to call it abstract art.',
    'I cleaned one drawer.\nPlease respect my journey.',
    'My calendar thinks we’re a lot more ambitious than we are.',
    'I’m available for adventure.\nDoes it have parking?',
    'I bought a planner.\nNow I can schedule my procrastination.',
    'The best part of making plans is the outfit I imagine wearing.',
    'I have a lot on my plate.\nUnfortunately, none of it is cake.',
    'My house is organized by the very advanced system of “somewhere.”',
    'I’m not ignoring my responsibilities.\nWe’re taking a little space.',
    'I went for a walk to clear my head.\nCame back thinking about tacos.',
    'I’ve reached the age where a good chair can change my plans.',
    'My grocery list said “essentials.”\nThe cookies looked essential.',
    'I love a spontaneous plan with three days’ notice.',
    'I put things off so efficiently, I should teach a class.\nLater.',
    'The weekend has a suspiciously short attention span.',
    'I saved the box just in case.\nThe case has yet to introduce itself.',
    'My plants and I are both doing our best with inconsistent routines.',
    'I came home to relax.\nThe dishes had other proposals.',
    'I don’t need much.\nJust a snack and fewer passwords.',
    'My screen-time report would like a word.\nI muted it.',
    'I rehearsed that conversation perfectly in the shower.',
    'I’m practicing mindfulness.\nMostly being mindful of lunch.',
    'My hobbies include moving things to slightly different piles.',
    'I was going to be productive.\nThen the dog looked comfortable.',
    'My budget and my shopping cart are in separate group chats.',
    'I enjoy a good mystery.\nLike where my other sock went.',
    'I’m in my quiet era.\nExcept when opening a bag of chips.',
    'I have excellent intentions.\nThey just don’t like getting up early.',
    'I checked the weather.\nThen dressed for the weather I preferred.',
    'I’m getting my steps in.\nMostly looking for my glasses.',
    'I followed the recipe exactly.\nExcept for the ingredients and timing.',
    'I made room for dessert.\nThat’s the kind of planning I believe in.',
    'I said “just browsing.”\nThe checkout button heard something else.',
    'I’m very good at remembering things five minutes too late.',
    'I like my mornings slow and my toast emotionally supportive.',
    'I sat down for a minute.\nThe couch filed an extension.',
    'I packed light.\nThen added everything I might possibly need.',
    'I don’t have a junk drawer.\nI have a museum of possibilities.',
    'I deserve a little treat.\nMy evidence is that it’s today.',
    'I’m working on balance.\nOne cookie in each hand.',
    'The doorbell rang.\nSuddenly, we’re all professional detectives.',
    'I’m not overthinking.\nI’m offering the situation several unnecessary sequels.',
    'I have a backup plan.\nIt involves pajamas.',
    'I bought the salad.\nThat should count for something.',
    'My “quick errand” has developed a supporting cast.',
    'I finally found a routine.\nIt’s looking for a routine.',
    'I’m embracing change.\nUnless someone moved my favorite mug.',
    'I left early to avoid stress.\nThen stressed about being early.',
    'My patience is rechargeable.\nPlease connect coffee.',
]

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()

def persist(ledger, message, extra=()):
    LEDGER.parent.mkdir(exist_ok=True)
    LEDGER.write_text(json.dumps(ledger, indent=2) + '\n')
    git('config', 'user.name', 'circus-peanuts-bot')
    git('config', 'user.email', 'actions@users.noreply.github.com')
    git('add', 'circus/ledger.json', *extra)
    if not git('diff', '--cached', '--name-only'):
        return
    git('commit', '-m', message)
    for attempt in range(3):
        git('pull', '--rebase', 'origin', 'main')
        try:
            git('push', 'origin', 'HEAD:main')
            return
        except subprocess.CalledProcessError:
            if attempt == 2:
                raise
            time.sleep(3)

def api(method, path, token, **kwargs):
    response = requests.request(method, BASE + '/' + path, headers={'Authorization': 'Bearer ' + token}, timeout=45, **kwargs)
    if not response.ok:
        try:
            error = response.json().get('error', {})
        except ValueError:
            error = {}
        raise RuntimeError(f'Instagram HTTP {response.status_code}; code {error.get("code")}; {error.get("message", "Request failed")}')
    return response.json()

def font(size, bold=False):
    name = 'DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf'
    return ImageFont.truetype('/usr/share/fonts/truetype/dejavu/' + name, size)

def render(text, path):
    image = Image.new('RGB', (1080, 1350), '#FFF1DC')
    draw = ImageDraw.Draw(image)
    # A small geometric tent echoes the circus brand without crowding the joke.
    draw.polygon([(430, 230), (540, 140), (650, 230)], fill='#D45432')
    draw.polygon([(540, 140), (578, 230), (502, 230)], fill='#FFF1DC')
    draw.line([(440, 245), (640, 245)], fill='#22201E', width=5)
    draw.line([(540, 140), (540, 112)], fill='#22201E', width=4)
    draw.polygon([(542, 112), (580, 125), (542, 133)], fill='#D45432')
    draw.text((540, 302), 'CIRCUS PEANUTS DAILY', font=font(31, True), fill='#B24D32', anchor='mm')
    for size in range(72, 43, -2):
        f = font(size, True)
        lines = []
        for paragraph in text.split('\n'):
            line = ''
            for word in paragraph.split():
                candidate = (line + ' ' + word).strip()
                if draw.textlength(candidate, font=f) > 850 and line:
                    lines.append(line)
                    line = word
                else:
                    line = candidate
            lines.append(line)
        if len(lines) * (size + 20) <= 560:
            break
    y = 720 - len(lines) * (size + 20) / 2
    for line in lines:
        draw.text((540, y), line, font=f, fill='#22201E', anchor='mt')
        y += size + 20
    draw.line([(430, 1110), (650, 1110)], fill='#D45432', width=4)
    draw.text((540, 1170), 'LAUGH MORE. WORRY LESS.', font=font(27), fill='#B24D32', anchor='mm')
    draw.text((540, 1235), '@circuspeanutsdaily', font=font(24), fill='#22201E', anchor='mm')
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, 'JPEG', quality=95, optimize=True)

def recent_today(user, token, today):
    rows = api('GET', user + '/media', token, params={'fields': 'id,timestamp,permalink,caption', 'limit': 100}).get('data')
    if not isinstance(rows, list):
        raise RuntimeError('Could not inspect recent Circus posts')
    return [row for row in rows if dt.datetime.fromisoformat(row['timestamp'].replace('Z', '+00:00')).astimezone(ZONE).date().isoformat() == today]

def main():
    now = dt.datetime.now(ZONE)
    # Use cron slot rather than runner start time: GitHub may delay scheduled jobs.
    if os.getenv('GITHUB_EVENT_NAME') == 'schedule':
        event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
        scheduled = event.get('schedule', '')
        expected = '0 17 * * *' if now.utcoffset() == dt.timedelta(hours=-5) else '0 18 * * *'
        if scheduled != expected:
            print('Skipping alternate daylight-saving cron slot')
            return
        if now.hour < 12 or now.hour >= 14:
            print('Skipping outside noon publishing window')
            return
    today = now.date().isoformat()
    token = os.environ['CIRCUS_IG_ACCESS_TOKEN'].strip()
    user = os.environ['CIRCUS_IG_USER_ID'].strip()
    if not token or not user.isdigit():
        raise RuntimeError('Circus-specific credentials are missing')
    account = api('GET', 'me', token, params={'fields': 'user_id,username,id'})
    if account.get('username') != 'circuspeanutsdaily' or str(account.get('user_id') or account.get('id')) != user:
        raise RuntimeError('Credentials do not match @circuspeanutsdaily; publishing blocked')
    print('PASS: verified @circuspeanutsdaily')
    ledger = json.loads(LEDGER.read_text()) if LEDGER.exists() else {}
    rows = recent_today(user, token, today)
    if rows:
        entry = ledger.setdefault(today, {})
        entry.update(state='published', media_id=rows[0]['id'], permalink=rows[0].get('permalink'), verified_at=now.isoformat())
        persist(ledger, 'Circus: reconcile verified post ' + today)
        print('Already live today:', rows[0].get('permalink', rows[0]['id']))
        return
    entry = ledger.get(today, {})
    if entry.get('state') in ('submitting', 'published'):
        raise RuntimeError('Prior submission needs reconciliation; refusing a blind duplicate retry')
    if entry.get('state') != 'prepared':
        used = {x.get('joke_index') for x in ledger.values() if x.get('joke_index') is not None}
        available = [i for i in range(len(JOKES)) if i not in used]
        if not available:
            raise RuntimeError('Curated joke bank exhausted; add fresh jokes before publishing')
        index = available[0]
        text = JOKES[index]
        caption = text + '\n\nEveryday nonsense. Questionable wisdom.\nLaugh more. Worry less.\n\n#CircusPeanutsDaily #EverydayHumor #LifesACircus'
        rel = 'docs/circus-posts/' + today + '.jpg'
        render(text, ROOT / rel)
        entry = {'state': 'prepared', 'joke_index': index, 'caption': caption, 'image_path': rel}
        ledger[today] = entry
        persist(ledger, 'Circus: prepare daily joke ' + today, (rel,))
        entry['image_commit'] = git('rev-parse', 'HEAD')
        persist(ledger, 'Circus: record image commit ' + today)
    if not entry.get('image_commit'):
        entry['image_commit'] = git('log', '-1', '--format=%H', '--', entry['image_path'])
        persist(ledger, 'Circus: recover image commit ' + today)
    image_url = f'https://raw.githubusercontent.com/{os.environ["GITHUB_REPOSITORY"]}/{entry["image_commit"]}/{entry["image_path"]}'
    for attempt in range(12):
        response = requests.get(image_url, timeout=30)
        if response.ok and response.content[:3] == b'\xff\xd8\xff':
            break
        time.sleep(5)
    else:
        raise RuntimeError('Public JPEG is not ready')
    container = api('POST', user + '/media', token, data={'image_url': image_url, 'caption': entry['caption']})['id']
    for attempt in range(40):
        status = api('GET', container, token, params={'fields': 'status_code'}).get('status_code')
        if status == 'FINISHED':
            break
        if status in ('ERROR', 'EXPIRED'):
            raise RuntimeError('Instagram container failed: ' + status)
        time.sleep(3)
    else:
        raise RuntimeError('Instagram container did not become ready')
    entry.update(state='submitting', container_id=container)
    persist(ledger, 'Circus: reserve publication ' + today)
    result = api('POST', user + '/media_publish', token, data={'creation_id': container})
    entry.update(state='published', media_id=result['id'])
    persist(ledger, 'Circus: record publication ' + today)
    verified = api('GET', result['id'], token, params={'fields': 'id,permalink,timestamp'})
    entry.update(permalink=verified['permalink'], verified_at=dt.datetime.now(ZONE).isoformat())
    persist(ledger, 'Circus: verify live post ' + today)
    print('LIVE_POST:', verified['permalink'])
    with open(os.environ.get('GITHUB_STEP_SUMMARY', os.devnull), 'a') as summary:
        summary.write('Circus Peanuts Daily is live: ' + verified['permalink'] + '\n')

if __name__ == '__main__':
    main()
