import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { CalendarClock, Check, ChevronDown, ChevronLeft, Images, Lightbulb, RefreshCw, RotateCcw, Search, Sparkles, Trash2, X } from 'lucide-react';
import { BulkBar, Button, Empty, ErrorBox, Field, Modal, PageHead, SelectAll, Spinner, StatusPill, useAction, useLoad, useSelection } from '../components/ui';
import { api, mediaUrl } from '../lib/api';
import ScrapeModal from '../components/ScrapeModal';
import { dayBucket, fmtDate, relative } from '../lib/format';
import { DIALECTS, useI18n } from '../lib/i18n';

const TABS = ['pending_review', 'all', 'approved', 'scheduled', 'published', 'failed', 'rejected'];
const BUCKETS = ['today', 'yesterday', 'week', 'older'];

export default function Review() {
  const { t, lang } = useI18n();
  const [params, setParams] = useSearchParams();
  const status = params.get('status') || 'pending_review';
  const campaign = params.get('campaign');
  const [q, setQ] = useState('');
  const [query, setQuery] = useState('');
  const [collapsed, setCollapsed] = useState({});
  const [showManual, setShowManual] = useState(false);
  const [showScrape, setShowScrape] = useState(false);
  const [busy, run] = useAction();

  useEffect(() => {
    const id = setTimeout(() => setQuery(q), 300);
    return () => clearTimeout(id);
  }, [q]);

  const path = `/api/drafts?status=${status === 'all' ? 'all' : status}` +
    (query ? `&q=${encodeURIComponent(query)}` : '') + (campaign ? `&campaign_id=${campaign}` : '');
  const drafts = useLoad(() => api.get(path), [path]);
  const counts = useLoad(() => api.get('/api/drafts/counts'), [path]);
  const jobs = useLoad(() => api.get('/api/jobs'), []);

  // Poll while something is running
  const active = jobs.data?.running || drafts.data?.some((d) => ['generating', 'publishing'].includes(d.status));
  useEffect(() => {
    if (!active) return undefined;
    const id = setInterval(() => { drafts.reload(true); counts.reload(true); jobs.reload(true); }, 5000);
    return () => clearInterval(id);
  }, [active]); // eslint-disable-line react-hooks/exhaustive-deps

  const groups = useMemo(() => {
    const g = Object.fromEntries(BUCKETS.map((b) => [b, []]));
    (drafts.data || []).forEach((d) => g[dayBucket(d.created_at)].push(d));
    return g;
  }, [drafts.data]);

  const sel = useSelection(drafts.data);
  const bulk = (action) => run(`bulk-${action}`, async () => {
    const res = await api.post('/api/drafts/bulk', { ids: sel.ids, action });
    sel.clear();
    await Promise.all([drafts.reload(true), counts.reload(true)]);
    if (res.skipped) {
      throw new Error(`${t('done')}: ${res.done} · ${t('skipped')}: ${res.skipped}${res.reasons?.length ? ` — ${res.reasons[0]}` : ''}`);
    }
    return res;
  }, t('done'));
  const bulkActions = [
    { key: 'auto_schedule', label: t('auto_schedule'), icon: CalendarClock, variant: 'gold' },
    { key: 'approve', label: t('approve'), icon: Check },
    { key: 'reject', label: t('reject'), icon: X },
    { key: 'restore', label: t('restore'), icon: RotateCcw },
    { key: 'delete', label: t('delete_forever'), icon: Trash2, variant: 'danger', confirm: t('confirm_bulk_delete') },
  ];

  const scrape = () => run('scrape', async () => {
    await api.post('/api/scrape/run-all');
    await jobs.reload(true);
  }, t('started'));

  return (
    <>
      <PageHead title={t('review_title')} sub={t('review_sub')}>
        <Button icon={Lightbulb} onClick={() => setShowManual(true)}>{t('new_post')}</Button>
        <Button variant="primary" icon={RefreshCw} busy={busy === 'scrape' || jobs.data?.running} onClick={() => setShowScrape(true)}>
          {t('run_scrape')}
        </Button>
      </PageHead>

      {jobs.data?.running && <div className="banner info"><Spinner size={16} /> {t('scrape_running')}</div>}
      {!jobs.data?.running && jobs.data?.last_run && (
        <div className="small muted" style={{ marginBottom: 10 }}>
          {t('last_run')}: {relative(jobs.data.last_run.finished_at, lang)} ·{' '}
          {jobs.data.last_run.new_articles ?? 0} {t('articles')} · {jobs.data.last_run.drafts ?? 0} {t('drafts')}
          {jobs.data.last_run.errors?.length ? ` · ⚠ ${jobs.data.last_run.errors.length}` : ''}
        </div>
      )}

      <div className="row" style={{ marginBottom: 6 }}>
        <div className="tabs">
          {TABS.map((s) => (
            <button key={s} className={`tab ${status === s ? 'active' : ''}`}
              onClick={() => setParams(s === 'pending_review' ? {} : { status: s })}>
              {t(`st_${s}`)}
              {counts.data && <span className="n">{counts.data[s] ?? 0}</span>}
            </button>
          ))}
        </div>
        <div className="spacer" />
        <div style={{ position: 'relative', minWidth: 220 }}>
          <Search size={16} className="muted" style={{ position: 'absolute', insetInlineStart: 10, top: 11 }} />
          <input className="input" style={{ paddingInlineStart: 34 }} placeholder={t('search')} value={q}
            onChange={(e) => setQ(e.target.value)} />
        </div>
      </div>
      {campaign && (
        <div className="row small" style={{ margin: '8px 0' }}>
          <span className="pill gold">{t('campaign')} #{campaign}</span>
          <button className="btn btn-sm btn-ghost" onClick={() => setParams(status === 'pending_review' ? {} : { status })}>✕</button>
        </div>
      )}

      {drafts.data?.length > 0 && (
        <div className="select-row">
          <SelectAll sel={sel} label={t('select_all')} />
          {!sel.count && <span className="xs muted">{t('select_hint')}</span>}
        </div>
      )}
      <BulkBar sel={sel} actions={bulkActions} onAction={bulk} busy={busy}
        selectedLabel={t('selected')} clearLabel={t('clear_selection')} />

      {drafts.error && <ErrorBox error={drafts.error} onRetry={drafts.reload} />}
      {drafts.loading && !drafts.data && <div className="center-page"><Spinner /></div>}
      {drafts.data && drafts.data.length === 0 && <Empty>{t('no_drafts')}</Empty>}

      {BUCKETS.filter((b) => groups[b].length).map((b) => (
        <section key={b}>
          <button className="group-head" onClick={() => setCollapsed((c) => ({ ...c, [b]: !c[b] }))}>
            {collapsed[b] ? <ChevronLeft size={18} /> : <ChevronDown size={18} />}
            {t(b)} <span className="n">{groups[b].length}</span>
          </button>
          {!collapsed[b] && (
            <div className="draft-grid">
              {groups[b].map((d) => <DraftCard key={d.id} d={d} picked={sel.has(d.id)} onPick={() => sel.toggle(d.id)} />)}
            </div>
          )}
        </section>
      ))}

      {showScrape && <ScrapeModal onClose={() => setShowScrape(false)} onStarted={() => jobs.reload(true)} />}
      {showManual && <ManualModal onClose={() => setShowManual(false)} onDone={() => drafts.reload(true)} />}
    </>
  );
}

