import { useState } from 'react';
import { CheckSquare, Eye, LayoutTemplate, Square } from 'lucide-react';
import { Button, useLoad } from './ui';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { useI18n } from '../lib/i18n';

/** The post designs of the company's field (40+): keep all, or only the ones the company likes. */
export default function TemplatePicker({ brand, value, onChange, classic, onUseTemplates }) {
  const { t, lang } = useI18n();
  const { user } = useAuth();
  const list = useLoad(() => api.get(`/api/brands/${brand.id}/templates`), [brand.id]);
  const [thumbs, setThumbs] = useState({});
  const [busy, setBusy] = useState(false);
  const [view, setView] = useState('all');
  const items = list.data || [];
  const kept = value.length ? value : items.map((i) => i.id);
  const shown = items.filter((i) => view === 'all' || (view === 'fx' ? i.finish : !i.finish));
  const toggle = (id) => {
    const next = kept.includes(id) ? kept.filter((x) => x !== id) : [...kept, id];
    if (!next.length) return;
    onChange(next.length === items.length ? [] : next);
  };
  const keepOnly = (ids) => { if (ids.length) onChange(ids.length === items.length ? [] : ids); };
  const loadThumbs = async () => {
    setBusy(true);
    const language = user?.org?.language || 'ar';
    const queue = shown.filter((i) => !thumbs[i.id]);
    const worker = async () => {
      while (queue.length) {
        const it = queue.shift();
        try {
          const r = await api.post(`/api/brands/${brand.id}/preview`, { kind: 'cover', variant: 0, template: it.id, language });
          setThumbs((x) => ({ ...x, [it.id]: r.image }));
        } catch { /* skip */ }
      }
    };
    await Promise.all([worker(), worker(), worker()]);
    setBusy(false);
  };
  return (
    <div className="card card-pad stack">
      <div className="field-head">
        <h3 style={{ margin: 0 }}><LayoutTemplate size={16} /> {t('templates_title')}</h3>
        <Button size="sm" icon={Eye} busy={busy} disabled={!shown.length} onClick={loadThumbs}>{t('templates_preview')}</Button>
      </div>
      <p className="xs muted" style={{ marginTop: -8 }}>{t('templates_hint')} — <b>{kept.length}/{items.length}</b></p>
      {classic && (
        <div className="banner warn small" style={{ margin: 0 }}>
          {t('templates_classic_warn')}{' '}
          <Button size="sm" variant="primary" onClick={onUseTemplates}>{t('templates_use')}</Button>
        </div>
      )}
      <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
        <div className="seg" role="tablist">
          {['all', 'base', 'fx'].map((v) => (
            <button key={v} type="button" className={`seg-item ${view === v ? 'on' : ''}`} onClick={() => setView(v)}>
              {t(`templates_view_${v}`)} ({items.filter((i) => v === 'all' || (v === 'fx' ? i.finish : !i.finish)).length})
            </button>
          ))}
        </div>
        <span className="spacer" />
        <Button size="sm" icon={CheckSquare} onClick={() => onChange([])}>{t('select_all')}</Button>
        <Button size="sm" onClick={() => keepOnly(items.filter((i) => !i.finish).map((i) => i.id))}>{t('templates_only_base')}</Button>
        <Button size="sm" onClick={() => keepOnly(items.filter((i) => i.finish).map((i) => i.id))}>{t('templates_only_fx')}</Button>
      </div>
      <div className="tpl-grid">
        {shown.map((it) => {
          const on = kept.includes(it.id);
          return (
            <button type="button" key={it.id} className={`tpl-item ${on ? 'on' : ''}`} aria-pressed={on} onClick={() => toggle(it.id)}>
              <div className="tpl-thumb">{thumbs[it.id] ? <img src={thumbs[it.id]} alt="" /> : <LayoutTemplate size={22} />}</div>
              <span>{on ? <CheckSquare size={14} /> : <Square size={14} />} {it[lang] || it.en}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
