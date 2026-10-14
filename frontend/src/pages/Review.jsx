import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { CalendarClock, Camera, Check, ChevronDown, ChevronLeft, ImagePlus, Images, Lightbulb, Plus, RefreshCw, RotateCcw, Search, Sparkles, Tag, Trash2, X } from 'lucide-react';
import { BulkBar, Button, Empty, ErrorBox, Field, Menu, Modal, PageHead, SelectAll, Spinner, StatusPill, useAction, useLoad, useSelection } from '../components/ui';
import { api, mediaUrl } from '../lib/api';
import ScrapeModal from '../components/ScrapeModal';
import { dayBucket, fmtDate, relative } from '../lib/format';
import { useExample } from '../lib/useExample';
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
  const [showAlbum, setShowAlbum] = useState(false);
  const [showOffer, setShowOffer] = useState(false);
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
        <Button icon={RefreshCw} busy={busy === 'scrape' || jobs.data?.running} onClick={() => setShowScrape(true)}>
          {t('run_scrape')}
        </Button>
        <Menu variant="primary" icon={Plus} label={t('create_post')} items={[
          { key: 'topic', icon: Lightbulb, label: t('new_post'), hint: t('create_topic_hint'), onClick: () => setShowManual(true) },
          { key: 'offer', icon: Tag, label: t('offer_new'), hint: t('create_offer_hint'), onClick: () => setShowOffer(true) },
          { key: 'album', icon: Camera, label: t('album_new'), hint: t('create_album_hint'), onClick: () => setShowAlbum(true) },
        ]} />
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
        <div className="search-box">
          <Search size={16} className="muted" />
          <input className="input" type="search" placeholder={t('search')} value={q}
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
      {showAlbum && <AlbumModal onClose={() => setShowAlbum(false)} />}
      {showOffer && <OfferModal onClose={() => setShowOffer(false)} />}
    </>
  );
}

