import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';
import type { Counts, Filters, Page, SettingOption } from './types';

let csrfFallback = '';
/** Токен, если куки csrftoken нет: <div id="alterlit-notifications" data-csrf="{{ csrf_token }}"> */
export function setCsrfFallback(token: string) {
  csrfFallback = token;
}
function csrfToken() {
  const m = document.cookie.match(/(?:^|; )csrftoken=([^;]*)/);
  return m ? decodeURIComponent(m[1]) : csrfFallback;
}

export function errorText(err: unknown): string {
  const e = err as { status?: unknown; data?: { detail?: unknown } };
  if (typeof e?.data?.detail === 'string') return e.data.detail;
  if (e?.status === 'FETCH_ERROR') return 'Нет связи с сервером. Проверьте интернет и попробуйте ещё раз.';
  if (e?.status === 401 || e?.status === 403) return 'Сессия истекла — войдите на сайт ещё раз.';
  return 'Возникла ошибка на сервере. Попробуйте позже.';
}

const params = (f: Filters) => ({
  ...(f.category ? { category: f.category } : {}),
  ...(f.unread ? { unread: 1 } : {}),
  ...(f.q ? { q: f.q } : {}),
});

export type DeleteBody =
  { ids: number[] } | ({ all: true } & Partial<{ category: string; unread: boolean; q: string }>) | { read: true };

export const api = createApi({
  reducerPath: 'api',
  baseQuery: fetchBaseQuery({
    baseUrl: '/api/v1/notifications/',
    credentials: 'same-origin',
    prepareHeaders: (h) => {
      h.set('X-CSRFToken', csrfToken());
      return h;
    },
  }),
  tagTypes: ['List', 'Counts', 'Settings'],
  endpoints: (b) => ({
    list: b.infiniteQuery<Page, Filters, string | null>({
      infiniteQueryOptions: {
        initialPageParam: null,
        getNextPageParam: (last) => last.next,
      },
      query: ({ queryArg, pageParam }) => ({
        url: '',
        params: { ...params(queryArg), ...(pageParam ? { cursor: pageParam } : {}) },
      }),
      providesTags: ['List'],
    }),
    /** Пришедшие после уведомления after — с теми же фильтрами, уже разобранные и сгруппированные */
    fresh: b.query<Page, Filters & { after: number }>({
      query: ({ after, ...f }) => ({ url: '', params: { ...params(f), after } }),
      keepUnusedDataFor: 0,
    }),
    counts: b.query<Counts, void>({ query: () => 'counts/', providesTags: ['Counts'] }),
    read: b.mutation<{ marked: number; unread: number }, { ids: number[] } | { all: true }>({
      query: (body) => ({ url: 'read/', method: 'POST', body }),
      invalidatesTags: ['Counts'],
    }),
    remove: b.mutation<{ deleted: number; unread: number }, DeleteBody>({
      query: (body) => ({ url: 'delete/', method: 'POST', body }),
      // удаление по выбору: карточки прячутся сразу (store.local), список не перезапрашиваем;
      // «удалить всё во вкладке» — перезапрашиваем
      invalidatesTags: (_r, _e, body) => ('ids' in body ? ['Counts'] : ['Counts', 'List']),
    }),
    settings: b.query<{ options: SettingOption[] }, void>({ query: () => 'settings/', providesTags: ['Settings'] }),
    saveSettings: b.mutation<{ options: SettingOption[] }, Record<string, boolean>>({
      query: (body) => ({ url: 'settings/', method: 'PUT', body }),
      // переключатель меняется сразу; не сохранилось — вернётся как был
      async onQueryStarted(changes, { dispatch, queryFulfilled }) {
        const patch = dispatch(
          api.util.updateQueryData('settings', undefined, (d) => {
            for (const o of d.options) if (o.code in changes) o.enabled = changes[o.code];
          }),
        );
        try {
          const { data } = await queryFulfilled;
          dispatch(api.util.updateQueryData('settings', undefined, () => data));
        } catch {
          patch.undo();
        }
      },
    }),
  }),
});

export const {
  useListInfiniteQuery,
  useLazyFreshQuery,
  useCountsQuery,
  useReadMutation,
  useRemoveMutation,
  useSettingsQuery,
  useSaveSettingsMutation,
} = api;
