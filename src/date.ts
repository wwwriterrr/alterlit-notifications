const MONTHS = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];

const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

/** Заголовок дня ленты: «Сегодня», «Вчера», «12 октября», «12 октября 2025». */
export function dayTitle(day: string, now = new Date()) {
  if (day === iso(now)) return 'Сегодня';
  const y = new Date(now);
  y.setDate(now.getDate() - 1);
  if (day === iso(y)) return 'Вчера';
  const [yy, mm, dd] = day.split('-').map(Number);
  return `${dd} ${MONTHS[mm - 1]}${yy === now.getFullYear() ? '' : ` ${yy}`}`;
}

/** Время у карточки: «только что», «5 мин», дальше — часы и минуты (день — в заголовке). */
export function timeLabel(date: string, now = Date.now()) {
  const d = new Date(date);
  const min = Math.floor((now - d.getTime()) / 60000);
  if (min < 1) return 'только что';
  if (min < 60) return `${min} мин`;
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

export function fullDate(date: string) {
  const d = new Date(date);
  return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}, ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

/** 1 оценка, 2 оценки, 5 оценок */
export function plural(n: number, one: string, few: string, many: string) {
  const m10 = n % 10;
  const m100 = n % 100;
  if (m10 === 1 && m100 !== 11) return one;
  if (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) return few;
  return many;
}
