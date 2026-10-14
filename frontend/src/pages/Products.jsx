import { useState } from 'react';
import { Link } from 'react-router-dom';
import { CalendarClock, ExternalLink, EyeOff, Link2, PackageSearch, Plus, RotateCcw, ShoppingBag, Sparkles, Trash2 } from 'lucide-react';
import { BulkBar, Button, Empty, ErrorBox, Field, Loading, Modal, PageHead, SelectAll, StatusPill, useAction, useLoad, useSelection, useToast } from '../components/ui';
import { api, mediaUrl } from '../lib/api';
import { useI18n } from '../lib/i18n';

const wait = (ms) => new Promise((r) => setTimeout(r, ms));

export default function Products() {
  const { t } = useI18n();
  const toast = useToast();
  const items = useLoad(() => api.get('/api/products'), []);
  const brands = useLoad(() => api.get('/api/brands'), []);
  const [url, setUrl] = useState('');
  const [filter, setFilter] = useState('new');
  const [busy, run] = useAction();
  const [result, setResult] = useState(null);
  const [adding, setAdding] = useState(false);
  const list = (items.data || []).filter((p) => filter === 'all' || p.status === filter);
  const sel = useSelection(list);
  const bulkActions = BULK_ACTIONS(t);
  const site = url.trim() || brands.data?.[0]?.website || '';

  // Reading a link runs on the server as a job (JavaScript sites open in a real browser): poll until done
  const sync = () => run('sync', async () => {
    setResult(null);
    const { job } = await api.post('/api/products/sync', { url: site });
    for (let i = 0; i < 120; i += 1) {
      await wait(i < 5 ? 1500 : 3000);
      const s = await api.get(`/api/products/sync/${job}`);
      if (s.status === 'done') {
        setResult(s.result);
        setFilter('new');
        items.reload(true);
        if (s.result.found) toast(`${t('products_found')}: ${s.result.found} · ${t('products_added')}: ${s.result.added}`, 'success');
        return;
      }
      if (s.status === 'failed') throw new Error(s.error);
    }
    throw new Error(t('products_timeout'));
  });
  const one = (p, schedule) => run(`d-${p.id}-${schedule ? 's' : 'p'}`, async () => {
    await api.post(`/api/products/${p.id}/draft`, { schedule });
    items.reload(true);
  }, schedule ? t('products_scheduling') : t('started'));
  const bulk = (action) => run(`bulk-${action}`, async () => {
    await api.post('/api/products/bulk', { ids: sel.ids, action });
    sel.clear();
    items.reload(true);
  }, action === 'schedule' ? t('products_scheduling') : action === 'draft' ? t('started') : t('done'));

  if (items.loading && !items.data) return <Loading />;
  const counts = (items.data || []).reduce((a, p) => ({ ...a, [p.status]: (a[p.status] || 0) + 1 }), {});

  return (
    <>
      <PageHead title={t('products_title')} sub={t('products_sub')}>
        <Button icon={Plus} onClick={() => setAdding(true)}>{t('products_add_manual')}</Button>
      </PageHead>
      {items.error && <ErrorBox error={items.error} onRetry={items.reload} />}
      <section className="card card-pad stack prod-read">
        <label className="field-head" htmlFor="prod-url"><Link2 size={16} /> {t('products_link')}</label>
        <div className="prod-read-row">
          <input id="prod-url" className="input ltr" dir="ltr" type="url" inputMode="url" value={url}
            placeholder={brands.data?.[0]?.website || 'https://your-site.com/offers'} onChange={(e) => setUrl(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && site && sync()} />
          <Button variant="primary" icon={PackageSearch} busy={busy === 'sync'} disabled={!site} onClick={sync}>
            {busy === 'sync' ? t('products_reading') : t('products_read')}
          </Button>
        </div>
        <p className="xs muted" style={{ margin: 0 }}>{t('products_hint')}</p>
        {result && (result.found ? (
          <div className="banner ok">{t('products_found')}: <b>{result.found}</b> · {t('products_added')}: <b>{result.added}</b>
            <span className="muted xs">({t(`products_method_${String(result.method || '').replace('browser-', '')}`) || result.method})</span></div>
        ) : (
          <div className="banner warn">{result.blocked ? t('products_blocked') : t('products_none')}
            <button type="button" className="btn btn-sm" style={{ marginInlineStart: 'auto' }} onClick={() => setAdding(true)}><Plus size={14} /> {t('products_add_manual')}</button></div>
        ))}
      </section>

      <div className="row prod-filters">
        <div className="seg" role="tablist">
          {['new', 'drafted', 'skipped', 'all'].map((s) => (
            <button key={s} type="button" className={`seg-item ${filter === s ? 'on' : ''}`} onClick={() => { setFilter(s); sel.clear(); }}>
              {t(`products_${s}`)}{s !== 'all' && counts[s] ? ` (${counts[s]})` : ''}
            </button>
          ))}
        </div>
        <div className="spacer" />
        {list.length > 0 && <SelectAll sel={sel} label={t('select_all')} />}
      </div>

      <BulkBar sel={sel} busy={busy} selectedLabel={t('selected')} clearLabel={t('clear_selection')} onAction={bulk}
        actions={bulkActions} />
      {list.length === 0 ? <div className="card"><Empty icon={ShoppingBag}>{t('products_empty')}</Empty></div> : (
        <div className="stack">
          {list.map((p) => (
            <div key={p.id} className={`card prod-item ${sel.has(p.id) ? 'on' : ''}`}>
              <input type="checkbox" checked={sel.has(p.id)} onChange={() => sel.toggle(p.id)} aria-label={t('select')} />
              <div className="prod-thumb">{p.image_url && <img src={mediaUrl(p.image_url)} alt="" loading="lazy" />}</div>
              <div className="prod-body">
                <div className="row" style={{ gap: 6 }}>
                  <b dir="auto">{p.name}</b>
                  <span className="pill">{t(`kind_${p.kind}`)}</span>
                  {p.price && <span className="pill gold ltr">{p.price} {p.currency}</span>}
                  <StatusPill status={p.status === 'drafted' ? 'approved' : p.status === 'skipped' ? 'rejected' : 'pending_review'} label={t(`products_${p.status}`)} />
                </div>
                <p className="xs muted clamp-2" dir="auto" style={{ margin: '6px 0' }}>{p.description}</p>
                {p.url.startsWith('http') && <a className="xs ltr prod-link" href={p.url} target="_blank" rel="noreferrer"><ExternalLink size={11} /> {(() => { try { return decodeURI(p.url); } catch { return p.url; } })()}</a>}
              </div>
              <div className="prod-actions">
                {p.draft_id ? (
                  <Link className="btn btn-sm" to={`/drafts/${p.draft_id}`}>{t('open_post')}</Link>
                ) : (
                  <>
                    <Button size="sm" variant="primary" icon={CalendarClock} busy={busy === `d-${p.id}-s`} onClick={() => one(p, true)}>{t('products_post_schedule')}</Button>
                    <Button size="sm" icon={Sparkles} busy={busy === `d-${p.id}-p`} onClick={() => one(p, false)}>{t('products_make_post')}</Button>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
      <BulkBar sel={sel} busy={busy} selectedLabel={t('selected')} clearLabel={t('clear_selection')} onAction={bulk}
        place="bottom" actions={bulkActions} />
      {adding && <AddModal onClose={() => setAdding(false)} onSaved={() => { setAdding(false); setFilter('new'); items.reload(true); }} />}
    </>
  );
}

// the same action row sits above the list (it follows while scrolling) and below it
const BULK_ACTIONS = (t) => ([
  { key: 'schedule', label: t('products_posts_schedule'), icon: CalendarClock, variant: 'primary' },
  { key: 'draft', label: t('products_make_posts'), icon: Sparkles },
  { key: 'skip', label: t('products_skip'), icon: EyeOff },
  { key: 'restore', label: t('restore'), icon: RotateCcw },
  { key: 'delete', label: t('delete'), icon: Trash2, variant: 'danger', confirm: t('confirm_delete') },
]);

function AddModal({ onClose, onSaved }) {
  const { t } = useI18n();
  const [f, setF] = useState({ name: '', url: '', description: '', price: '', currency: '', image_url: '', kind: 'product' });
  const [busy, run] = useAction();
  const set = (k, v) => setF((x) => ({ ...x, [k]: v }));
  const save = () => run('save', async () => {
    await api.post('/api/products', { ...f, image_url: f.image_url.trim() || null });
    onSaved();
  }, t('saved'));
  return (
    <Modal title={t('products_add_manual')} onClose={onClose} footer={<>
      <span className="spacer" />
      <Button variant="ghost" onClick={onClose}>{t('cancel')}</Button>
      <Button variant="primary" icon={Plus} busy={busy === 'save'} disabled={f.name.trim().length < 2} onClick={save}>{t('add')}</Button>
    </>}>
      <div className="stack">
        <div className="seg">
          {['product', 'service', 'course', 'offer', 'event'].map((k) => (
            <button key={k} type="button" className={`seg-item ${f.kind === k ? 'on' : ''}`} onClick={() => set('kind', k)}>{t(`kind_${k}`)}</button>
          ))}
        </div>
        <Field label={t('offer_title')}><input className="input" value={f.name} onChange={(e) => set('name', e.target.value)} /></Field>
        <Field label={t('products_page_link')}><input className="input ltr" dir="ltr" value={f.url} placeholder="https://" onChange={(e) => set('url', e.target.value)} /></Field>
        <div className="grid grid-2">
          <Field label={t('offer_price')}><input className="input" value={f.price} onChange={(e) => set('price', e.target.value)} /></Field>
          <Field label={t('offer_currency')}><input className="input" value={f.currency} placeholder="RM / SAR / USD" onChange={(e) => set('currency', e.target.value)} /></Field>
        </div>
        <Field label={t('products_image_link')}><input className="input ltr" dir="ltr" value={f.image_url} placeholder="https://…jpg" onChange={(e) => set('image_url', e.target.value)} /></Field>
        <Field label={t('offer_details')}><textarea className="textarea" rows={4} value={f.description} onChange={(e) => set('description', e.target.value)} /></Field>
      </div>
    </Modal>
  );
}
