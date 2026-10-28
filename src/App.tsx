import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { errorText, useCountsQuery, useLazyFreshQuery, useListInfiniteQuery, useReadMutation, useRemoveMutation } from './api';
import { useAppDispatch, useAppSelector } from './hooks';
import { localActions } from './store';
import { useVisibleRead } from './useVisibleRead';
import Card from './Card';
import Confirm from './Confirm';
import Settings from './Settings';
import * as Ic from './icons';
import { dayTitle, plural } from './date';
import type { Card as CardT, Filters, Page, Person } from './types';

const Q_MIN = 2;

/** Фильтры живут в адресе: /notifications/?tab=likes&unread=1&q=… — переживают перезагрузку. */
function readUrl(): Filters {
  const p = new URLSearchParams(window.location.search);
  return { category: p.get('tab'), unread: p.get('unread') === '1', q: p.get('q') ?? '' };
}
function writeUrl(f: Filters) {
  const p = new URLSearchParams(window.location.search);
  for (const [k, v] of [
    ['tab', f.category],
    ['unread', f.unread ? '1' : null],
    ['q', f.q || null],
  ] as const) {
    if (v) p.set(k, v);
    else p.delete(k);
  }
  const s = p.toString();
  window.history.replaceState(window.history.state, '', window.location.pathname + (s ? `?${s}` : '') + window.location.hash);
}

