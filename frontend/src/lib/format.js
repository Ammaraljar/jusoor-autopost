export function toDate(v) {
  if (!v) return null;
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function fmtDate(v, lang = 'ar', opts = { day: 'numeric', month: 'long', year: 'numeric' }) {
  const d = toDate(v);
  if (!d) return '—';
  return new Intl.DateTimeFormat(lang === 'ar' ? 'ar-u-nu-latn' : lang, opts).format(d);
}

export function fmtDateTime(v, lang = 'ar') {
  return fmtDate(v, lang, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
}

export function relative(v, lang = 'ar') {
  const d = toDate(v);
  if (!d) return '—';
  const diff = (d.getTime() - Date.now()) / 1000;
  const rtf = new Intl.RelativeTimeFormat(lang === 'ar' ? 'ar' : lang, { numeric: 'auto' });
  const abs = Math.abs(diff);
  if (abs < 60) return rtf.format(Math.round(diff), 'second');
  if (abs < 3600) return rtf.format(Math.round(diff / 60), 'minute');
  if (abs < 86400) return rtf.format(Math.round(diff / 3600), 'hour');
  return rtf.format(Math.round(diff / 86400), 'day');
}

/** ISO date (YYYY-MM-DD) in local time. */
export function isoDay(d) {
  const z = new Date(d.getTime() - d.getTimezoneOffset() * 60000);
  return z.toISOString().slice(0, 10);
}

export function dayBucket(v) {
  const d = toDate(v);
  if (!d) return 'older';
  const start = new Date();
  start.setHours(0, 0, 0, 0);
  const diffDays = Math.floor((start - new Date(d).setHours(0, 0, 0, 0)) / 86400000);
  if (diffDays <= 0) return 'today';
  if (diffDays === 1) return 'yesterday';
  if (diffDays < 7) return 'week';
  return 'older';
}

/** Value for <input type="datetime-local"> */
export function toLocalInput(d) {
  const z = new Date(d.getTime() - d.getTimezoneOffset() * 60000);
  return z.toISOString().slice(0, 16);
}
