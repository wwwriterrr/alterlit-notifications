import { useEffect, useRef, useState, type ReactNode, type SVGProps } from 'react';
import Avatar from './Avatar';
import * as Ic from './icons';
import { fullDate, plural, timeLabel } from './date';
import type { Actor, Card as CardT, Kind, Person } from './types';

/** Значок вида у аватара: иконка и цвет */
const BADGE: Record<Kind, { icon: (p: SVGProps<SVGSVGElement>) => ReactNode; cls: string; label: string }> = {
  like_comment: { icon: Ic.Heart, cls: 'like', label: 'Оценка' },
  like_post: { icon: Ic.Heart, cls: 'like', label: 'Оценка' },
  dislike_post: { icon: Ic.ThumbDown, cls: 'gray', label: 'Оценка' },
  comment: { icon: Ic.Bubble, cls: 'blue', label: 'Комментарий' },
  mention: { icon: Ic.At, cls: 'violet', label: 'Упоминание' },
  review: { icon: Ic.Book, cls: 'amber', label: 'Рецензия' },
  post_status: { icon: Ic.Doc, cls: 'green', label: 'Публикация' },
  post_deleted: { icon: Ic.Trash, cls: 'red', label: 'Удаление' },
  new_post: { icon: Ic.Pen, cls: 'green', label: 'Подписка' },
  finance: { icon: Ic.Coin, cls: 'amber', label: 'Финансы' },
  support: { icon: Ic.Lifebuoy, cls: 'blue', label: 'Поддержка' },
  moderation: { icon: Ic.Shield, cls: 'violet', label: 'Модерация' },
  account: { icon: Ic.Shield, cls: 'red', label: 'Аккаунт' },
  other: { icon: Ic.Bell, cls: 'gray', label: 'Уведомление' },
};

/** Разные авторы группы, новые первыми */
function actorsOf(card: CardT) {
  const seen = new Map<string, Actor>();
  for (const i of card.items) if (i.actor && !seen.has(i.actor.username)) seen.set(i.actor.username, i.actor);
  return [...seen.values()];
}

function Name({ a, people }: { a: Actor; people: Record<string, Person> }) {
  return (
    <a className="nt-name" href={a.url} onClick={(e) => e.stopPropagation()}>
      {people[a.username]?.name || a.name}
    </a>
  );
}

/** «Анна», «Анна и Борис», «Анна, Борис и Вера», «Анна, Борис и ещё 3 человека» */
function Names({ actors, people }: { actors: Actor[]; people: Record<string, Person> }) {
  if (!actors.length) return null;
  if (actors.length === 1) return <Name a={actors[0]} people={people} />;
  if (actors.length === 2)
    return (
      <>
        <Name a={actors[0]} people={people} /> и <Name a={actors[1]} people={people} />
      </>
    );
  if (actors.length === 3)
    return (
      <>
        <Name a={actors[0]} people={people} />, <Name a={actors[1]} people={people} /> и <Name a={actors[2]} people={people} />
      </>
    );
  const rest = actors.length - 2;
  return (
    <>
      <Name a={actors[0]} people={people} />, <Name a={actors[1]} people={people} /> и ещё {rest}{' '}
      {plural(rest, 'человек', 'человека', 'человек')}
    </>
  );
}

const Title = ({ t }: { t?: { url: string | null; title: string } | null }) =>
  t?.title ? (
    t.url ? (
      <a className="nt-title" href={t.url} onClick={(e) => e.stopPropagation()}>
        «{t.title}»
      </a>
    ) : (
      <b className="nt-title">«{t.title}»</b>
    )
  ) : null;

const statusText = (x: { status?: string }) => (x.status === 'В профиле' ? 'Опубликовано в профиле' : (x.status ?? '—'));

