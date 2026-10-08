import { useRef, useState } from 'react';
import { Images, Link2, Search, Tag, Trash2, Upload } from 'lucide-react';
import { BulkBar, Button, Empty, ErrorBox, Field, Loading, Modal, PageHead, SelectAll, useAction, useLoad, useSelection } from '../components/ui';
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
