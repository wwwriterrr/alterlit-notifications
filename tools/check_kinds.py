"""Проверка разбора на настоящих шаблонах текстов уведомлений (без Django): python3 -I tools/check_kinds.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'django'))
from notifications.kinds import parse  # noqa: E402

P = '/profile/anna/'
CASES = [
    ('I', f'Пользователю <a href="{P}">Анна</a> понравился ваш комментарий: <a href="/post/5/#c9">Отличный текст, спасибо</a>',
     'like_comment', 'anna', '/post/5/#c9', 'Отличный текст, спасибо'),
    ('I', f'Пользователю <a href="{P}">Анна</a> понравилась ваша публикация <a href=/post/5/>Поединок</a>',
     'like_post', 'anna', '/post/5/', ''),
    ('I', f'Пользователю <a href="{P}">Анна</a> не понравилась ваша публикация <a href="/post/5/">Поединок</a>',
     'dislike_post', 'anna', '/post/5/', ''),
    ('C', f'Пользователь <a href="{P}" target="_blank"><b>Анна</b></a> оставил комментарий к вашей публикации '
          f'<a href="/post/5/" target="_blank"><b>Поединок</b></a><br><br>Комментарий: <a href="/post/5/#c7">Браво!</a>',
     'comment', 'anna', '/post/5/#c7', 'Браво!'),
    ('CU', f'<b><a href="{P}">Анна</a></b> упомянул(а) вас в своём <a href="/post/5/#c3">комментарии</a>:<br/><a href="/post/5/#c3">@bob смотри</a>',
     'mention', 'anna', '/post/5/#c3', '@bob смотри'),
    ('CU', f'<b><a href="{P}">Анна</a></b> упомянул(а) вас в своём комментарии: <div class="ntf-comment"><a href="/post/5/#c4">@bob ну</a></div>',
     'mention', 'anna', '/post/5/#c4', '@bob ну'),
    ('I', 'На вашу публикацию <a href="/post/5/"><b>"Поединок"</b></a> написали рецензию <a href="/post/6/"><b>"О поединке"</b></a>',
     'review', None, '/post/6/', ''),
    ('I', 'Изменился статус публикации <a href="/post/5/">"Поединок"</a><br>Новый стaтус: <b>Отклонено</b><br>Причина отказа: <b>Мат</b>',
     'post_status', None, '/post/5/', ''),
    ('I', 'Ваш текст <a href="/post/5/">"Поединок"</a> опубликован в <a href="/profile/bob/">профиле</a>. Вы можете разместить его на <a href="/ebloscope/">Ярмарке</a>',
     'post_status', None, '/post/5/', ''),
    ('I', 'Ваша публикация "Поединок" была удалена модератором <b><a href="/profile/mod/">Мод</a></b>',
     'post_deleted', 'mod', None, ''),
    ('PS', f'Пользователь <a href="{P}" target="_blank" style="text-decoration: underline;">Анна</a> добавил новую публикацию '
           '<a href="/post/8/" target="_blank" style="text-decoration: underline;">Новое</a>',
     'new_post', 'anna', '/post/8/', ''),
    ('I', 'Пользователь <a href="/profile/anna/">Анна</a> добавил новую публикацию <a href="/post/8/">Новое</a>',
     'new_post', 'anna', '/post/8/', ''),
    ('I', 'Ваш аккаунт заблокирован.<br>Вам запрещены любые авторизованные действия на сайте.', 'account', None, None, ''),
    ('SP', 'Новое <a href="/admin/support/task/5/" target="_blank">обращение</a> в поддержку от пользователя сайта <b>Анна</b>',
     'support', None, '/admin/support/task/5/', ''),
    ('MN', '<a class="tr-finance-link" href="/finance/">Списание с баланса: 10 L</a>', 'finance', None, '/finance/', ''),
    ('I', 'Снято выделение цветом объявления "Продам гараж"', 'other', None, None, ''),
]

bad = 0
for status, html, kind, user, url, excerpt in CASES:
    p = parse(status, html)
    got = (p['kind'], p['actor']['username'] if p['actor'] else None, p['url'], p['excerpt'])
    want = (kind, user, url, excerpt)
    flag = 'ok ' if got == want else 'BAD'
    bad += got != want
    print(flag, kind, '' if got == want else f'\n    got  {got}\n    want {want}', p['target'], p['extra'] or '')
# группировка: смены статуса одной публикации и новые публикации одного автора — по одной карточке
from datetime import datetime  # noqa: E402
from notifications.group import build_cards  # noqa: E402

NEW = ('Пользователь <a href="/profile/anna/" target="_blank" style="text-decoration: underline;">Анна</a> добавил новую '
       'публикацию <a href="/post/{0}/" target="_blank" style="text-decoration: underline;">Текст {0}</a>')
STATUS = 'Изменился статус публикации <a href="/post/5/">"Поединок"</a><br>Новый стaтус: <b>{}</b>'
SUP = 'Новое <a href="/task/{0}/" target="_blank">обращение</a> в поддержку от {1} <b>{2}</b>'
rows = [
    {'id': 9, 'status': 'SP', 'content': SUP.format(2, 'неавторизованного пользователя', 'a@b.ru'), 'is_read': False,
     'date': datetime(2026, 10, 26, 13), 'site': 'AL'},
    {'id': 8, 'status': 'SP', 'content': SUP.format(1, 'пользователя сайта', 'Анна'), 'is_read': False,
     'date': datetime(2026, 10, 26, 12, 30), 'site': 'AL'},
    {'id': 6, 'status': 'I', 'content': NEW.format(3), 'is_read': False, 'date': datetime(2026, 10, 26, 12), 'site': 'AL'},
    {'id': 5, 'status': 'PS', 'content': NEW.format(2), 'is_read': False, 'date': datetime(2026, 10, 26, 11), 'site': 'AL'},
    {'id': 4, 'status': 'I', 'content': STATUS.format('Опубликовано'), 'is_read': True, 'date': datetime(2026, 10, 26, 10), 'site': 'AL'},
    {'id': 3, 'status': 'I', 'content': STATUS.format('На модерации'), 'is_read': True, 'date': datetime(2026, 10, 26, 9), 'site': 'AL'},
    {'id': 2, 'status': 'I', 'content': NEW.format(1), 'is_read': True, 'date': datetime(2026, 10, 25, 9), 'site': 'AL'},
]
cards = build_cards(rows, day_of=lambda d: d.date().isoformat(), clean=lambda h: h)
got = [(c['kind'], [i['id'] for i in c['items']]) for c in cards]
want = [('support', [9, 8]), ('new_post', [6, 5]), ('post_status', [4, 3]), ('new_post', [2])]
sup = cards[0]['items']
ok_sup = [i['extra'] for i in sup] == [{'from': 'a@b.ru', 'guest': True}, {'from': 'Анна', 'guest': False}]
bad += not ok_sup
print('ok ' if ok_sup else 'BAD', 'поддержка: от кого', [i['extra'] for i in sup])
ok = got == want
bad += not ok
print('ok ' if ok else 'BAD', 'группировка', '' if ok else f'\n    got  {got}\n    want {want}')
# настройки: выключенное не создаётся, остальное — как обычно
from notifications import settings  # noqa: E402


class Profile:
    meta = {}

    def get_meta(self, key, none_value=None):
        return self.meta.get(key, none_value)

    def set_meta(self, key, value):
        self.meta[key] = value


class User:
    profile = Profile()


user = User()
settings.update(user, {'likes_comments': False, 'mentions': False, 'nonsense': False})
checks = [
    (CASES[0], True),   # оценка комментария — выключена
    (CASES[4], True),   # упоминание — выключено
    (CASES[1], False),  # оценка публикации — включена
    (CASES[3], False),  # комментарий — включён
]
ok = all(settings.is_muted(user, c[0], c[1]) == want for c, want in checks) and user.profile.meta['notify_off'] == ['likes_comments', 'mentions']
settings.update(user, {'mentions': True})
ok = ok and not settings.is_muted(user, CASES[4][0], CASES[4][1])
bad += not ok
print('ok ' if ok else 'BAD', 'настройки', [o['enabled'] for o in settings.options(user)])
print('fails:', bad)
sys.exit(1 if bad else 0)
