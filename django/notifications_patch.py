# Страница уведомлений /notifications/ — бэк острова (api/notifications/).
#
# Ставится рядом со старым кодом и ничего в нём не меняет. Использует уже выложенные
# функции юзербара из api/notification/notifications.py: SITES_BY_MODE, request_mode,
# push_notifications_count (счётчик колокольчика после «прочитать» и «удалить»).
# Очистка HTML — nh3 (уже стоит для редактора).
#
# Что внутри:
#   api/notifications/kinds.py     — вид уведомления по тексту: шаблоны, фильтры вкладок, разбор
#   api/notifications/group.py     — карточки ленты и группировка (одного вида, об одном объекте, за сутки)
#   api/notifications/sanitize.py  — очистка HTML уведомления
#   api/notifications/service.py   — выборки, счётчики, прочитать, удалить
#   api/notifications/settings.py  — какие уведомления пользователь отключил (мета профиля notify_off)
#   api/notifications/views.py     — ручки (описание формата — в начале файла)
#   api/notifications/urls.py
#   в конце — страница /notifications/, шаблон и индекс
#
# Ручки (префикс /api/v1/):
#   GET  notifications/?category=&unread=1&q=&cursor=   лента
#   GET  notifications/counts/                          вкладки со счётчиками
#   POST notifications/read/    {"ids": [..]} | {"all": true}
#   POST notifications/delete/  {"ids": [..]} | {"all": true, "category", "unread", "q"}
#        по ids — свои, у is_staff — любые
#   GET/PUT notifications/settings/                     отключение уведомлений по видам


# ── 1. api/notifications/__init__.py — пустой файл ────────────────────────────


# ── 2. api/notifications/kinds.py ─────────────────────────────────────────────
"""
Вид уведомления по его тексту. У модели Notification тип почти нигде не записан: лайки,
рецензии, решения модерации — всё под status='I', отличить можно только по шаблону текста.
Здесь — единственное место, где перечислены шаблоны: и для разбора (parse), и для фильтра
в базе (kind_q / category_q). Новый шаблон уведомления — новая запись в KINDS.

Модуль без Django ORM (кроме Q, который импортируется лениво), чтобы разбор проверялся
отдельно: tools/check_kinds.py.
"""
import re
from dataclasses import dataclass, field
from html import unescape
from urllib.parse import unquote


@dataclass(frozen=True)
class Kind:
    code: str
    category: str
    statuses: tuple = ('I',)
    any_of: tuple = ()      # текст содержит хотя бы одну из строк (пусто — любой текст этого статуса)
    none_of: tuple = ()     # и не содержит ни одной из этих
    # одна карточка за сутки: 'target' — об одном объекте, 'actor' — от одного автора,
    # 'day' — все такие за день (обращения в поддержку), None — по одному
    group_by: str = None  # без «str | None»: на сервере может быть Python старше 3.10


# Порядок важен: первое совпадение — вид уведомления.
KINDS = (
    Kind('like_comment', 'likes', any_of=('понравился ваш комментарий',), group_by='target'),
    Kind('dislike_post', 'likes', any_of=('не понравилась ваша публикация',), group_by='target'),
    Kind('like_post', 'likes', any_of=('понравилась ваша публикация',), group_by='target'),
    Kind('comment', 'comments', statuses=('C',), group_by='target'),
    Kind('mention', 'mentions', statuses=('CU',)),
    Kind('review', 'posts', any_of=('написали рецензию',)),
    Kind('post_status', 'posts', any_of=('Изменился статус публикации', 'опубликован в <a'), group_by='target'),
    Kind('post_deleted', 'posts', any_of=('удалена модератором', 'удалён модератором')),
    Kind('new_post', 'subscriptions', statuses=('PS',), group_by='actor'),
    # та же рассылка подписчикам бывала и со статусом по умолчанию
    Kind('new_post', 'subscriptions', any_of=('добавил новую публикацию',), group_by='actor'),
    Kind('account', 'service', any_of=('Ваш аккаунт заблокирован',)),
    Kind('finance', 'finance', statuses=('MN',)),
    Kind('support', 'service', statuses=('SP',), group_by='day'),
    Kind('moderation', 'service', statuses=('M',)),
)
# у каких видов в тексте есть «кто сделал» (ссылка на профиль); у остальных она — о другом
WITH_ACTOR = {'like_comment', 'dislike_post', 'like_post', 'comment', 'mention', 'post_deleted', 'new_post'}
OTHER = 'other'

