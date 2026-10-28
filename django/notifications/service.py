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
