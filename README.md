# Уведомления — остров страницы /notifications/

React + TS + Vite + RTK Query. Монтируется в `#alterlit-notifications` (data-csrf), статика —
`/assets/notifications/notifications.js|css` (постоянные имена, в шаблоне — с `?v=`).
Выкладка: `../deploy.sh notifications`.

## Бэк

`django/notifications_patch.py` — сборка модулей `django/notifications/` (`python3 -I tools/build_patch.py`):
пакет `api/notifications/` + страница, шаблон и индекс (в конце файла). Формат ручек — в начале `views.py`.

- `kinds.py` — **единственное место**, где описаны шаблоны текстов уведомлений: вид, вкладка,
  фильтр в базе и разбор (кто, о чём, текст комментария). У модели тип почти не записан —
  лайки, рецензии, модерация лежат под `status='I'`, различаются только текстом.
- `group.py` — карточки: одного вида, об одном объекте, за одни сутки → одна карточка.
  Группа, разрезанная границей страниц, склеивается на фронте по `key`.
- Проверка разбора на настоящих шаблонах: `npm run check`.

## Разработка

`.env.local`:
- `DEV_FIXTURES=1` — заглушки: `npm run fixtures` (порт 5186, тот же kinds.py и group.py) и `npm run dev` (5185);
- без него — прод через прокси: `BACKEND_URL`, `DEV_COOKIE` (строка Cookie); запись — только с `DEV_ALLOW_WRITE=1`.

Прочитанным считается то, что больше секунды было на экране (`useVisibleRead.ts`).
Новые уведомления: лента обновляется по событию окна `alterlit:notification` (юзербар — позже)
и при возвращении на вкладку через минуту.