# Вкладки фильтра — в таком порядке и с такими подписями на странице
CATEGORIES = (
    ('comments', 'Комментарии'),
    ('mentions', 'Упоминания'),
    ('likes', 'Оценки'),
    ('posts', 'Публикации'),
    ('subscriptions', 'Подписки'),
    ('finance', 'Финансы'),
    ('service', 'Служебные'),
    (OTHER, 'Прочее'),
)
CATEGORY_CODES = {c for c, _ in CATEGORIES}

# Что пользователь может отключить на странице уведомлений: (код, подпись, группа, виды).
# Код хранится в профиле (settings.py), поэтому его не переименовывают; новые пункты — в конец группы.
SETTINGS = (
    ('likes_posts', 'Оценки моих публикаций', 'Оценки', ('like_post', 'dislike_post')),
    ('likes_comments', 'Оценки моих комментариев', 'Оценки', ('like_comment',)),
    ('comments', 'Комментарии к моим публикациям', 'Комментарии', ('comment',)),
    ('mentions', 'Упоминания в комментариях', 'Комментарии', ('mention',)),
)
SETTING_CODES = {code for code, *_ in SETTINGS}


def kind_of(status, content):
    content = content or ''
    for k in KINDS:
        if status not in k.statuses:
            continue
        if k.any_of and not any(m in content for m in k.any_of):
            continue
        if any(m in content for m in k.none_of):
            continue
        return k
    return None


# ── фильтр в базе ───────────────────────────────────────────────────────────
def kind_q(k):
    from django.db.models import Q
    q = Q(status__in=k.statuses)
    if k.any_of:
        alt = Q()
        for m in k.any_of:
            alt |= Q(content__contains=m)
        q &= alt
    for m in k.none_of:
        q &= ~Q(content__contains=m)
    return q


def _first_match_q(k):
    """Уведомление этого вида с учётом порядка: подходит под k и не под виды раньше него."""
    q = kind_q(k)
    for prev in KINDS:
        if prev is k:
            break
        if set(prev.statuses) & set(k.statuses):
            q &= ~kind_q(prev)
    return q


def category_q(category):
    """Q для вкладки; 'other' — всё, что не подошло ни под один вид."""
    from django.db.models import Q
    if category == OTHER:
        q = Q()
        for k in KINDS:
            q &= ~kind_q(k)
        return q
    parts = [_first_match_q(k) for k in KINDS if k.category == category]
    q = parts[0]
    for p in parts[1:]:
        q |= p
    return q


# ── разбор текста ───────────────────────────────────────────────────────────
RE_A = re.compile(r'<a\b([^>]*)>(.*?)</a\s*>', re.S | re.I)
RE_HREF = re.compile(r'''href\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))''', re.I)
RE_TAG = re.compile(r'<[^>]+>')
RE_PROFILE = re.compile(r'^(?:https?://[^/]+)?/profile/([^/?#]+)/?(?:[?#].*)?$')
RE_B = re.compile(r'<b>(.*?)</b>', re.S | re.I)


def text(html):
    return re.sub(r'\s+', ' ', unescape(RE_TAG.sub(' ', html or ''))).strip()


def _title(s):
    """Название из ссылки: без кавычек вокруг (шаблоны пишут «"Название"»)."""
    s = text(s)
    if len(s) >= 2 and s[0] == s[-1] == '"':
        s = s[1:-1].strip()
    return s


def links(html):
    out = []
    for m in RE_A.finditer(html or ''):
        h = RE_HREF.search(m.group(1))
        href = unescape(next(g for g in h.groups() if g is not None)) if h else ''
        out.append({'url': href, 'text': m.group(2), 'start': m.start(), 'end': m.end()})
    return out


