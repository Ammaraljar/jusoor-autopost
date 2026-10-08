import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ExternalLink, EyeOff, PackageSearch, RefreshCw, RotateCcw, ShoppingBag, Sparkles, Trash2 } from 'lucide-react';
import { BulkBar, Button, Empty, ErrorBox, Loading, PageHead, SelectAll, StatusPill, useAction, useLoad, useSelection } from '../components/ui';
import { api, mediaUrl } from '../lib/api';
import { useI18n } from '../lib/i18n';

export default function Products() {
  const { t } = useI18n();
  const items = useLoad(() => api.get('/api/products'), []);
  const brands = useLoad(() => api.get('/api/brands'), []);
  const [url, setUrl] = useState('');
  const [filter, setFilter] = useState('new');
  const [busy, run] = useAction();
  const list = (items.data || []).filter((p) => filter === 'all' || p.status === filter);
  const sel = useSelection(list);
  const site = url || brands.data?.[0]?.website || '';

  const sync = () => run('sync', async () => {
    const r = await api.post('/api/products/sync', { url: site });
    items.reload(true);
    return r;
  }).then((r) => r && window.alert(`${t('products_found')}: ${r.found} · ${t('products_added')}: ${r.added}`));
  const one = (p) => run(`d-${p.id}`, async () => { await api.post(`/api/products/${p.id}/draft`); items.reload(true); }, t('started'));
  const bulk = (action) => run(`bulk-${action}`, async () => {
    await api.post('/api/products/bulk', { ids: sel.ids, action });
    sel.clear();
    items.reload(true);
  }, action === 'draft' ? t('started') : t('done'));

  if (items.loading && !items.data) return <Loading />;
  const counts = (items.data || []).reduce((a, p) => ({ ...a, [p.status]: (a[p.status] || 0) + 1 }), {});

  return (
    <>
      <PageHead title={t('products_title')} sub={t('products_sub')}>
        <Button variant="primary" icon={RefreshCw} busy={busy === 'sync'} onClick={sync}>{t('products_sync')}</Button>
      </PageHead>
      {items.error && <ErrorBox error={items.error} onRetry={items.reload} />}
      <div className="card card-pad stack" style={{ marginBottom: 16 }}>
        <div className="row" style={{ flexWrap: 'nowrap', gap: 8 }}>
          <input className="input ltr" value={url} placeholder={site || 'https://your-site.com'} onChange={(e) => setUrl(e.target.value)} />
          <Button icon={PackageSearch} busy={busy === 'sync'} onClick={sync}>{t('products_read')}</Button>
        </div>
        <p className="xs muted" style={{ margin: 0 }}>{t('products_hint')}</p>
      </div>

      <div className="row" style={{ marginBottom: 10 }}>
        {['new', 'drafted', 'skipped', 'all'].map((s) => (
          <button key={s} className={`btn btn-sm ${filter === s ? 'btn-primary' : ''}`} onClick={() => { setFilter(s); sel.clear(); }}>
            {t(`products_${s}`)}{s !== 'all' && counts[s] ? ` (${counts[s]})` : ''}
          </button>
        ))}
        <div className="spacer" />
        {list.length > 0 && <SelectAll sel={sel} label={t('select_all')} />}
      </div>

      {list.length === 0 ? <Empty icon={ShoppingBag}>{t('products_empty')}</Empty> : (
        <div className="stack">
          {list.map((p) => (
            <div key={p.id} className="card card-pad row" style={{ alignItems: 'flex-start', flexWrap: 'nowrap', gap: 14 }}>
              <input type="checkbox" checked={sel.has(p.id)} onChange={() => sel.toggle(p.id)} style={{ marginTop: 6 }} />
              <div style={{ width: 92, height: 92, borderRadius: 12, overflow: 'hidden', flex: 'none', background: 'var(--surface-2, #eee)' }}>
                {p.image_url && <img src={mediaUrl(p.image_url)} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />}
              </div>
              <div style={{ minWidth: 0, flex: 1 }}>
                <div className="row" style={{ gap: 6 }}>
                  <b dir="auto">{p.name}</b>
                  <span className="pill">{t(`kind_${p.kind}`)}</span>
                  {p.price && <span className="pill gold ltr">{p.price} {p.currency}</span>}
                  <StatusPill status={p.status === 'drafted' ? 'approved' : p.status === 'skipped' ? 'rejected' : 'pending_review'} label={t(`products_${p.status}`)} />
                </div>
                <p className="xs muted clamp-2" dir="auto" style={{ margin: '6px 0' }}>{p.description}</p>
                <a className="xs ltr" href={p.url} target="_blank" rel="noreferrer"><ExternalLink size={11} /> {p.url}</a>
              </div>
              <div className="stack" style={{ gap: 6, flex: 'none' }}>
                {p.draft_id ? (
                  <Link className="btn btn-sm" to={`/drafts/${p.draft_id}`}>{t('open_post')}</Link>
                ) : (
                  <Button size="sm" variant="primary" icon={Sparkles} busy={busy === `d-${p.id}`} onClick={() => one(p)}>{t('products_make_post')}</Button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
      <BulkBar sel={sel} busy={busy} selectedLabel={t('selected')} clearLabel={t('clear_selection')} onAction={bulk}
        actions={[
          { key: 'draft', label: t('products_make_posts'), icon: Sparkles, variant: 'primary' },
          { key: 'skip', label: t('products_skip'), icon: EyeOff },
          { key: 'restore', label: t('restore'), icon: RotateCcw },
          { key: 'delete', label: t('delete'), icon: Trash2, variant: 'danger', confirm: t('confirm_delete') },
        ]} />
    </>
  );
}
