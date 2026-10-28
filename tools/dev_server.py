"""
Заглушка API для разработки острова: те же kinds.py и group.py, что на сервере, но строки —
выдуманные и в памяти. Фильтр вкладок — через разбор текста (на сервере — SQL kinds.category_q).

    python3 -I tools/dev_server.py        # http://127.0.0.1:5186, vite проксирует при DEV_FIXTURES=1
"""
import json
import random
import sys
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'django'))
from notifications import kinds  # noqa: E402
from notifications.group import build_cards, usernames  # noqa: E402

PAGE = 40
random.seed(7)
NOW = datetime.now(timezone.utc).replace(microsecond=0)
USERS = {
    'anna': 'Анна Ветрова', 'boris': 'Борис', 'vera': 'Вера Лис', 'gleb': 'Глеб', 'dina': 'Дина',
    'egor': 'Егор Пятый', 'zhenya': 'Женя', 'ilya': 'Илья', 'kira': 'Кира', 'lev': 'Лев Толстой-младший',
}
POSTS = [(5, 'Поединок. Пентон 2'), (6, 'Осень в Тарусе'), (7, 'Письма незнакомке'), (8, 'Стихи о нигде')]
COMMENTS = ['Отличный текст, перечитал дважды', 'Финал не убедил, но язык прекрасный',
            'Спасибо! Очень точно про осень', 'А продолжение будет?', 'Сильно. Особенно третья глава']


def u(name):
    return f'<a href="/profile/{name}/">{USERS[name]}</a>'


def rows():
    out = []
    t = NOW

    def add(status, content, minutes, read=None):
        nonlocal t
        t -= timedelta(minutes=minutes)
        out.append({'id': 0, 'status': status, 'content': content, 'date': t, 'site': 'AL',
                    'is_read': (t < NOW - timedelta(hours=20)) if read is None else read})

    for day in range(9):
        for name in random.sample(list(USERS), 5):
            add('I', f'Пользователю {u(name)} понравился ваш комментарий: <a href="/post/5/#c91">{COMMENTS[0]}</a>', 7)
        pid, title = POSTS[day % 4]
        for name in random.sample(list(USERS), 3):
            add('I', f'Пользователю {u(name)} понравилась ваша публикация <a href=/post/{pid}/>{title}</a>', 11)
        for name in random.sample(list(USERS), 3):
            c = random.choice(COMMENTS)
            add('C', f'Пользователь <a href="/profile/{name}/" target="_blank"><b>{USERS[name]}</b></a> оставил комментарий к вашей '
                     f'публикации <a href="/post/{pid}/" target="_blank"><b>{title}</b></a><br><br>Комментарий: '
                     f'<a href="/post/{pid}/#c{random.randint(100, 999)}">{c}</a>', 23)
        add('CU', f'<b>{u("kira")}</b> упомянул(а) вас в своём комментарии: <div class="ntf-comment">'
                  f'<a href="/post/6/#c{day}">@devil посмотри, тут про тебя</a></div>', 35)
        if day % 2 == 0:
            add('I', f'На вашу публикацию <a href="/post/{pid}/"><b>"{title}"</b></a> написали рецензию '
                     '<a href="/post/77/"><b>"Разбор полётов"</b></a>', 50)
            add('I', 'Изменился статус публикации <a href="/post/9/">"Черновик века"</a><br>Новый стaтус: <b>Отклонено</b>'
                     '<br>Причина отказа: <b>Слишком коротко</b>', 30)
            add('I', 'Изменился статус публикации <a href="/post/9/">"Черновик века"</a><br>Новый стaтус: <b>На модерации</b>', 25)
        add('MN', '<a class="tr-finance-link" href="/finance/">Пополнение баланса: 100 L</a><br>Сообщение: <b>за конкурс</b>', 60)
        add('PS', f'Пользователь <a href="/profile/vera/" target="_blank" style="text-decoration: underline;">{USERS["vera"]}</a> '
                  'добавил новую публикацию <a href="/post/12/" target="_blank" style="text-decoration: underline;">Новые стихи</a>', 90)
        add('I', f'Пользователь <a href="/profile/vera/" target="_blank" style="text-decoration: underline;">{USERS["vera"]}</a> '
                 f'добавил новую публикацию <a href="/post/{13 + day}/" target="_blank" style="text-decoration: underline;">Эссе {day}</a>', 40)
        for who, sender in (('пользователя сайта', USERS['dina']), ('неавторизованного пользователя', 'guest@mail.ru'),
                            ('пользователя сайта', USERS['ilya'])):
            add('SP', f'Новое <a href="/admin/support/task/{day}{len(out)}/" target="_blank">обращение</a> в поддержку '
                      f'от {who} <b>{sender}</b>', 15)
        if day == 3:
            add('I', 'Снято выделение цветом объявления "Продам гараж"', 40)
            add('I', 'Ваша публикация "Старое" была удалена модератором <b><a href="/profile/lev/">Лев Толстой-младший</a></b>', 40)
        t -= timedelta(hours=random.randint(6, 12))
    for n, r in enumerate(reversed(out), start=1):
        r['id'] = n
    return out