export default function App() {
  const d = useAppDispatch();
  const local = useAppSelector((s) => s.local);
  const [filters, setFilters] = useState<Filters>(readUrl);
  const [query, setQuery] = useState(filters.q);
  const [selecting, setSelecting] = useState(false);
  // /notifications/#settings — сразу открыть настройки (ссылка из других мест сайта)
  const [settings, setSettings] = useState(() => window.location.hash === '#settings');
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [confirm, setConfirm] = useState<{ title: string; text: string; ok: string; run: () => Promise<unknown> } | null>(null);
  const [toast, setToast] = useState<{ text: string; error?: boolean } | null>(null);
  const [feedEl, setFeedEl] = useState<HTMLDivElement | null>(null);
  const tabsRef = useRef<HTMLDivElement>(null);
  const tabsScrolled = useRef(false);

  // пришедшие на странице (событие alterlit:notification от юзербара) — сверху ленты
  const [fresh, setFresh] = useState<Page[]>([]);
  const [loadFresh] = useLazyFreshQuery();
  const counts = useCountsQuery();
  const list = useListInfiniteQuery(filters);
  const [read] = useReadMutation();
  const [remove, removeState] = useRemoveMutation();

  // поиск — с паузой, от двух знаков
  useEffect(() => {
    const t = window.setTimeout(() => {
      const q = query.trim();
      const next = q.length >= Q_MIN ? q : '';
      setFilters((f) => (f.q === next ? f : { ...f, q: next }));
    }, 350);
    return () => clearTimeout(t);
  }, [query]);
  useEffect(() => writeUrl(filters), [filters]);
  useEffect(() => {
    setSelected(new Set());
    setFresh([]);
  }, [filters]);

  useEffect(() => {
    if (!toast) return;
    const t = window.setTimeout(() => setToast(null), toast.error ? 6000 : 3000);
    return () => clearTimeout(t);
  }, [toast]);

  // вернулись на вкладку через минуту и больше — свежие уведомления сверху
  const { refetch } = list;
  const refetchCounts = counts.refetch;
  useEffect(() => {
    let hiddenAt = 0;
    const onVis = () => {
      if (document.visibilityState === 'hidden') hiddenAt = Date.now();
      else if (hiddenAt && Date.now() - hiddenAt > 60_000) {
        setFresh([]);
        refetch();
        refetchCounts();
      }
    };
    document.addEventListener('visibilitychange', onVis);
    return () => document.removeEventListener('visibilitychange', onVis);
  }, [refetch, refetchCounts]);

  // страницы → карточки; группа, разрезанная границей страниц, склеивается обратно по key
  const { cards, people } = useMemo(() => {
    const byKey = new Map<string, CardT>();
    const order: string[] = [];
    const people: Record<string, Person> = {};
    const seen = new Set<number>();
    for (const page of [...fresh, ...(list.data?.pages ?? [])]) {
      Object.assign(people, page.people);
      for (const card of page.cards) {
        // одно уведомление могло прийти и живьём, и при обновлении ленты
        const items = card.items.filter((i) => !seen.has(i.id));
        items.forEach((i) => seen.add(i.id));
        if (!items.length) continue;
        const c = { ...card, items };
        const prev = byKey.get(c.key);
        if (prev) byKey.set(c.key, { ...prev, items: [...prev.items, ...c.items] });
        else {
          byKey.set(c.key, c);
          order.push(c.key);
        }
      }
    }
    const cards: CardT[] = [];
    for (const k of order) {
      const c = byKey.get(k)!;
      const items = c.items
        .filter((i) => !local.deleted[i.id])
        .map((i) => (local.allRead || local.read[i.id] ? { ...i, is_read: true } : i));
      if (items.length) cards.push({ ...c, items, date: items[0].date, is_read: items.every((i) => i.is_read) });
    }
    return { cards, people };
  }, [list.data, fresh, local]);

  // новое уведомление (юзербар пересылает событие сокета): дозапросить пришедшие после
  // последнего показанного — сервер разберёт и сгруппирует их, как всю ленту
  const newestId = useMemo(() => cards.reduce((m, c) => Math.max(m, ...c.items.map((i) => i.id)), 0), [cards]);
  const newest = useRef(0);
  newest.current = newestId;
  useEffect(() => {
    let timer: number | undefined;
    const pull = async () => {
      try {
        const page = await loadFresh({ ...filters, after: newest.current }).unwrap();
        if (page.cards.length) setFresh((f) => [page, ...f]);
      } catch {
        /* не вышло — появится при следующем обновлении ленты */
      }
      refetchCounts();
    };
    // несколько уведомлений подряд (рассылка) — один запрос
    const onNew = () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(pull, 600);
    };
    window.addEventListener('alterlit:notification', onNew);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener('alterlit:notification', onNew);
    };
  }, [filters, loadFresh, refetchCounts]);

  const days = useMemo(() => {
    const out: { day: string; cards: CardT[] }[] = [];
    for (const c of cards) {
      const last = out[out.length - 1];
      if (last?.day === c.day) last.cards.push(c);
      else out.push({ day: c.day, cards: [c] });
    }
    return out;
  }, [cards]);

  const doRead = useCallback(
    (ids: number[]) => {
      if (!ids.length) return;
      d(localActions.markRead(ids));
      read({ ids })
        .unwrap()
        .catch(() => undefined);
    },
    [d, read],
  );
  useVisibleRead(feedEl, doRead, !selecting);

  const doDelete = async (ids: number[], quiet = false) => {
    try {
      const r = await remove({ ids }).unwrap();
      d(localActions.markDeleted(ids));
      if (!quiet) setToast({ text: `Удалено: ${r.deleted}` });
    } catch (e) {
      setToast({ text: errorText(e), error: true });
    }
  };

  const readAll = async () => {
    try {
      await read({ all: true }).unwrap();
      d(localActions.markAllRead());
    } catch (e) {
      setToast({ text: errorText(e), error: true });
    }
  };

  // подгрузка при прокрутке
  const sentinel = useRef<HTMLDivElement>(null);
  const { hasNextPage, isFetchingNextPage, fetchNextPage } = list;
  useEffect(() => {
    const el = sentinel.current;
    if (!el || !hasNextPage) return;
    const io = new IntersectionObserver((e) => e[0].isIntersecting && !isFetchingNextPage && fetchNextPage(), {
      rootMargin: '600px 0px',
    });
    io.observe(el);
    return () => io.disconnect();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  // выбранная вкладка — в поле зрения (на узком экране ряд прокручивается)
  useEffect(() => {
    const el = tabsRef.current?.querySelector<HTMLElement>('[aria-pressed="true"]');
    const row = tabsRef.current;
    if (!el || !row) return;
    row.scrollTo({
      left: el.offsetLeft - row.clientWidth / 2 + el.clientWidth / 2,
      behavior: tabsScrolled.current ? 'smooth' : 'instant',
    });
    tabsScrolled.current = true;
  }, [filters.category, counts.data]);

  const cats = counts.data?.categories.filter((c) => c.total > 0 || c.code === filters.category) ?? [];
  const tabLabel = filters.category
    ? (counts.data?.categories.find((c) => c.code === filters.category)?.label ?? 'вкладке')
    : null;
  const unread = counts.data?.all.unread ?? list.data?.pages[0]?.unread ?? 0;
  const readCount = counts.data ? counts.data.all.total - counts.data.all.unread : 0;
  const selIds = cards.filter((c) => selected.has(c.key)).flatMap((c) => c.items.map((i) => i.id));
  const searching = Boolean(filters.q);

  const setTab = (category: string | null) => setFilters((f) => ({ ...f, category }));
  const toggle = (key: string) =>
    setSelected((s) => {
      const n = new Set(s);
      if (n.has(key)) n.delete(key);
      else n.add(key);
      return n;
    });

  const deleteAllText = [
    searching ? `найденные по запросу «${filters.q}»` : null,
    filters.unread ? 'непрочитанные' : null,
    tabLabel ? `во вкладке «${tabLabel}»` : null,
  ]
    .filter(Boolean)
    .join(', ');

  return (
    <div className="nt-app">
      <div className="nt-head">
        <div className="nt-head-row">
          <div className="nt-h1" role="heading" aria-level={1}>
            Уведомления
            {unread > 0 ? <span className="nt-count">{unread > 99 ? '99+' : unread}</span> : null}
          </div>
          <div className="nt-head-actions">
            {unread > 0 ? (
              <button type="button" className="nt-btn nt-btn-ghost" onClick={readAll}>
                <Ic.CheckAll width={18} height={18} />
                <span className="nt-hide-xs">Прочитать все</span>
              </button>
            ) : null}
            {readCount > 0 ? (
              <button
                type="button"
                className="nt-btn nt-btn-ghost"
                title="Удалить все прочитанные"
                onClick={() =>
                  setConfirm({
                    title: 'Удалить все прочитанные?',
                    text: `Будут удалены все прочитанные уведомления — ${readCount} ${plural(readCount, 'уведомление', 'уведомления', 'уведомлений')}, во всех вкладках, а не только на этой странице. Восстановить их будет нельзя. Непрочитанные останутся.`,
                    ok: 'Удалить прочитанные',
                    run: async () => {
                      try {
                        const r = await remove({ read: true }).unwrap();
                        setFresh([]);
                        setToast({ text: `Удалено: ${r.deleted}` });
                      } catch (e) {
                        setToast({ text: errorText(e), error: true });
                      }
                    },
                  })
                }
              >
                <Ic.Trash width={18} height={18} />
                <span className="nt-hide-xs">Удалить прочитанные</span>
              </button>
            ) : null}
            <button
              type="button"
              className="nt-icon-btn nt-gear"
              aria-label="Настройки уведомлений"
              title="Настройки уведомлений"
              onClick={() => setSettings(true)}
            >
              <Ic.Gear width={20} height={20} />
            </button>
            <button
              type="button"
              className="nt-btn nt-btn-ghost"
              aria-pressed={selecting}
              onClick={() => {
                setSelecting((v) => !v);
                setSelected(new Set());
              }}
            >
              {selecting ? 'Готово' : 'Выбрать'}
            </button>
          </div>
        </div>

        <div className="nt-search-row">
          <label className="nt-search">
            <Ic.Search width={18} height={18} />
            <input
              type="search"
              value={query}
              placeholder="Поиск по уведомлениям"
              aria-label="Поиск по уведомлениям"
              maxLength={100}
              onChange={(e) => setQuery(e.target.value)}
            />
            {query ? (
              <button type="button" className="nt-icon-btn" aria-label="Очистить поиск" onClick={() => setQuery('')}>
                <Ic.Close width={16} height={16} />
              </button>
            ) : null}
          </label>
          <button
            type="button"
            className="nt-tab nt-tab-toggle"
            aria-pressed={filters.unread}
            onClick={() => setFilters((f) => ({ ...f, unread: !f.unread }))}
          >
            <span className="nt-hide-xs">Непрочитанные</span>
            <span className="nt-show-xs">Новые</span>
          </button>
        </div>

        <div className="nt-tabs" role="navigation" aria-label="Виды уведомлений" ref={tabsRef}>
          <button type="button" className="nt-tab" aria-pressed={!filters.category} onClick={() => setTab(null)}>
            Все
          </button>
          {cats.map((c) => (
            <button
              key={c.code}
              type="button"
              className="nt-tab"
              aria-pressed={filters.category === c.code}
              onClick={() => setTab(c.code)}
            >
              {c.label}
              {c.unread ? <span className="nt-tab-badge">{c.unread > 99 ? '99+' : c.unread}</span> : null}
            </button>
          ))}
        </div>
      </div>

      <div className="nt-feed" ref={setFeedEl} aria-busy={list.isFetching || undefined}>
        {list.isLoading ? (
          <Skeleton />
        ) : list.isError ? (
          <div className="nt-empty">
            <p>{errorText(list.error)}</p>
            <button type="button" className="nt-btn" onClick={() => refetch()}>
              Повторить
            </button>
          </div>
        ) : !cards.length ? (
          <div className="nt-empty">
            <span className="nt-empty-ic">
              <Ic.Bell width={28} height={28} />
            </span>
            <p>
              {searching
                ? `По запросу «${filters.q}» ничего не нашлось`
                : filters.unread
                  ? 'Непрочитанных уведомлений нет'
                  : filters.category
                    ? 'Здесь пока пусто'
                    : 'Уведомлений пока нет'}
            </p>
            {searching || filters.unread || filters.category ? (
              <button
                type="button"
                className="nt-btn"
                onClick={() => {
                  setQuery('');
                  setFilters({ category: null, unread: false, q: '' });
                }}
              >
                Показать все уведомления
              </button>
            ) : null}
          </div>
        ) : (
          <>
            {days.map((g) => (
              <div key={g.day} className="nt-day" role="group" aria-label={dayTitle(g.day)}>
                <div className="nt-day-title" role="heading" aria-level={2}>
                  {dayTitle(g.day)}
                </div>
                {g.cards.map((c) => (
                  <Card
                    key={c.key}
                    card={c}
                    people={people}
                    selecting={selecting}
                    selected={selected.has(c.key)}
                    onSelect={() => toggle(c.key)}
                    onRead={doRead}
                    onDelete={(ids) => doDelete(ids)}
                  />
                ))}
              </div>
            ))}
            <div ref={sentinel} className="nt-sentinel">
              {isFetchingNextPage ? (
                <span className="nt-spinner" aria-label="Загружаем" />
              ) : hasNextPage ? (
                <button type="button" className="nt-btn nt-btn-ghost" onClick={() => fetchNextPage()}>
                  Показать ещё
                </button>
              ) : cards.length > 8 ? (
                <span className="nt-end">Это все уведомления</span>
              ) : null}
            </div>
          </>
        )}
      </div>

      {selecting ? (
        <div className="nt-selbar" role="toolbar" aria-label="Выбранные уведомления">
          <span className="nt-selbar-count">
            {selected.size
              ? `Выбрано: ${selIds.length} ${plural(selIds.length, 'уведомление', 'уведомления', 'уведомлений')}`
              : 'Выберите уведомления'}
          </span>
          <button
            type="button"
            className="nt-btn nt-btn-ghost"
            onClick={() => setSelected(selected.size === cards.length ? new Set() : new Set(cards.map((c) => c.key)))}
          >
            {selected.size === cards.length && cards.length ? 'Снять выбор' : 'Выбрать загруженные'}
          </button>
          <button
            type="button"
            className="nt-btn"
            disabled={!selIds.length}
            onClick={() => {
              doRead(selIds);
              setSelected(new Set());
            }}
          >
            Прочитать
          </button>
          <button
            type="button"
            className="nt-btn nt-btn-danger"
            disabled={!selIds.length}
            onClick={() =>
              setConfirm({
                title: 'Удалить выбранные?',
                text: `${selIds.length} ${plural(selIds.length, 'уведомление будет удалено', 'уведомления будут удалены', 'уведомлений будут удалены')} без возможности восстановить.`,
                ok: 'Удалить',
                run: async () => {
                  await doDelete(selIds);
                  setSelected(new Set());
                },
              })
            }
          >
            Удалить
          </button>
          <span className="nt-selbar-gap" />
          <button
            type="button"
            className="nt-btn nt-btn-ghost nt-danger-text"
            onClick={() =>
              setConfirm({
                title: deleteAllText ? 'Удалить все уведомления этого списка?' : 'Удалить все уведомления?',
                text: `Будут удалены все уведомления${deleteAllText ? ` — ${deleteAllText}` : ''}, а не только загруженные на странице. Восстановить их нельзя.`,
                ok: 'Удалить все',
                run: async () => {
                  try {
                    const r = await remove({
                      all: true,
                      ...(filters.category ? { category: filters.category } : {}),
                      ...(filters.unread ? { unread: true } : {}),
                      ...(filters.q ? { q: filters.q } : {}),
                    }).unwrap();
                    setToast({ text: `Удалено: ${r.deleted}` });
                    setSelecting(false);
                  } catch (e) {
                    setToast({ text: errorText(e), error: true });
                  }
                },
              })
            }
          >
            Удалить все{deleteAllText ? ' в списке' : ''}
          </button>
        </div>
      ) : null}

      {confirm ? (
        <Confirm
          title={confirm.title}
          text={confirm.text}
          confirm={confirm.ok}
          busy={removeState.isLoading}
          onClose={() => setConfirm(null)}
          onConfirm={async () => {
            await confirm.run();
            setConfirm(null);
          }}
        />
      ) : null}

      {settings ? <Settings onClose={() => setSettings(false)} onError={(text) => setToast({ text, error: true })} /> : null}

      {toast ? (
        <div className="nt-toast" data-error={toast.error || undefined} role={toast.error ? 'alert' : 'status'}>
          {toast.text}
        </div>
      ) : null}
    </div>
  );
}

function Skeleton() {
  return (
    <div className="nt-day" aria-hidden="true">
      <div className="nt-skel nt-skel-day" />
      {[0, 1, 2, 3, 4, 5].map((i) => (
        <div key={i} className="nt-card nt-card-skel">
          <span className="nt-skel nt-skel-ava" />
          <div className="nt-body">
            <div className="nt-skel nt-skel-line" />
            <div className="nt-skel nt-skel-line nt-skel-short" />
          </div>
        </div>
      ))}
    </div>
  );
}
