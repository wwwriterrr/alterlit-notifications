import { useState } from 'react';
import type { Person } from './types';

const COLORS = ['#c9734f', '#4f8a6b', '#5a7bb5', '#b0638f', '#c79a3c', '#6f6bb3', '#3f8f9a', '#9a6b4f'];

function color(seed: string) {
  let h = 0;
  for (const ch of seed) h = (h * 31 + ch.charCodeAt(0)) | 0;
  return COLORS[Math.abs(h) % COLORS.length];
}

/** Аватар автора: инициал на цветном фоне, поверх — фото, когда загрузится. */
export default function Avatar({ username, name, person, size = 44 }: { username: string; name: string; person?: Person; size?: number }) {
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(false);
  const shown = person?.name || name || username;
  const src = person?.avatar && !failed ? person.avatar : null;
  return (
    <span className="nt-ava" style={{ width: size, height: size, background: color(username), fontSize: size * 0.42 }} aria-hidden="true">
      {loaded ? null : (shown.trim()[0] ?? '?').toUpperCase()}
      {src ? (
        <img src={src} alt="" loading="lazy" onLoad={() => setLoaded(true)} onError={() => setFailed(true)} data-loaded={loaded || undefined} />
      ) : null}
    </span>
  );
}
