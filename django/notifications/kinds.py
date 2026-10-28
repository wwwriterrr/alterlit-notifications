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