def profile_username(url):
    m = RE_PROFILE.match(url or '')
    return unquote(m.group(1)) if m else None


def _actor(ls):
    for a in ls:
        u = profile_username(a['url'])
        if u:
            return {'username': u, 'name': text(a['text']) or u, 'url': a['url']}
    return None


def _after(ls, html, marker):
    """Первая ссылка после слов marker."""
    i = html.find(marker)
    if i < 0:
        return None
    return next((a for a in ls if a['start'] > i), None)


def _non_profile(ls):
    return [a for a in ls if not profile_username(a['url'])]


def parse(status, content):
    """→ {'kind', 'category', 'group', 'actor', 'target', 'excerpt', 'url', 'extra'} или kind=other.

    actor — кто сделал ({username, name, url}), target — о чём ({url, title}),
    excerpt — текст комментария, url — куда ведёт карточка.
    """
    html = content or ''
    k = kind_of(status, html)
    out = {'kind': k.code if k else OTHER, 'category': k.category if k else OTHER, 'group_by': k.group_by if k else None,
           'actor': None, 'target': None, 'excerpt': '', 'url': None, 'extra': {}}
    if k is None:
        return out
    ls = links(html)
    other = _non_profile(ls)
    actor = _actor(ls)

    if k.code == 'like_comment':
        a = _after(ls, html, 'понравился ваш комментарий')
        if a:
            out.update(target={'url': a['url'], 'title': ''}, excerpt=text(a['text']), url=a['url'])
    elif k.code in ('like_post', 'dislike_post'):
        a = _after(ls, html, 'ваша публикация')
        if a:
            out.update(target={'url': a['url'], 'title': _title(a['text'])}, url=a['url'])
    elif k.code == 'comment':
        # «Пользователь <a>Имя</a> оставил комментарий к вашей публикации <a>Пост</a> … Комментарий: <a>текст</a>»
        post = _after(ls, html, 'к вашей публикации') or (other[0] if other else None)
        com = _after(ls, html, 'Комментарий:') or (other[-1] if len(other) > 1 else None)
        if post:
            out['target'] = {'url': post['url'], 'title': _title(post['text'])}
        if com:
            out.update(excerpt=text(com['text']), url=com['url'])
        else:
            out['url'] = post['url'] if post else None
    elif k.code == 'mention':
        # два шаблона; текст комментария — в последней ссылке
        if other:
            last = other[-1]
            out.update(excerpt=text(last['text']), url=last['url'])
            out['target'] = {'url': last['url'], 'title': ''}
    elif k.code == 'review':
        if len(other) >= 2:
            out['target'] = {'url': other[0]['url'], 'title': _title(other[0]['text'])}
            out['extra']['review'] = {'url': other[1]['url'], 'title': _title(other[1]['text'])}
            out['url'] = other[1]['url']
    elif k.code == 'post_status':
        if other:
            out['target'] = {'url': other[0]['url'], 'title': _title(other[0]['text'])}
            out['url'] = other[0]['url']
        if 'опубликован в <a' in html:
            out['extra']['status'] = 'В профиле'
        else:
            bs = [text(b) for b in RE_B.findall(html)]
            if bs:
                out['extra']['status'] = bs[0]
            m = re.search(r'Причина отказа:\s*<b>(.*?)</b>', html, re.S)
            if m:
                out['extra']['reason'] = text(m.group(1))
    elif k.code == 'post_deleted':
        m = re.search(r'"(.*?)"\s*был', html, re.S)
        if m:
            out['target'] = {'url': None, 'title': text(m.group(1))}
        out['extra']['draft'] = 'черновик' in html.lower()
    elif k.code == 'support':
        # «Новое <a>обращение</a> в поддержку от пользователя сайта <b>Имя</b>» (или «от неавторизованного … <b>почта</b>»)
        if other:
            out['url'] = other[0]['url']
        m = re.search(r'от (неавторизованного )?пользовател\w*(?: сайта)?\s*<b>(.*?)</b>', html, re.S)
        if m:
            out['extra'] = {'from': text(m.group(2)), 'guest': bool(m.group(1))}
    elif k.code == 'new_post':
        if other:
            out['target'] = {'url': other[0]['url'], 'title': _title(other[0]['text'])}
            out['url'] = other[0]['url']
    elif other:
        out['url'] = other[0]['url']

    if k.code in WITH_ACTOR:
        out['actor'] = actor
    return out


