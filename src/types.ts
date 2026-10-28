/** Ответы /api/v1/notifications/ — формат описан в django/notifications/views.py */

export type Kind =
  | 'like_comment'
  | 'dislike_post'
  | 'like_post'
  | 'comment'
  | 'mention'
  | 'review'
  | 'post_status'
  | 'post_deleted'
  | 'new_post'
  | 'finance'
  | 'support'
  | 'moderation'
  | 'account'
  | 'other';

export interface Actor {
  username: string;
  name: string;
  url: string;
}

export interface Item {
  id: number;
  date: string;
  is_read: boolean;
  actor: Actor | null;
  /** текст комментария (оценка комментария, новый комментарий, упоминание) */
  excerpt: string;
  /** куда ведёт уведомление */
  url: string | null;
  /** свои у каждого уведомления группы: публикации автора, статусы одной публикации */
  target: { url: string | null; title: string } | null;
  extra: Extra;
}

export interface Extra {
  review?: { url: string; title: string };
  status?: string;
  reason?: string;
  draft?: boolean;
  /** обращение в поддержку: от кого (имя или почта) и аноним ли */
  from?: string;
  guest?: boolean;
}

/** Одно уведомление или группа: одного вида, об одном объекте, за одни сутки. */
export interface Card {
  key: string;
  kind: Kind;
  category: string;
  /** день (YYYY-MM-DD, по времени сервера) */
  day: string;
  date: string;
  site: string;
  is_read: boolean;
  target: { url: string | null; title: string } | null;
  extra: Extra;
  /** очищенный на сервере HTML исходного текста — для видов без своего оформления */
  html: string;
  /** новые сверху */
  items: Item[];
}

export interface Person {
  name: string;
  avatar: string | null;
}

export interface Page {
  cards: Card[];
  people: Record<string, Person>;
  next: string | null;
  unread: number;
}

export interface Counts {
  all: { total: number; unread: number };
  categories: { code: string; label: string; total: number; unread: number }[];
}

export interface Filters {
  category: string | null;
  unread: boolean;
  q: string;
}

/** Что можно отключить — GET/PUT /api/v1/notifications/settings/ */
export interface SettingOption {
  code: string;
  label: string;
  group: string;
  enabled: boolean;
}