function DraftCard({ d, picked, onPick }) {
  const { t, lang } = useI18n();
  const origin = d.origin === 'source' ? d.source : d.origin === 'calendar' ? t('calendar_origin') : d.origin === 'offer' ? t('offer_new') : d.origin === 'occasion' ? t('occasion_origin') : t('manual');
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

const ALBUM_MAX = 10;

/** Photos for a post: uploaded from the device (reorderable) and/or picked from the library. */
function usePhotos(max) {
  const [files, setFiles] = useState([]);          // [{file, url}]
  const [picked, setPicked] = useState([]);        // library ids
  useEffect(() => () => files.forEach((f) => URL.revokeObjectURL(f.url)), []); // eslint-disable-line
  const total = files.length + picked.length;
  const addFiles = (list) => {
    const room = max - total;
    const next = [...list].filter((f) => f.type.startsWith('image/')).slice(0, Math.max(0, room))
      .map((file) => ({ file, url: URL.createObjectURL(file) }));
    setFiles((x) => [...x, ...next]);
  };
  const fill = (fd) => {
    files.forEach((f) => fd.append('files', f.file));
    fd.append('media_ids', picked.join(','));
  };
  return { files, setFiles, picked, setPicked, total, addFiles, fill, max };
}

function PhotoPicker({ photos, label, hint, coverTag = true }) {
  const { t } = useI18n();
  const fileRef = useRef(null);
  const [showLib, setShowLib] = useState(false);
  const library = useLoad(() => (showLib ? api.get('/api/media') : Promise.resolve(null)), [showLib]);
  const { files, setFiles, picked, setPicked, total, addFiles, max } = photos;
  const move = (i, d) => setFiles((x) => {
    const j = i + d;
    if (j < 0 || j >= x.length) return x;
    const y = [...x]; [y[i], y[j]] = [y[j], y[i]]; return y;
  });
  return (
    <Field label={`${label} (${total}/${max})`} hint={hint}>
      <div className="album-grid" onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => { e.preventDefault(); addFiles(e.dataTransfer.files); }}>
        {files.map((f, i) => (
          <div key={f.url} className="album-tile">
            <img src={f.url} alt="" />
            {coverTag && i === 0 && !picked.length && <span className="album-tag">{t('album_cover')}</span>}
            <div className="album-tools">
              <button type="button" onClick={() => move(i, -1)} aria-label="←">‹</button>
              <button type="button" onClick={() => setFiles((x) => x.filter((_, k) => k !== i))} aria-label={t('delete')}><X size={14} /></button>
              <button type="button" onClick={() => move(i, 1)} aria-label="→">›</button>
            </div>
          </div>
        ))}
        {total < max && (
          <button type="button" className="album-add" onClick={() => fileRef.current?.click()}>
            <ImagePlus size={26} /><span>{t('album_add')}</span>
          </button>
        )}
      </div>
      <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp" multiple hidden
        onChange={(e) => { addFiles(e.target.files); e.target.value = ''; }} />
      <div className="row" style={{ marginTop: 8 }}>
        <Button size="sm" icon={Images} onClick={() => setShowLib((v) => !v)}>{t('album_from_library')}{picked.length ? ` (${picked.length})` : ''}</Button>
      </div>
      {showLib && (
        <div className="album-grid lib" style={{ marginTop: 8 }}>
          {(library.data || []).map((a) => {
            const on = picked.includes(a.id);
            return (
              <button type="button" key={a.id} className={`album-tile pick-lib ${on ? 'on' : ''}`}
                disabled={!on && total >= max}
                onClick={() => setPicked((x) => (on ? x.filter((k) => k !== a.id) : [...x, a.id]))}>
                <img src={mediaUrl(a.url)} alt="" loading="lazy" />
                {on && <span className="album-tag">{picked.indexOf(a.id) + 1}</span>}
              </button>
            );
          })}
          {library.data && !library.data.length && <span className="xs muted">{t('album_library_empty')}</span>}
        </div>
      )}
    </Field>
  );
}

function DialectField({ value, onChange }) {
  const { t } = useI18n();
  return (
    <Field label={t('dialect')}>
      <select className="select" value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">{t('dialect_default')}</option>
        {DIALECTS.map((x) => <option key={x} value={x}>{t(`dialect_${x}`)}</option>)}
      </select>
    </Field>
  );
}

function AlbumModal({ onClose }) {
  const { t } = useI18n();
  const ex = useExample();
  const navigate = useNavigate();
  const [title, setTitle] = useState('');
  const [text, setText] = useState('');
  const [dialect, setDialect] = useState('');
  const photos = usePhotos(ALBUM_MAX);
  const [busy, run] = useAction();
  const submit = () => run('go', async () => {
    const fd = new FormData();
    photos.fill(fd);
    fd.append('title', title);
    fd.append('text', text);
    if (dialect) fd.append('dialect', dialect);
    const r = await api.post('/api/drafts/album', fd);
    onClose();
    navigate(`/drafts/${r.draft_id}`);
  }, t('started'));

  return (
    <Modal wide title={t('album_new')} onClose={onClose}
      footer={<>
        <Button onClick={onClose}>{t('cancel')}</Button>
        <Button variant="primary" icon={Sparkles} busy={busy === 'go'} disabled={!photos.total || (!title.trim() && !text.trim())} onClick={submit}>
          {t('generate')}
        </Button>
      </>}>
      <div className="stack">
        <p className="muted small" style={{ margin: 0 }}>{t('album_hint')}</p>
        <Field label={t('album_title')}>
          <input className="input" value={title} placeholder={ex('topic')} onChange={(e) => setTitle(e.target.value)} autoFocus />
        </Field>
        <Field label={t('album_text')} hint={t('album_text_hint')}>
          <textarea className="textarea" rows={3} value={text} placeholder={ex('notes')} onChange={(e) => setText(e.target.value)} />
        </Field>
        <PhotoPicker photos={photos} label={t('album_photos')} hint={t('album_photos_hint')} />
        <DialectField value={dialect} onChange={setDialect} />
      </div>
    </Modal>
  );
}