# ── 3. api/notifications/group.py ─────────────────────────────────────────────
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


# ── 4. api/notifications/sanitize.py ──────────────────────────────────────────
"""Текст уведомления для страницы: только ссылки и простое выделение, без стилей и скриптов.
Названия публикаций в старых шаблонах попадали в HTML без экранирования."""
import nh3

TAGS = {'a', 'b', 'strong', 'i', 'em', 'br', 'div', 'span', 'p'}
ATTRS = {'a': {'href'}}


def clean(html):
    return nh3.clean(html or '', tags=TAGS, attributes=ATTRS, url_schemes={'http', 'https', 'mailto'},
                     link_rel='noopener noreferrer')


# ── 5. api/notifications/service.py ───────────────────────────────────────────
"""Выборки, счётчики, «прочитать» и «удалить» — для views. Сайт — request.mode, как у юзербара."""
from datetime import datetime

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone as tz

from blog.models import Notification
from api.notification.notifications import SITES_BY_MODE, push_notifications_count

from . import kinds
from .group import build_cards, usernames
from .sanitize import clean

PAGE = 40           # строк уведомлений на страницу (карточек может выйти меньше — группы)
Q_MIN, Q_MAX = 2, 100
IDS_MAX = 1000      # за один запрос «прочитать» / «удалить»


def own(user, mode):
    """Уведомления пользователя для сайта запроса: alterlit — AL/ALL, altcg — ALT/ALL."""
    return Notification.objects.filter(to_id=user.id, site__in=SITES_BY_MODE[mode])


def filtered(user, mode, category=None, unread=False, q=''):
    qs = own(user, mode)
    if category:
        qs = qs.filter(kinds.category_q(category))
    if unread:
        qs = qs.filter(is_read=False)
    if q:
        qs = qs.filter(content__icontains=q)
    return qs


# ── курсор: дата и id последнего уведомления страницы ───────────────────────
def encode_cursor(row):
    return f"{row['date'].isoformat()}|{row['id']}"


def decode_cursor(cursor):
    """→ (date, id) или None, если курсор испорчен."""
    try:
        d, i = cursor.rsplit('|', 1)
        return datetime.fromisoformat(d), int(i)
    except (ValueError, AttributeError):
        return None


def _day(d):
    """День уведомления по местному времени; при USE_TZ=False даты без пояса — уже местные."""
    return (d.date() if tz.is_naive(d) else tz.localdate(d)).isoformat()


def page(user, mode, category=None, unread=False, q='', cursor=None, after=None):
    qs = filtered(user, mode, category, unread, q).order_by('-date', '-id')
    if after:
        # только пришедшие после уведомления after — остров дописывает их сверху ленты
        qs = qs.filter(id__gt=after)
    if cursor:
        d, i = cursor
        # id — второй ключ: уведомления, созданные одной рассылкой, могут совпасть по времени
        qs = qs.filter(Q(date__lt=d) | Q(date=d, id__lt=i))
    rows = list(qs.values('id', 'status', 'content', 'is_read', 'date', 'site')[:PAGE + 1])
    more = len(rows) > PAGE
    rows = rows[:PAGE]
    cards = build_cards(rows, day_of=_day, clean=clean)
    for c in cards:
        c['date'] = c['date'].isoformat()
        for it in c['items']:
            it['date'] = it['date'].isoformat()
    return {
        'cards': cards,
        'people': people(usernames(cards)),
        'next': encode_cursor(rows[-1]) if more else None,
    }


