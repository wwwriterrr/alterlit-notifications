"""
Карточки ленты из строк уведомлений: разбор (kinds.parse) и группировка.

Группа — уведомления одного вида за одни сутки об одном объекте («ваш комментарий
понравился: Анна, Борис и ещё 3», смены статуса одной публикации) или от одного автора
(«Анна опубликовал(а) 3 публикации») или все такие за день (обращения в поддержку).
Как группировать — Kind.group_by. Страница
строится из среза строк, поэтому группа может начаться на одной странице и продолжиться
на следующей: у таких карточек одинаковый key, остров склеивает их сам.

Без Django: строки — словари {id, status, content, is_read, date, site}, день и очистка
HTML передаются функциями (views — localdate и nh3, tools/ — свои).
"""
from .kinds import parse


def card_key(p, day, row_id):
    if p['group_by'] == 'target' and p['target'] and p['target'].get('url'):
        return f"{p['kind']}:{p['target']['url']}:{day}"
    if p['group_by'] == 'actor' and p['actor']:
        return f"{p['kind']}:@{p['actor']['username']}:{day}"
    if p['group_by'] == 'day':
        return f"{p['kind']}:{day}"
    return f"n:{row_id}"


def build_cards(rows, day_of, clean):
    """rows — новые сверху. → [карточка], в порядке самого нового уведомления карточки."""
    cards = {}
    order = []
    for r in rows:
        p = parse(r['status'], r['content'])
        day = day_of(r['date'])
        key = card_key(p, day, r['id'])
        item = {
            'id': r['id'],
            'date': r['date'],
            'is_read': r['is_read'],
            'actor': p['actor'],
            'excerpt': p['excerpt'],
            'url': p['url'],
            # у групп по автору объекты разные, у смен статуса — разный статус
            'target': p['target'],
            'extra': p['extra'],
        }
        card = cards.get(key)
        if card is None:
            card = cards[key] = {
                'key': key,
                'kind': p['kind'],
                'category': p['category'],
                'day': day,
                'date': r['date'],
                'site': r['site'],
                'target': p['target'],
                'extra': p['extra'],
                # исходный текст — для видов, которые остров не умеет рисовать сам, и на всякий случай
                'html': clean(r['content']),
                'items': [],
            }
            order.append(key)
        card['items'].append(item)
    out = []
    for key in order:
        c = cards[key]
        c['is_read'] = all(i['is_read'] for i in c['items'])
        out.append(c)
    return out


def usernames(cards):
    seen = []
    for c in cards:
        for i in c['items']:
            a = i['actor']
            if a and a['username'] not in seen:
                seen.append(a['username'])
    return seen