DB = rows()


def category_of(r):
    return kinds.parse(r['status'], r['content'])['category']


def matching(params):
    category = params.get('category')
    q = (params.get('q') or '').lower()
    res = [r for r in DB if (not category or category_of(r) == category)
           and (params.get('unread') not in ('1', 'true') or not r['is_read'])
           and (not q or q in r['content'].lower())]
    return sorted(res, key=lambda r: (r['date'], r['id']), reverse=True)


def page(params):
    res = matching(params)
    if params.get('after'):
        res = [r for r in res if r['id'] > int(params['after'])]
    if params.get('cursor'):
        d, i = params['cursor'].rsplit('|', 1)
        d, i = datetime.fromisoformat(d), int(i)
        res = [r for r in res if (r['date'], r['id']) < (d, i)]
    more = len(res) > PAGE
    res = res[:PAGE]
    cards = build_cards(res, day_of=lambda d: d.astimezone().date().isoformat(), clean=lambda h: h)
    for c in cards:
        c['date'] = c['date'].isoformat()
        for it in c['items']:
            it['date'] = it['date'].isoformat()
    return {
        'cards': cards,
        'people': {n: {'name': USERS.get(n, n), 'avatar': None} for n in usernames(cards)},
        'next': f"{res[-1]['date'].isoformat()}|{res[-1]['id']}" if more else None,
        'unread': sum(not r['is_read'] for r in DB),
    }


def counts():
    cats = []
    for code, label in kinds.CATEGORIES:
        rs = [r for r in DB if category_of(r) == code]
        cats.append({'code': code, 'label': label, 'total': len(rs), 'unread': sum(not r['is_read'] for r in rs)})
    return {'all': {'total': len(DB), 'unread': sum(not r['is_read'] for r in DB)}, 'categories': cats}


class H(BaseHTTPRequestHandler):
    def _json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('content-type', 'application/json; charset=utf-8')
        self.send_header('content-length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlparse(self.path)
        params = {k: v[0] for k, v in parse_qs(url.query).items()}
        if url.path == '/api/v1/notifications/':
            return self._json(page(params))
        if url.path == '/api/v1/notifications/counts/':
            return self._json(counts())
        self._json({'detail': 'dev: нет такой заглушки'}, 404)

    def do_POST(self):
        global DB
        url = urlparse(self.path)
        data = json.loads(self.rfile.read(int(self.headers.get('content-length') or 0)) or b'{}')
        unread = lambda: sum(not r['is_read'] for r in DB)  # noqa: E731
        if url.path == '/api/v1/notifications/read/':
            ids = None if data.get('all') is True else set(data.get('ids') or [])
            marked = 0
            for r in DB:
                if not r['is_read'] and (ids is None or r['id'] in ids):
                    r['is_read'] = True
                    marked += 1
            return self._json({'marked': marked, 'unread': unread()})
        if url.path == '/api/v1/notifications/dev-add/':
            # имитация: кто-то лайкнул тот же комментарий (группа «сегодня» пополнится и всплывёт)
            name = data.get('who', 'lev')
            DB.append({'id': max(r['id'] for r in DB) + 1, 'status': 'I', 'site': 'AL', 'is_read': False,
                       'date': datetime.now(timezone.utc).replace(microsecond=0),
                       'content': f'Пользователю {u(name)} понравился ваш комментарий: <a href="/post/5/#c91">{COMMENTS[0]}</a>'})
            return self._json({'ok': True})
        if url.path == '/api/v1/notifications/delete/':
            if data.get('read') is True:
                gone = {r['id'] for r in DB if r['is_read']}
            else:
                gone = {r['id'] for r in matching(data)} if data.get('all') is True else set(data.get('ids') or [])
            before = len(DB)
            DB = [r for r in DB if r['id'] not in gone]
            return self._json({'deleted': before - len(DB), 'unread': unread()})
        self._json({'detail': 'dev: нет такой заглушки'}, 404)

    def log_message(self, *a):
        pass


if __name__ == '__main__':
    print(f'заглушки уведомлений: {len(DB)} строк, http://127.0.0.1:5186')
    ThreadingHTTPServer(('127.0.0.1', 5186), H).serve_forever()