def people(names):
    """Имя и аватар авторов страницы — одним запросом (в тексте уведомления только имя и ссылка)."""
    if not names:
        return {}
    out = {}
    for u in User.objects.filter(username__in=names).select_related('profile'):
        profile = getattr(u, 'profile', None)
        avatar = getattr(profile, 'avatar', None)
        try:
            avatar_url = avatar.url if avatar else None
        except ValueError:
            avatar_url = None
        out[u.username] = {
            'name': (getattr(profile, 'nickname', '') or '').strip() or u.username,
            'avatar': avatar_url,
        }
    return out


def counts(user, mode):
    """Сколько всего и непрочитанных — по вкладкам; одним проходом по уведомлениям пользователя."""
    aggr = {'all_t': Count('id'), 'all_u': Count('id', filter=Q(is_read=False))}
    for code, _ in kinds.CATEGORIES:
        q = kinds.category_q(code)
        aggr[f'{code}_t'] = Count('id', filter=q)
        aggr[f'{code}_u'] = Count('id', filter=q & Q(is_read=False))
    r = own(user, mode).aggregate(**aggr)
    return {
        'all': {'total': r['all_t'], 'unread': r['all_u']},
        'categories': [{'code': code, 'label': label, 'total': r[f'{code}_t'], 'unread': r[f'{code}_u']}
                       for code, label in kinds.CATEGORIES],
    }


def unread_count(user, mode):
    return own(user, mode).filter(is_read=False).count()


def mark_read(user, mode, ids=None):
    """Прочитать свои уведомления: ids — эти, None — все непрочитанные сайта. → сколько."""
    qs = own(user, mode).filter(is_read=False)
    if ids is not None:
        qs = qs.filter(id__in=ids)
    marked = qs.update(is_read=True)  # update() сигналов не шлёт — счётчик пересчитываем сами
    if marked:
        push_notifications_count(user.id)
    return marked


def delete(user, mode, ids=None, category=None, unread=False, q='', read_only=False):
    """Удалить: ids — эти (свои; у is_staff — любые), ids=None — все свои по фильтру вкладки;
    read_only — все свои прочитанные на этом сайте (фильтры вкладки не учитываются).
    Одним DELETE без сигналов: post_delete у Notification пересчитывает счётчик на каждую
    строку, а здесь их могут быть тысячи. Счётчик — один раз каждому, кого коснулось."""
    if read_only:
        qs = own(user, mode).filter(is_read=True)
    elif ids is None:
        qs = filtered(user, mode, category, unread, q)
    elif user.is_staff:
        qs = Notification.objects.filter(id__in=ids)
    else:
        qs = Notification.objects.filter(to_id=user.id, id__in=ids)
    with transaction.atomic():
        touched = set(qs.filter(is_read=False).values_list('to_id', flat=True).distinct())
        deleted = qs._raw_delete(qs.db)
    for to_id in touched:
        push_notifications_count(to_id)
    return deleted


# ── 6. api/notifications/settings.py ──────────────────────────────────────────
"""
Какие уведомления пользователь отключил: список кодов kinds.SETTINGS в мета профиля
(ключ notify_off). Проверка — в Notification.create_notif: выключенное уведомление
не создаётся вовсе (нет ни в ленте, ни в счётчике, ни в сокете). Старые не трогаются.
"""
import logging

from . import kinds

logger = logging.getLogger(__name__)
META_KEY = 'notify_off'


def disabled(user):
    """Коды выключенных пунктов настроек."""
    try:
        raw = user.profile.get_meta(META_KEY, none_value=[]) or []
    except Exception:
        return set()
    return {c for c in raw if c in kinds.SETTING_CODES}


def muted_kinds(user):
    off = disabled(user)
    return {k for code, _label, _group, ks in kinds.SETTINGS if code in off for k in ks}


def is_muted(user, status, content):
    """Не создавать ли уведомление этому пользователю. Любая ошибка — создать (лучше лишнее, чем потерянное)."""
    try:
        off = muted_kinds(user)
        if not off:
            return False
        k = kinds.kind_of(status, content)
        return bool(k and k.code in off)
    except Exception:
        logger.exception('notify settings check')
        return False