const OFFER_KINDS = ['package', 'offer', 'service', 'limited'];

function OfferModal({ onClose }) {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [f, setF] = useState({ kind: 'offer', title: '', details: '', price: '', old_price: '', currency: '',
    valid_until: '', audience: '', link: '' });
  const [dialect, setDialect] = useState('');
  const photos = usePhotos(10);
  const [busy, run] = useAction();
  const set = (k, v) => setF((x) => ({ ...x, [k]: v }));
  const submit = () => run('go', async () => {
    const fd = new FormData();
    photos.fill(fd);
    Object.entries(f).forEach(([k, v]) => fd.append(k, v));
    if (dialect) fd.append('dialect', dialect);
    const r = await api.post('/api/drafts/offer', fd);
    onClose();
    navigate(`/drafts/${r.draft_id}`);
  }, t('started'));

  return (
    <Modal wide title={t('offer_new')} onClose={onClose}
      footer={<>
        <Button onClick={onClose}>{t('cancel')}</Button>
        <Button variant="primary" icon={Sparkles} busy={busy === 'go'} disabled={f.title.trim().length < 2} onClick={submit}>
          {t('generate')}
        </Button>
      </>}>
      <div className="stack">
        <p className="muted small" style={{ margin: 0 }}>{t('offer_hint')}</p>
        <div className="seg" role="radiogroup">
          {OFFER_KINDS.map((k) => (
            <button type="button" key={k} role="radio" aria-checked={f.kind === k}
              className={`seg-item ${f.kind === k ? 'on' : ''}`} onClick={() => set('kind', k)}>{t(`offer_${k}`)}</button>
          ))}
        </div>
        <Field label={t('offer_title')}>
          <input className="input" value={f.title} onChange={(e) => set('title', e.target.value)} autoFocus />
        </Field>
        <Field label={t('offer_details')} hint={t('offer_details_hint')}>
          <textarea className="textarea" rows={3} value={f.details} onChange={(e) => set('details', e.target.value)} />
        </Field>
        <div className="grid grid-3">
          <Field label={t('offer_price')}><input className="input" inputMode="decimal" value={f.price} onChange={(e) => set('price', e.target.value)} /></Field>
          <Field label={t('offer_old_price')}><input className="input" inputMode="decimal" value={f.old_price} onChange={(e) => set('old_price', e.target.value)} /></Field>
          <Field label={t('offer_currency')}><input className="input" value={f.currency} placeholder="RM / SAR / USD" onChange={(e) => set('currency', e.target.value)} /></Field>
        </div>
        <div className="grid grid-2">
          <Field label={t('offer_valid')}><input className="input" value={f.valid_until} placeholder={t('offer_valid_ph')} onChange={(e) => set('valid_until', e.target.value)} /></Field>
          <Field label={t('offer_link')}><input className="input ltr" value={f.link} placeholder="https://" onChange={(e) => set('link', e.target.value)} /></Field>
        </div>
        <Field label={t('offer_audience')}>
          <input className="input" value={f.audience} onChange={(e) => set('audience', e.target.value)} />
        </Field>
        <PhotoPicker photos={photos} label={t('offer_photos')} hint={t('offer_photos_hint')} coverTag={false} />
        <DialectField value={dialect} onChange={setDialect} />
      </div>
    </Modal>
  );
}

function ManualModal({ onClose, onDone }) {
  const ex = useExample();
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
            placeholder={ex('topic')} autoFocus />
        </Field>
        <Field label={t('notes')}>
          <textarea className="textarea" value={notes} placeholder={ex('notes')} onChange={(e) => setNotes(e.target.value)} />
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
