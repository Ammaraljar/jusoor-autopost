import { useRef, useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import { CheckCircle2, Cloud, FolderSync, Globe, Images, KeyRound, Link2, RefreshCw, Search, Tag, Trash2, Upload } from 'lucide-react';
import { BulkBar, Button, Empty, ErrorBox, Field, Loading, Modal, PageHead, SelectAll, useAction, useLoad, useSelection, useToast } from '../components/ui';
import { api, mediaUrl } from '../lib/api';
import { useExample } from '../lib/useExample';
import { useI18n } from '../lib/i18n';

function LinksModal({ onClose, onDone }) {
  const { t } = useI18n();
  const [urls, setUrls] = useState('');
  const [tags, setTags] = useState('');
  const [result, setResult] = useState(null);
  const [busy, run] = useAction();
  const submit = () => run('links', async () => {
    const list = urls.split(/\s+/).map((u) => u.trim()).filter(Boolean);
    const res = await api.post('/api/media/links', { urls: list, tags });
    setResult(res);
    onDone();
  });
  return (
    <Modal title={t('add_links')} onClose={onClose} footer={(
      <>
        <Button onClick={onClose}>{t('close')}</Button>
        <Button variant="primary" icon={Link2} busy={busy === 'links'} disabled={!urls.trim()} onClick={submit}>{t('add')}</Button>
      </>
    )}>
      <div className="stack">
        <Field label={t('image_links')} hint={t('image_links_hint')}>
          <textarea className="textarea ltr" rows={6} value={urls} placeholder="https://drive.google.com/file/d/…/view"
            onChange={(e) => setUrls(e.target.value)} />
        </Field>
        <Field label={t('tags')} hint={t('tags_hint')}>
          <input className="input" value={tags} onChange={(e) => setTags(e.target.value)} />
        </Field>
        {result && (
          <div className={`banner ${result.errors?.length ? 'warn' : 'ok'} small`} style={{ margin: 0 }}>
            <div>
              {t('added_count')}: {result.added?.length || 0}
              {(result.errors || []).map((e) => <div key={e.url} className="xs ltr">{e.url} — {e.error}</div>)}
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
}

function EditModal({ asset, onClose, onSaved }) {
  const { t } = useI18n();
  const [title, setTitle] = useState(asset.title || '');
  const [tags, setTags] = useState(asset.tags || '');
  const [busy, run] = useAction();
  const save = () => run('save', async () => {
    onSaved(await api.patch(`/api/media/${asset.id}`, { title, tags }));
    onClose();
  }, t('saved'));
  return (
    <Modal title={t('edit_photo')} onClose={onClose} footer={(
      <>
        <Button onClick={onClose}>{t('cancel')}</Button>
        <Button variant="primary" busy={busy === 'save'} onClick={save}>{t('save')}</Button>
      </>
    )}>
      <div className="stack">
        <img src={mediaUrl(asset.url)} alt="" style={{ width: '100%', maxHeight: 280, objectFit: 'contain', borderRadius: 10 }} />
        <Field label={t('title')}>
          <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} />
        </Field>
        <Field label={t('tags')} hint={t('tags_hint')}>
          <input className="input" value={tags} onChange={(e) => setTags(e.target.value)} />
        </Field>
        {asset.source_url && <a className="xs ltr" href={asset.source_url} target="_blank" rel="noreferrer">{asset.source_url}</a>}
      </div>
    </Modal>
  );
}


const KIND_LABEL = { dropbox: 'Dropbox', gdrive: 'Google Drive', onedrive: 'OneDrive / SharePoint', gphotos: 'Google Photos', page: 'lib_kind_page' };
const STOCK = [
  { id: 'pexels', name: 'Pexels', key: true }, { id: 'pixabay', name: 'Pixabay', key: true },
  { id: 'unsplash', name: 'Unsplash', key: true }, { id: 'openverse', name: 'Openverse', key: false },
  { id: 'wikimedia', name: 'Wikimedia Commons', key: false },
];
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

/** Whole libraries linked to the company (imported now, synced again later) + the stock libraries. */
function ConnectedLibraries({ onImported }) {
  const { t, lang } = useI18n();
  const toast = useToast();
  const sources = useLoad(() => api.get('/api/media/sources'), []);
  const status = useLoad(() => api.get('/api/status'), []);
  const [url, setUrl] = useState('');
  const [tags, setTags] = useState('');
  const [busy, run] = useAction();
  const poll = async (job) => {
    for (let i = 0; i < 100; i += 1) {
      await wait(i < 4 ? 1500 : 3000);
      const s = await api.get(`/api/media/import/${job}`);
      if (s.status === 'done') return s.result;
      if (s.status === 'failed') throw new Error(s.error);
    }
    throw new Error(t('products_timeout'));
  };
  const report = (r) => toast(`${t('added_count')}: ${r.added}${r.skipped ? ` · ${t('lib_skipped')}: ${r.skipped}` : ''}`, r.added ? 'success' : 'info');
  const connect = () => run('connect', async () => {
    const { job } = await api.post('/api/media/import', { url: url.trim(), tags, keep: true });
    report(await poll(job));
    setUrl('');
    sources.reload(true);
    onImported();
  });
  const sync = (src) => run(`sync-${src.url}`, async () => {
    const { job } = await api.post('/api/media/sources/sync', { url: src.url });
    report(await poll(job));
    sources.reload(true);
    onImported();
  });
  const remove = (src) => window.confirm(t('lib_remove_confirm')) && run(`rm-${src.url}`, async () => {
    await api.post('/api/media/sources/remove', { url: src.url });
    sources.reload(true);
  });
  const imgs = status.data?.images || {};
  return (
    <section className="card card-pad stack lib-connect">
      <div>
        <h3><FolderSync size={17} /> {t('lib_connect_title')}</h3>
        <p className="xs muted" style={{ margin: 0 }}>{t('lib_connect_hint')}</p>
      </div>
      <div className="lib-providers">
        {['Dropbox', 'Google Drive', 'OneDrive', 'SharePoint', 'Google Photos', t('lib_kind_page')].map((n) => (
          <span key={n} className="lib-provider"><Cloud size={14} /> {n}</span>
        ))}
      </div>
      <div className="lib-connect-row">
        <input className="input ltr" dir="ltr" type="url" value={url} placeholder="https://www.dropbox.com/scl/fo/…  ·  https://drive.google.com/drive/folders/…"
          onChange={(e) => setUrl(e.target.value)} />
        <input className="input" value={tags} placeholder={t('tags')} onChange={(e) => setTags(e.target.value)} />
        <Button variant="primary" icon={Link2} busy={busy === 'connect'} disabled={!url.trim().startsWith('http')} onClick={connect}>
          {busy === 'connect' ? t('lib_importing') : t('lib_connect')}
        </Button>
      </div>
      {(sources.data || []).length > 0 && (
        <div className="lib-sources">
          {sources.data.map((src) => (
            <div key={src.url} className="lib-source">
              <span className="lib-kind">{KIND_LABEL[src.kind]?.startsWith('lib_') ? t(KIND_LABEL[src.kind]) : KIND_LABEL[src.kind] || src.kind}</span>
              <a className="xs ltr lib-url" href={src.url} target="_blank" rel="noreferrer">{src.url}</a>
              <span className="xs muted">{src.count || 0} {t('photos')}{src.last_sync ? ` · ${new Date(src.last_sync).toLocaleDateString(lang === 'ar' ? 'ar-EG-u-nu-latn' : lang)}` : ''}</span>
              <Button size="sm" icon={RefreshCw} busy={busy === `sync-${src.url}`} onClick={() => sync(src)}>{t('lib_sync')}</Button>
              <button type="button" className="btn btn-sm btn-ghost btn-danger icon-btn" aria-label={t('delete')} onClick={() => remove(src)}><Trash2 size={15} /></button>
            </div>
          ))}
        </div>
      )}
      <div className="divider" />
      <div>
        <b className="small">{t('lib_stock_title')}</b>
        <p className="xs muted" style={{ margin: '2px 0 8px' }}>{t('lib_stock_hint')}</p>
        <div className="lib-stock">
          {STOCK.map((s) => {
            const on = s.key ? imgs[s.id] : true;
            return (
              <div key={s.id} className={`lib-stock-item ${on ? 'on' : ''}`}>
                {on ? <CheckCircle2 size={16} /> : <KeyRound size={16} />}
                <b>{s.name}</b>
                <span className="xs muted">{s.key ? (on ? t('configured') : t('key_missing')) : t('lib_free')}</span>
              </div>
            );
          })}
          <RouterLink className="btn btn-sm" to="/settings#keys"><KeyRound size={14} /> {t('lib_add_keys')}</RouterLink>
        </div>
      </div>
    </section>
  );
}

export default function Library() {
  const ex = useExample();
  const { t } = useI18n();
  const [q, setQ] = useState('');
  const [query, setQuery] = useState('');
  const items = useLoad(() => api.get(`/api/media${query ? `?q=${encodeURIComponent(query)}` : ''}`), [query]);
  const [tags, setTags] = useState('');
  const [links, setLinks] = useState(false);
  const [editing, setEditing] = useState(null);
  const [busy, run] = useAction();
  const fileRef = useRef(null);
  const sel = useSelection(items.data);

  const upload = (files) => {
    if (!files?.length) return;
    run('upload', async () => {
      const fd = new FormData();
      [...files].forEach((f) => fd.append('files', f));
      fd.append('tags', tags);
      const res = await api.post('/api/media/upload', fd);
      items.reload(true);
      if (res.errors?.length) throw new Error(res.errors.map((e) => `${e.name}: ${e.error}`).join(' — '));
    }, t('uploaded'));
  };
  const remove = (a) => window.confirm(t('confirm_delete')) &&
    run(`del-${a.id}`, async () => { await api.del(`/api/media/${a.id}`); items.reload(true); });
  const bulk = () => run('bulk-delete', async () => {
    await api.post('/api/media/bulk-delete', { ids: sel.ids });
    sel.clear();
    items.reload(true);
  }, t('done'));

  if (items.loading && !items.data) return <Loading />;
  const list = items.data || [];

  return (
    <>
      <PageHead title={t('library_title')} sub={t('library_sub')}>
        <Button icon={Link2} onClick={() => setLinks(true)}>{t('add_links')}</Button>
        <Button variant="primary" icon={Upload} busy={busy === 'upload'} onClick={() => fileRef.current?.click()}>{t('upload_photos')}</Button>
        <input ref={fileRef} type="file" accept="image/*" multiple hidden
          onChange={(e) => { upload(e.target.files); e.target.value = ''; }} />
      </PageHead>
      {items.error && <ErrorBox error={items.error} onRetry={items.reload} />}
      <ConnectedLibraries onImported={() => items.reload(true)} />

      <div className="card card-pad" style={{ marginBottom: 16 }}>
        <div className="grid grid-2">
          <Field label={t('tags_for_upload')} hint={t('tags_hint')}>
            <input className="input" value={tags} onChange={(e) => setTags(e.target.value)} placeholder={ex('tags')} />
          </Field>
          <Field label={t('search_photos')}>
            <form className="row" style={{ flexWrap: 'nowrap', gap: 8 }} onSubmit={(e) => { e.preventDefault(); setQuery(q.trim()); }}>
              <input className="input" value={q} onChange={(e) => setQ(e.target.value)} />
              <Button type="submit" icon={Search} />
            </form>
          </Field>
        </div>
        <p className="xs muted" style={{ marginBottom: 0 }}>{t('library_hint')}</p>
      </div>

      {list.length > 0 && (
        <div className="row" style={{ marginBottom: 10 }}>
          <SelectAll sel={sel} label={t('select_all')} />
          <span className="xs muted">{list.length} {t('photos')}</span>
        </div>
      )}
      {list.length === 0 ? <Empty icon={Images}>{t('library_empty')}</Empty> : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 12 }}>
          {list.map((a) => (
            <div key={a.id} className="card" style={{ overflow: 'hidden', outline: sel.has(a.id) ? '2px solid var(--accent, #c6a23c)' : 'none' }}>
              <div style={{ position: 'relative', aspectRatio: '4 / 5', background: 'var(--surface-2, #eee)' }}>
                <img src={mediaUrl(a.url)} alt={a.title} loading="lazy"
                  style={{ width: '100%', height: '100%', objectFit: 'cover', cursor: 'pointer' }} onClick={() => setEditing(a)} />
                <label style={{ position: 'absolute', top: 8, insetInlineStart: 8, background: 'rgba(255,255,255,.85)', borderRadius: 6, padding: '2px 4px' }}>
                  <input type="checkbox" checked={sel.has(a.id)} onChange={() => sel.toggle(a.id)} />
                </label>
                {a.used_count > 0 && <span className="pill" style={{ position: 'absolute', bottom: 8, insetInlineStart: 8 }}>{t('used')} {a.used_count}</span>}
              </div>
              <div style={{ padding: 8 }}>
                <div className="xs" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.title || '—'}</div>
                <div className="xs muted" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  <Tag size={10} /> {a.tags || t('no_tags')}
                </div>
                <div className="row" style={{ gap: 6, marginTop: 6 }}>
                  <Button size="sm" onClick={() => setEditing(a)}>{t('edit')}</Button>
                  <Button size="sm" variant="danger" icon={Trash2} busy={busy === `del-${a.id}`} onClick={() => remove(a)} />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
      <BulkBar sel={sel} busy={busy} selectedLabel={t('selected')} clearLabel={t('clear_selection')}
        actions={[{ key: 'delete', label: t('delete'), icon: Trash2, variant: 'danger', confirm: t('confirm_delete') }]}
        onAction={bulk} />
      {links && <LinksModal onClose={() => setLinks(false)} onDone={() => items.reload(true)} />}
      {editing && <EditModal asset={editing} onClose={() => setEditing(null)}
        onSaved={(a) => items.setData(list.map((x) => (x.id === a.id ? a : x)))} />}
    </>
  );
}
