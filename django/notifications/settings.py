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
