"""Текст уведомления для страницы: только ссылки и простое выделение, без стилей и скриптов.
Названия публикаций в старых шаблонах попадали в HTML без экранирования."""
import nh3

TAGS = {'a', 'b', 'strong', 'i', 'em', 'br', 'div', 'span', 'p'}
ATTRS = {'a': {'href'}}


def clean(html):
    return nh3.clean(html or '', tags=TAGS, attributes=ATTRS, url_schemes={'http', 'https', 'mailto'},
                     link_rel='noopener noreferrer')