def options(user):
    off = disabled(user)
    return [{'code': code, 'label': label, 'group': group, 'enabled': code not in off}
            for code, label, group, _ks in kinds.SETTINGS]


def update(user, changes):
    """changes — {код: включено}. Неизвестные коды пропускаются. → options(user)"""
    off = disabled(user)
    for code, enabled in changes.items():
        if code not in kinds.SETTING_CODES:
            continue
        if enabled:
            off.discard(code)
        else:
            off.add(code)
    user.profile.set_meta(META_KEY, sorted(off))
    return options(user)


# ── 7. api/notifications/views.py ─────────────────────────────────────────────
"""
Страница уведомлений /notifications/ — REST для острова. Только сессия (SessionAuthentication),
запись — с X-CSRFToken. Сайт — request.mode: alterlit видит AL/ALL, altcg — ALT/ALL.

  GET  /api/v1/notifications/?category=&unread=1&q=&cursor=&after=
       after=<id> — только уведомления новее этого (живое добавление по событию сокета)
       → {"cards": [карточка], "people": {username: {name, avatar}}, "next": курсор | null, "unread": n}
       карточка — одно уведомление или группа (kinds.py, group.py):
       {key, kind, category, day, date, site, is_read, target, extra, html, items: [{id, date, is_read, actor, excerpt, url}]}
  GET  /api/v1/notifications/counts/
       → {"all": {total, unread}, "categories": [{code, label, total, unread}]}
  POST /api/v1/notifications/read/     {"ids": [..]} | {"all": true}            → {"marked", "unread"}
  GET  /api/v1/notifications/settings/
       → {"options": [{code, label, group, enabled}]}  — что можно отключить (kinds.SETTINGS)
  PUT  /api/v1/notifications/settings/  {"likes_posts": false, …}  → то же
       Выключенное не создаётся (Notification.create_notif → settings.is_muted).
  POST /api/v1/notifications/delete/   {"ids": [..]} | {"all": true, "category", "unread", "q"} | {"read": true}
       → {"deleted", "unread"}; по ids — только свои, у is_staff — любые; all — свои по фильтру;
       read — все свои прочитанные на сайте запроса
"""
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.notification.notifications import request_mode

from . import kinds, service, settings


class Base(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]


def _bad(field, text):
    return Response({'detail': text, 'errors': {field: text}}, status=400)


def _filters(params):
    """category, unread, q из запроса → (значения, ошибка-ответ | None)."""
    category = (params.get('category') or '').strip() or None
    if category and category not in kinds.CATEGORY_CODES:
        return None, _bad('category', 'Неизвестная вкладка')
    unread = str(params.get('unread') or '').lower() in ('1', 'true')
    q = (params.get('q') or '').strip()
    if q and not service.Q_MIN <= len(q) <= service.Q_MAX:
        return None, _bad('q', f'Поиск — от {service.Q_MIN} до {service.Q_MAX} знаков')
    return (category, unread, q), None


def _ids(data):
    raw = data.get('ids') if hasattr(data, 'get') else None
    if not isinstance(raw, list) or not raw:
        return None, _bad('ids', 'Не выбраны уведомления')
    if len(raw) > service.IDS_MAX:
        return None, _bad('ids', f'Не больше {service.IDS_MAX} уведомлений за раз')
    try:
        return sorted({int(i) for i in raw}), None
    except (TypeError, ValueError):
        return None, _bad('ids', 'Неверные номера уведомлений')


class Notifications(Base):
    def get(self, request):
        mode = request_mode(request)
        f, err = _filters(request.query_params)
        if err:
            return err
        cursor = None
        if request.query_params.get('cursor'):
            cursor = service.decode_cursor(request.query_params['cursor'])
            if cursor is None:
                return _bad('cursor', 'Неверный курсор')
        after = request.query_params.get('after')
        if after and not after.isdigit():
            return _bad('after', 'Неверный номер уведомления')
        data = service.page(request.user, mode, *f, cursor=cursor, after=int(after) if after else None)
        data['unread'] = service.unread_count(request.user, mode)
        return Response(data)


class Counts(Base):
    def get(self, request):
        return Response(service.counts(request.user, request_mode(request)))


