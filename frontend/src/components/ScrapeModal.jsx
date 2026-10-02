import { useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { Button, Field, Modal, useAction } from './ui';
import { api } from '../lib/api';
import { isoDay } from '../lib/format';
import { useI18n } from '../lib/i18n';

const daysAgo = (n) => { const d = new Date(); d.setDate(d.getDate() - n); return isoDay(d); };

/** Fetch news now — optionally only what was published in a chosen period. */
export default function ScrapeModal({ source, onClose, onStarted }) {
  const { t } = useI18n();
  const [preset, setPreset] = useState('new');
  const [from, setFrom] = useState(daysAgo(7));
  const [to, setTo] = useState(isoDay(new Date()));
  const [maxItems, setMaxItems] = useState(10);
  const [purpose, setPurpose] = useState('');
  const [busy, run] = useAction();

  const presets = { today: 0, d3: 3, week: 7, month: 30 };
  const choose = (p) => {
    setPreset(p);
    if (presets[p] !== undefined) { setFrom(daysAgo(presets[p])); setTo(isoDay(new Date())); }
  };

  const start = () => run('go', async () => {
    const body = preset === 'new' ? {} : { date_from: from, date_to: to, max_items: Number(maxItems) };
    if (!source && purpose) body.purpose = purpose;
    await api.post(source ? `/api/sources/${source.id}/scrape` : '/api/scrape/run-all', body);
    onStarted?.();
    onClose();
  }, t('started'));

  return (
    <Modal title={source ? `${t('scrape_now')} — ${source.name}` : t('run_scrape')} onClose={onClose} footer={<>
      <Button onClick={onClose}>{t('cancel')}</Button>
      <Button variant="primary" icon={RefreshCw} busy={busy === 'go'} disabled={preset !== 'new' && from > to} onClick={start}>
        {t('start_scrape')}
      </Button>
    </>}>
      <div className="stack">
        <Field label={t('scrape_period')}>
          <div className="tabs" style={{ flexWrap: 'wrap' }}>
            {['new', 'today', 'd3', 'week', 'month', 'custom'].map((p) => (
              <button key={p} type="button" className={`tab ${preset === p ? 'active' : ''}`} onClick={() => choose(p)}>
                {t(`period_${p}`)}
              </button>
            ))}
          </div>
        </Field>
        {preset !== 'new' && (
          <>
            <div className="grid grid-2">
              <Field label={t('date_from')}>
                <input className="input ltr" type="date" value={from} max={to} onChange={(e) => { setFrom(e.target.value); setPreset('custom'); }} />
              </Field>
              <Field label={t('date_to')}>
                <input className="input ltr" type="date" value={to} min={from} onChange={(e) => { setTo(e.target.value); setPreset('custom'); }} />
              </Field>
            </div>
            <Field label={t('max_per_source')}>
              <input className="input" type="number" min={1} max={50} value={maxItems} onChange={(e) => setMaxItems(e.target.value)} />
            </Field>
            <p className="xs muted" style={{ margin: 0 }}>{t('period_note')}</p>
          </>
        )}
        {!source && (
          <Field label={t('source_purpose')}>
            <select className="select" value={purpose} onChange={(e) => setPurpose(e.target.value)}>
              <option value="">{t('all_sources')}</option>
              <option value="news">{t('purpose_news')}</option>
              <option value="programs">{t('purpose_programs')}</option>
            </select>
          </Field>
        )}
      </div>
    </Modal>
  );
}