function DraftCard({ d, picked, onPick }) {
  const { t, lang } = useI18n();
  const origin = d.origin === 'source' ? d.source : d.origin === 'calendar' ? t('calendar_origin') : t('manual');
  return (
    <Link to={`/drafts/${d.id}`} className={`card draft-card ${picked ? 'picked' : ''}`}>
      <div className="thumb">
        <span className="pick" role="checkbox" aria-checked={picked} title={t('select')}
          onClick={(e) => { e.preventDefault(); e.stopPropagation(); onPick(); }}>
          <input type="checkbox" checked={picked} readOnly tabIndex={-1} style={{ pointerEvents: 'none' }} />
        </span>
        {d.cover_url ? <img src={mediaUrl(d.cover_url)} alt="" loading="lazy" /> : <Sparkles size={34} />}
        <StatusPill status={d.status} />
        {d.slides > 0 && <span className="count"><Images size={12} /> {d.slides}</span>}
        {(d.content_type === 'program' || (d.dialect && d.dialect !== 'msa')) && (
          <span className="tags-corner">
            {d.content_type === 'program' && <span className="pill gold">{t('program')}</span>}
            {d.dialect && d.dialect !== 'msa' && <span className="pill info">{t(`dialect_${d.dialect}`)}</span>}
          </span>
        )}
      </div>
      <div className="body">
        <div className="title clamp-2" dir="auto">{d.hook || '…'}</div>
        {d.error && <div className="xs clamp-2" style={{ color: 'var(--danger)' }}>{d.error}</div>}
        <div className="meta">
          <span className="clamp-2">{origin}</span>
          <span style={{ whiteSpace: 'nowrap' }}>
            {d.status === 'scheduled' ? fmtDate(d.scheduled_at, lang, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
              : fmtDate(d.original_published_at || d.created_at, lang)}
          </span>
        </div>
      </div>
    </Link>
  );
}

function ManualModal({ onClose, onDone }) {
  const { t } = useI18n();
  const [topic, setTopic] = useState('');
  const [notes, setNotes] = useState('');
  const [dialect, setDialect] = useState('');
  const [busy, run] = useAction();
  const brands = useLoad(() => api.get('/api/brands'), []);
  const [brandId, setBrandId] = useState('');

  const submit = () => run('go', async () => {
    await api.post('/api/drafts/manual', { topic, notes, brand_id: brandId ? Number(brandId) : null, dialect: dialect || null });
    onDone();
    onClose();
  }, t('started'));

  return (
    <Modal title={t('manual_title')} onClose={onClose}
      footer={<>
        <Button onClick={onClose}>{t('cancel')}</Button>
        <Button variant="primary" icon={Sparkles} busy={busy === 'go'} disabled={topic.trim().length < 3} onClick={submit}>
          {t('generate')}
        </Button>
      </>}>
      <div className="stack">
        <p className="muted small">{t('manual_hint')}</p>
        <Field label={t('topic')}>
          <input className="input" value={topic} onChange={(e) => setTopic(e.target.value)}
            placeholder="أفضل 5 أنشطة عائلية في لنكاوي" autoFocus />
        </Field>
        <Field label={t('notes')}>
          <textarea className="textarea" value={notes} onChange={(e) => setNotes(e.target.value)} />
        </Field>
        <Field label={t('dialect')}>
          <select className="select" value={dialect} onChange={(e) => setDialect(e.target.value)}>
            <option value="">{t('dialect_default')}</option>
            {DIALECTS.map((x) => <option key={x} value={x}>{t(`dialect_${x}`)}</option>)}
          </select>
        </Field>
        {brands.data?.length > 1 && (
          <Field label={t('brand')}>
            <select className="select" value={brandId} onChange={(e) => setBrandId(e.target.value)}>
              <option value="">{brands.data.find((b) => b.is_default)?.name}</option>
              {brands.data.filter((b) => !b.is_default).map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
            </select>
          </Field>
        )}
      </div>
    </Modal>
  );
}
