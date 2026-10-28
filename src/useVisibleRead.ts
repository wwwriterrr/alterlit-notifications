import { useEffect, useRef } from 'react';

/**
 * Прочитано то, что пользователь увидел: карточка с непрочитанным больше чем наполовину на экране
 * дольше секунды. id копятся и уходят одним запросом раз в ~1,5 с.
 */
export function useVisibleRead(root: HTMLElement | null, onRead: (ids: number[]) => void, enabled: boolean) {
  const cb = useRef(onRead);
  cb.current = onRead;

  useEffect(() => {
    if (!root || !enabled || typeof IntersectionObserver === 'undefined') return;
    const timers = new Map<Element, number>();
    const queue = new Set<number>();
    let flush: number | null = null;

    const send = () => {
      flush = null;
      if (document.visibilityState !== 'visible' || !queue.size) return;
      cb.current([...queue]);
      queue.clear();
    };
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            if (timers.has(e.target)) continue;
            timers.set(
              e.target,
              window.setTimeout(() => {
                const ids = (e.target as HTMLElement).dataset.unreadIds;
                ids?.split(',').forEach((x) => queue.add(Number(x)));
                if (flush == null) flush = window.setTimeout(send, 1500);
              }, 1000),
            );
          } else {
            clearTimeout(timers.get(e.target));
            timers.delete(e.target);
          }
        }
      },
      { threshold: 0.5 },
    );
    const watch = () => root.querySelectorAll('[data-unread-ids]').forEach((el) => io.observe(el));
    watch();
    // новые карточки (подгрузка страниц) — тоже под наблюдение; observe() того же элемента ничего не делает
    const mo = new MutationObserver(watch);
    mo.observe(root, { subtree: true, childList: true });
    return () => {
      io.disconnect();
      mo.disconnect();
      timers.forEach((t) => clearTimeout(t));
      if (flush != null) clearTimeout(flush);
      send();
    };
  }, [root, enabled]);
}
