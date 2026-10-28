import { configureStore, createSlice, type PayloadAction } from '@reduxjs/toolkit';
import { api } from './api';

/**
 * Что изменилось на странице без перезапроса ленты: прочитанные и удалённые уведомления.
 * Прочитанное остаётся на месте (и во вкладке «непрочитанные» — до обновления), удалённое исчезает.
 */
const local = createSlice({
  name: 'local',
  initialState: { read: {} as Record<number, true>, deleted: {} as Record<number, true>, allRead: false },
  reducers: {
    markRead(s, a: PayloadAction<number[]>) {
      for (const id of a.payload) s.read[id] = true;
    },
    markAllRead(s) {
      s.allRead = true;
    },
    markDeleted(s, a: PayloadAction<number[]>) {
      for (const id of a.payload) s.deleted[id] = true;
    },
  },
});

export const localActions = local.actions;

export const store = configureStore({
  reducer: { [api.reducerPath]: api.reducer, local: local.reducer },
  middleware: (gdm) => gdm().concat(api.middleware),
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