/** Публикации группы «новые публикации автора» — без повторов (рассылку могли прислать дважды) */
function uniquePosts(card: CardT) {
  const seen = new Map<string, { url: string | null; title: string }>();
  for (const i of card.items)
    if (i.target && !seen.has(i.target.url ?? i.target.title)) seen.set(i.target.url ?? i.target.title, i.target);
  return [...seen.values()];
}

/** Текст карточки по виду; null — показать исходный HTML уведомления. */
function phrase(card: CardT, people: Record<string, Person>): ReactNode | null {
  const actors = actorsOf(card);
  const a = actors[0];
  const n = card.items.length;
  const first = card.items[0];
  const names = <Names actors={actors} people={people} />;
  switch (card.kind) {
    case 'like_comment':
      return a ? <>Ваш комментарий понравился: {names}</> : null;
    case 'like_post':
      return a && card.target ? (
        <>
          Ваша публикация <Title t={card.target} /> понравилась: {names}
        </>
      ) : null;
    case 'dislike_post':
      return a && card.target ? (
        <>
          Ваша публикация <Title t={card.target} /> не понравилась: {names}
        </>
      ) : null;
    case 'comment':
      if (!a) return null;
      return n > 1 ? (
        <>
          {n} {plural(n, 'новый комментарий', 'новых комментария', 'новых комментариев')} к <Title t={card.target} />: {names}
        </>
      ) : (
        <>
          <Name a={a} people={people} /> прокомментировал(а) <Title t={card.target} />
        </>
      );
    case 'mention':
      return a ? (
        <>
          <Name a={a} people={people} /> упомянул(а) вас в комментарии
        </>
      ) : null;
    case 'review':
      return card.target && card.extra.review ? (
        <>
          На вашу публикацию <Title t={card.target} /> написали рецензию <Title t={card.extra.review} />
        </>
      ) : null;
    case 'post_status':
      if (!card.target) return null;
      if (n > 1)
        return (
          <>
            Публикация <Title t={card.target} /> — статус менялся {n} {plural(n, 'раз', 'раза', 'раз')}, сейчас:{' '}
            <b>{statusText(card.extra)}</b>
          </>
        );
      return card.extra.status === 'В профиле' ? (
        <>
          Ваш текст <Title t={card.target} /> опубликован в профиле
        </>
      ) : (
        <>
          Публикация <Title t={card.target} /> — новый статус: <b>{card.extra.status ?? '—'}</b>
        </>
      );
    case 'post_deleted':
      return card.target ? (
        <>
          {a ? (
            <>
              <Name a={a} people={people} /> удалил(а)
            </>
          ) : (
            'Удалён(а)'
          )}{' '}
          {card.extra.draft ? 'ваш черновик' : 'вашу публикацию'} <Title t={card.target} />
        </>
      ) : null;
    case 'support': {
      const senders = [...new Set(card.items.map((i) => i.extra.from).filter(Boolean))] as string[];
      if (!senders.length) return null;
      if (n === 1)
        return (
          <>
            Новое{' '}
            <a className="nt-title" href={first.url ?? '#'} onClick={(e) => e.stopPropagation()}>
              обращение
            </a>{' '}
            в поддержку от {first.extra.guest ? 'гостя' : 'пользователя'} <b>{first.extra.from}</b>
          </>
        );
      const shown = senders.slice(0, senders.length === 3 ? 3 : 2);
      const rest = senders.length - shown.length;
      return (
        <>
          {n} {plural(n, 'новое обращение', 'новых обращения', 'новых обращений')} в поддержку:{' '}
          {shown.map((x, i) => (
            <span key={x}>
              {i ? (i === shown.length - 1 && !rest ? ' и ' : ', ') : null}
              <b>{x}</b>
            </span>
          ))}
          {rest ? ` и ещё ${rest}` : null}
        </>
      );
    }
    case 'new_post': {
      if (!a || !card.target) return null;
      const posts = uniquePosts(card);
      if (posts.length < 2)
        return (
          <>
            <Name a={a} people={people} /> опубликовал(а) <Title t={card.target} />
          </>
        );
      const shown = posts.slice(0, posts.length === 3 ? 3 : 2);
      const rest = posts.length - shown.length;
      return (
        <>
          <Name a={a} people={people} /> опубликовал(а) {posts.length}{' '}
          {plural(posts.length, 'публикацию', 'публикации', 'публикаций')}:{' '}
          {shown.map((t, i) => (
            <span key={t.url ?? t.title}>
              {i ? (i === shown.length - 1 && !rest ? ' и ' : ', ') : null}
              <Title t={t} />
            </span>
          ))}
          {rest ? ` и ещё ${rest}` : null}
        </>
      );
    }
    default:
      return null;
  }
}

