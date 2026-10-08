import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Pencil, Plus, Target, Trash2 } from 'lucide-react';
import { BulkBar, Button, Empty, ErrorBox, Field, Loading, Modal, PageHead, SelectAll, useAction, useLoad, useSelection } from '../components/ui';
import { api } from '../lib/api';
import { fmtDate } from '../lib/format';
import { useExample } from '../lib/useExample';
import { useI18n } from '../lib/i18n';

export default function Campaigns() {
  const { t, lang } = useI18n();
  const list = useLoad(() => api.get('/api/campaigns'), []);
  const [editing, setEditing] = useState(null);
  const [busy, run] = useAction();
  const sel = useSelection(list.data);

  if (list.loading && !list.data) return <Loading />;
  const bulkDelete = () => run('bulk-delete', async () => {
    await api.post('/api/campaigns/bulk-delete', { ids: sel.ids });
    sel.clear();
    list.reload(true);
  }, t('done'));
  return (
    <>
      <PageHead title={t('campaigns_title')} sub={t('campaigns_sub')}>
        <Button variant="primary" icon={Plus} onClick={() => setEditing({})}>{t('add_campaign')}</Button>
      </PageHead>
      {list.error && <ErrorBox error={list.error} onRetry={list.reload} />}
      {list.data?.length > 0 && <div className="select-row"><SelectAll sel={sel} label={t('select_all')} /></div>}
      <BulkBar sel={sel} busy={busy} onAction={bulkDelete} selectedLabel={t('selected')} clearLabel={t('clear_selection')}
        actions={[{ key: 'delete', label: t('delete_forever'), icon: Trash2, variant: 'danger', confirm: t('confirm_bulk_delete') }]} />
      {list.data?.length === 0 && <div className="card"><Empty icon={Target}>{t('add_campaign')}</Empty></div>}
      <div className="grid grid-3">
        {list.data?.map((c) => (
          <div key={c.id} className="card card-pad stack" style={{ borderTop: `5px solid ${c.color}`,
            outline: sel.has(c.id) ? '3px solid var(--gold)' : undefined }}>
            <div className="row">
              <input type="checkbox" checked={sel.has(c.id)} onChange={() => sel.toggle(c.id)} aria-label={t('select')} />
              <h3 style={{ margin: 0 }}>{c.name}</h3>
              <div className="spacer" />
              <button className="btn btn-sm btn-ghost icon-btn" onClick={() => setEditing(c)} aria-label={t('edit')}><Pencil size={15} /></button>
              <button className="btn btn-sm btn-ghost btn-danger icon-btn" aria-label={t('delete')}
                onClick={() => window.confirm(t('confirm_delete')) && run(c.id, async () => { await api.del(`/api/campaigns/${c.id}`); list.reload(true); })}>
                <Trash2 size={15} />
              </button>
            </div>
            {c.objective && <p className="small muted">{c.objective}</p>}
            <div className="small">
              {c.start_date ? fmtDate(c.start_date, lang) : '—'} – {c.end_date ? fmtDate(c.end_date, lang) : '—'}
            </div>
            <div className="grid grid-4" style={{ gap: 8 }}>
              {[['drafts', c.stats.drafts], ['scheduled', c.stats.scheduled], ['published', c.stats.published], ['planned', c.stats.planned]].map(([k, v]) => (
                <div key={k} style={{ textAlign: 'center' }}>
                  <div className="bold" style={{ fontSize: 20 }}>{v}</div>
                  <div className="xs muted">{t(k)}</div>
                </div>
              ))}
            </div>
            <Link className="btn btn-sm" to={`/?status=all&campaign=${c.id}`}>{t('view_posts')}</Link>
          </div>
        ))}
      </div>
      {editing && <CampaignModal item={editing} onClose={() => setEditing(null)}
        onSaved={() => { setEditing(null); list.reload(true); }} />}
    </>
  );
}

function CampaignModal({ item, onClose, onSaved }) {
  const ex = useExample();
  const { t } = useI18n();
  const [f, setF] = useState({ name: '', objective: '', color: '#C6A23C', start_date: '', end_date: '', notes: '', ...item });
  const [busy, run] = useAction();
  const set = (k, v) => setF((x) => ({ ...x, [k]: v }));
  const save = () => run('save', async () => {
    const body = { name: f.name, objective: f.objective, color: f.color, notes: f.notes || '',
      start_date: f.start_date || null, end_date: f.end_date || null };
    if (item.id) await api.patch(`/api/campaigns/${item.id}`, body);
    else await api.post('/api/campaigns', body);
    onSaved();
  }, t('saved'));

  return (
    <Modal title={item.id ? t('edit') : t('add_campaign')} onClose={onClose} footer={<>
      <Button onClick={onClose}>{t('cancel')}</Button>
      <Button variant="primary" busy={busy === 'save'} disabled={f.name.trim().length < 2} onClick={save}>{t('save')}</Button>
    </>}>
      <div className="stack">
        <div className="grid grid-2">
          <Field label={t('name')}><input className="input" value={f.name} placeholder={ex('campaign')} onChange={(e) => set('name', e.target.value)} autoFocus /></Field>
          <Field label={t('color')}><input className="input" type="color" value={f.color} onChange={(e) => set('color', e.target.value)} /></Field>
        </div>
        <Field label={t('objective')}>
          <textarea className="textarea" rows={2} value={f.objective} placeholder={ex('objective')} onChange={(e) => set('objective', e.target.value)} />
        </Field>
        <div className="grid grid-2">
          <Field label={t('start')}><input className="input" type="date" value={f.start_date || ''} onChange={(e) => set('start_date', e.target.value)} /></Field>
          <Field label={t('end')}><input className="input" type="date" value={f.end_date || ''} onChange={(e) => set('end_date', e.target.value)} /></Field>
        </div>
        <Field label={t('notes')}>
          <textarea className="textarea" rows={2} value={f.notes || ''} onChange={(e) => set('notes', e.target.value)} />
        </Field>
      </div>
    </Modal>
  );
}