class Read(Base):
    def post(self, request):
        mode = request_mode(request)
        if hasattr(request.data, 'get') and request.data.get('all') is True:
            marked = service.mark_read(request.user, mode)
        else:
            ids, err = _ids(request.data)
            if err:
                return err
            marked = service.mark_read(request.user, mode, ids)
        return Response({'marked': marked, 'unread': service.unread_count(request.user, mode)})


class Delete(Base):
    def post(self, request):
        mode = request_mode(request)
        data = request.data if hasattr(request.data, 'get') else {}
        if data.get('read') is True:
            deleted = service.delete(request.user, mode, read_only=True)
        elif data.get('all') is True:
            f, err = _filters(data)
            if err:
                return err
            deleted = service.delete(request.user, mode, None, *f)
        else:
            ids, err = _ids(data)
            if err:
                return err
            deleted = service.delete(request.user, mode, ids)
        return Response({'deleted': deleted, 'unread': service.unread_count(request.user, mode)})


class Settings(Base):
    def get(self, request):
        return Response({'options': settings.options(request.user)})

    def put(self, request):
        data = request.data if hasattr(request.data, 'items') else None
        if not data or not all(isinstance(v, bool) for v in data.values()):
            return _bad('settings', 'Ожидается {"код": true | false}')
        return Response({'options': settings.update(request.user, dict(data))})


# ── 8. api/notifications/urls.py ──────────────────────────────────────────────
# В api/urls.py (префикс /api/v1/):  path('notifications/', include('api.notifications.urls')),
from django.urls import path

from . import views

urlpatterns = [
    path('', views.Notifications.as_view(), name='notifications-list'),
    path('counts/', views.Counts.as_view(), name='notifications-counts'),
    path('read/', views.Read.as_view(), name='notifications-read'),
    path('delete/', views.Delete.as_view(), name='notifications-delete'),
    path('settings/', views.Settings.as_view(), name='notifications-settings'),
]


# ── 9. api/urls.py — подключить (префикс /api/v1/) ──────────────────────────
#     path('notifications/', include('api.notifications.urls')),


# ── 10. Страница /notifications/ ─────────────────────────────────────────────
# Вьюха (например, в blog/views.py) и урл в корневом urls.py:
#
#     from django.contrib.auth.decorators import login_required
#     from django.views.decorators.csrf import ensure_csrf_cookie
#
#     @login_required
#     @ensure_csrf_cookie
#     def notifications_page(request):
#         return render(request, 'notifications.html')
#
#     path('notifications/', notifications_page, name='notifications'),
#
# Шаблон templates/notifications.html — внутри общей вёрстки сайта (блоки — свои):
#
#     {% block content %}
#       <link rel="stylesheet" href="/assets/notifications/notifications.css?v=1">
#       <div id="alterlit-notifications" data-csrf="{{ csrf_token }}"></div>
#       <script type="module" src="/assets/notifications/notifications.js?v=1"></script>
#     {% endblock %}


# ── 11. Отключённые уведомления не создаются — blog/models.py, Notification ─────
# create_notif заменить целиком. Заодно статус пишется сразу при создании: раньше уведомление
# сохранялось дважды (create, затем save со статусом), и в сокет уходило со статусом "I".
#
#     @staticmethod
#     def create_notif(to, content, status="I", site="AL"):
#         from api.notifications.settings import is_muted
#
#         if status not in [x[0] for x in Notification.STATUSES]:
#             status = "I"
#         if is_muted(to, status, content):
#             return False
#         Notification.objects.create(to=to, content=content, status=status, site=site)
#         return True


# ── 12. Индекс для вкладок со статусом (комментарии, упоминания, финансы…) ──
# blog/models.py, Notification.Meta.indexes — добавить третий, затем makemigrations + migrate:
#
#     models.Index(fields=["to", "status", "date"], name="notif_to_status_date"),
#
# Остальные вкладки (оценки, публикации) отличаются только текстом — их ищут подстрокой
# в пределах уведомлений одного пользователя по уже имеющемуся notif_to_date.