/** Список «Все…»: у новых публикаций автора — каждая публикация один раз */
function members(card: CardT) {
  if (card.kind !== 'new_post') return card.items;
  const seen = new Set<string>();
  return card.items.filter((i) => {
    const k = i.target?.url ?? i.target?.title ?? String(i.id);
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
}

function moreLabel(card: CardT) {
  const n = card.items.length;
  if (card.kind === 'comment') return `Все комментарии (${n})`;
  if (card.kind === 'post_status') return `История (${n})`;
  if (card.kind === 'support') return `Все обращения (${n})`;
  if (card.kind === 'new_post') return `Все публикации (${uniquePosts(card).length})`;
  return `Все (${n})`;
}

export interface CardProps {
  card: CardT;
  people: Record<string, Person>;
  selecting: boolean;
  selected: boolean;
  onSelect: () => void;
  onRead: (ids: number[]) => void;
  onDelete: (ids: number[]) => void;
}

export default function Card({ card, people, selecting, selected, onSelect, onRead, onDelete }: CardProps) {
  const [open, setOpen] = useState(false);
  const [menu, setMenu] = useState(false);
  const actors = actorsOf(card);
  const text = phrase(card, people);
  const badge = BADGE[card.kind] ?? BADGE.other;
  const first = card.items[0];
  const url = first.url ?? card.target?.url ?? null;
  const unreadIds = card.items.filter((i) => !i.is_read).map((i) => i.id);
  const ids = card.items.map((i) => i.id);
  const many = card.kind === 'new_post' ? uniquePosts(card).length > 1 : card.items.length > 1;
  const quote = card.kind === 'like_comment' || card.kind === 'comment' || card.kind === 'mention' ? first.excerpt : '';

  const go = () => {
    if (selecting) return onSelect();
    if (unreadIds.length) onRead(unreadIds);
    if (url) window.location.href = url;
  };

  return (
    <div
      role="article"
      className="nt-card"
      data-unread={!card.is_read || undefined}
      data-selected={selected || undefined}
      data-unread-ids={unreadIds.join(',') || undefined}
      onClick={go}
    >
      {selecting ? (
        <span className="nt-check" role="checkbox" aria-checked={selected} aria-label="Выбрать">
          {selected ? <Ic.Check width={14} height={14} /> : null}
        </span>
      ) : null}
      <div className="nt-pic">
        {actors.length ? (
          <span className={`nt-stack nt-stack-${Math.min(actors.length, 2)}`}>
            {actors.slice(0, 2).map((x) => (
              <Avatar
                key={x.username}
                username={x.username}
                name={x.name}
                person={people[x.username]}
                size={actors.length > 1 ? 32 : 44}
              />
            ))}
          </span>
        ) : (
          <span className={`nt-kind-ic nt-c-${badge.cls}`}>
            <badge.icon width={22} height={22} />
          </span>
        )}
        {actors.length ? (
          <span className={`nt-badge nt-c-${badge.cls}`} title={badge.label}>
            <badge.icon width={11} height={11} />
          </span>
        ) : null}
      </div>

      <div className="nt-body">
        {text ? (
          <p className="nt-text">{text}</p>
        ) : (
          <div className="nt-text nt-html" dangerouslySetInnerHTML={{ __html: card.html }} />
        )}
        {card.kind === 'post_status' && card.extra.reason ? <p className="nt-reason">Причина: {card.extra.reason}</p> : null}
        {quote ? <div className="nt-quote">{quote}</div> : null}
        <div className="nt-meta">
          <time dateTime={card.date} title={fullDate(card.date)}>
            {timeLabel(card.date)}
          </time>
          {many ? (
            <button
              type="button"
              className="nt-more"
              aria-expanded={open}
              onClick={(e) => {
                e.stopPropagation();
                setOpen((o) => !o);
              }}
            >
              {open ? 'Свернуть' : moreLabel(card)}
              <Ic.Chevron width={14} height={14} />
            </button>
          ) : null}
        </div>
        {open ? (
          <ul className="nt-members" onClick={(e) => e.stopPropagation()}>
            {members(card).map((i) => (
              <li key={i.id} data-unread={!i.is_read || undefined}>
                {i.actor && card.kind !== 'new_post' ? (
                  <Avatar username={i.actor.username} name={i.actor.name} person={people[i.actor.username]} size={28} />
                ) : null}
                <div>
                  {card.kind === 'post_status' ? (
                    <span>
                      <b>{statusText(i.extra)}</b>
                      {i.extra.reason ? <span className="nt-reason"> · {i.extra.reason}</span> : null}
                    </span>
                  ) : card.kind === 'support' ? (
                    <a className="nt-member-text" href={i.url ?? '#'}>
                      <b>{i.extra.from ?? 'Обращение'}</b>
                      {i.extra.guest ? ' · гость' : ''}
                    </a>
                  ) : card.kind === 'new_post' ? (
                    <Title t={i.target} />
                  ) : i.actor ? (
                    <Name a={i.actor} people={people} />
                  ) : null}
                  {card.kind === 'comment' && i.excerpt ? (
                    <a className="nt-member-text" href={i.url ?? '#'}>
                      {i.excerpt}
                    </a>
                  ) : null}
                </div>
                <time dateTime={i.date} title={fullDate(i.date)}>
                  {timeLabel(i.date)}
                </time>
              </li>
            ))}
          </ul>
        ) : null}
      </div>

      {!card.is_read ? <span className="nt-dot" aria-label="Не прочитано" /> : null}
      {!selecting ? (
        <CardMenu
          open={menu}
          setOpen={setMenu}
          items={[
            ...(unreadIds.length
              ? [{ label: 'Отметить прочитанным', icon: <Ic.Check width={16} height={16} />, run: () => onRead(unreadIds) }]
              : []),
            {
              label: many ? `Удалить (${ids.length})` : 'Удалить',
              icon: <Ic.Trash width={16} height={16} />,
              run: () => onDelete(ids),
              danger: true,
            },
          ]}
        />
      ) : null}
    </div>
  );
}

function CardMenu({
  open,
  setOpen,
  items,
}: {
  open: boolean;
  setOpen: (v: boolean) => void;
  items: { label: string; icon: ReactNode; run: () => void; danger?: boolean }[];
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: Event) => !ref.current?.contains(e.target as Node) && setOpen(false);
    const esc = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false);
    document.addEventListener('pointerdown', close);
    document.addEventListener('keydown', esc);
    return () => {
      document.removeEventListener('pointerdown', close);
      document.removeEventListener('keydown', esc);
    };
  }, [open, setOpen]);
  return (
    <div className="nt-menu-wrap" ref={ref} onClick={(e) => e.stopPropagation()}>
      <button
        type="button"
        className="nt-icon-btn nt-card-menu"
        aria-label="Действия"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        <Ic.Dots />
      </button>
      {open ? (
        <div className="nt-menu" role="menu">
          {items.map((it) => (
            <button
              key={it.label}
              type="button"
              role="menuitem"
              className={it.danger ? 'nt-danger' : undefined}
              onClick={() => {
                setOpen(false);
                it.run();
              }}
            >
              {it.icon}
              {it.label}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
