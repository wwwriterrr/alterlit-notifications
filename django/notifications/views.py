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
