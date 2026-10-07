import { useEffect, useState } from 'react';
import { Building2, ExternalLink, Pause, Play, Plus } from 'lucide-react';
import KeysCard from '../components/KeysCard';
import { Button, ErrorBox, Field, Loading, Modal, PageHead, useAction, useLoad } from '../components/ui';
import { api, setActingOrg } from '../lib/api';
import { fmtDate } from '../lib/format';
import { DIALECTS, LANGUAGES, useI18n } from '../lib/i18n';


function NewOrgModal({ industries, onClose, onSaved }) {
  const { t, lang } = useI18n();
  const [f, setF] = useState({ name: '', industry: 'general', language: 'ar', dialect: 'msa', owner_name: '',
    owner_email: '', owner_password: '', max_users: 10 });
  const [busy, run] = useAction();
  const set = (k, v) => setF((x) => ({ ...x, [k]: v }));
  const save = () => run('save', async () => {
    await api.post('/api/admin/orgs', { ...f, dialect: f.language === 'ar' ? f.dialect : null,
      max_users: Number(f.max_users) || 10 });
    onSaved();
    onClose();
  }, t('saved'));
  return (
    <Modal title={t('new_company')} onClose={onClose} footer={(
      <>
        <Button onClick={onClose}>{t('cancel')}</Button>
        <Button variant="primary" busy={busy === 'save'} disabled={!f.name || !f.owner_email || f.owner_password.length < 8}
          onClick={save}>{t('create_company')}</Button>
      </>
    )}>
      <div className="stack">
        <Field label={t('company_name')}><input className="input" value={f.name} onChange={(e) => set('name', e.target.value)} /></Field>
        <div className="grid grid-2">
          <Field label={t('industry')}>
            <select className="select" value={f.industry} onChange={(e) => set('industry', e.target.value)}>
              {industries.map((i) => <option key={i.id} value={i.id}>{i[lang] || i.en}</option>)}
            </select>
          </Field>
          <Field label={t('content_language')}>
            <select className="select" value={f.language} onChange={(e) => set('language', e.target.value)}>
              {LANGUAGES.map((l) => <option key={l.id} value={l.id}>{l.label}</option>)}
            </select>
          </Field>
          {f.language === 'ar' && (
            <Field label={t('dialect')}>
              <select className="select" value={f.dialect} onChange={(e) => set('dialect', e.target.value)}>
                {DIALECTS.map((o) => <option key={o} value={o}>{t(`dialect_${o}`)}</option>)}
              </select>
            </Field>
          )}
          <Field label={t('max_users')}>
            <input className="input" type="number" min={1} max={500} value={f.max_users} onChange={(e) => set('max_users', e.target.value)} />
          </Field>
        </div>
        <div className="divider" />
        <b className="small">{t('owner_account')}</b>
        <Field label={t('your_name')}><input className="input" value={f.owner_name} onChange={(e) => set('owner_name', e.target.value)} /></Field>
        <Field label={t('email')}><input className="input ltr" type="email" value={f.owner_email} onChange={(e) => set('owner_email', e.target.value)} /></Field>
        <Field label={t('temp_password')} hint={t('temp_password_hint')}>
          <input className="input ltr" autoComplete="new-password" value={f.owner_password} onChange={(e) => set('owner_password', e.target.value)} />
        </Field>
      </div>
    </Modal>
  );
}

export default function Admin() {
  const { t, lang } = useI18n();
  const orgs = useLoad(() => api.get('/api/admin/orgs'), []);
  const [industries, setIndustries] = useState([]);
  const [adding, setAdding] = useState(false);
  const [busy, run] = useAction();
  useEffect(() => { api.get('/api/auth/industries').then(setIndustries).catch(() => {}); }, []);

  if (orgs.loading && !orgs.data) return <Loading />;
  const label = (id) => {
    const i = industries.find((x) => x.id === id);
    return i ? (i[lang] || i.en) : id;
  };
  const patch = (o, body) => run(`p-${o.id}`, async () => { await api.patch(`/api/admin/orgs/${o.id}`, body); orgs.reload(true); }, t('saved'));
  const open = (o) => { setActingOrg(o.id); window.location.assign('/'); };

  return (
    <>
      <PageHead title={t('admin_title')} sub={t('admin_sub')}>
        <Button variant="primary" icon={Plus} onClick={() => setAdding(true)}>{t('new_company')}</Button>
      </PageHead>
      {orgs.error && <ErrorBox error={orgs.error} onRetry={orgs.reload} />}

      <div className="stack" style={{ marginBottom: 20 }}>
        {(orgs.data || []).map((o) => (
          <div key={o.id} className="card card-pad row" style={{ opacity: o.status === 'active' ? 1 : 0.65 }}>
            <Building2 size={20} />
            <div style={{ minWidth: 0, flex: '1 1 220px' }}>
              <b>{o.name}</b> <span className="pill">{label(o.industry)}</span>
              {o.status !== 'active' && <span className="pill">{t('suspended')}</span>}
              <div className="xs muted">
                #{o.id} · {o.language === 'ar' ? 'العربية' : 'English'} · {o.users} {t('users')} · {o.sources} {t('nav_sources')} · {o.drafts} {t('posts')}
                {o.created_at ? ` · ${fmtDate(o.created_at, lang)}` : ''}
              </div>
            </div>
            <label className="xs row" style={{ gap: 6 }}>
              {t('max_users')}
              <input className="input" type="number" min={1} max={500} style={{ width: 80 }} defaultValue={o.max_users || 10}
                onBlur={(e) => Number(e.target.value) !== o.max_users && patch(o, { max_users: Number(e.target.value) })} />
            </label>
            <Button size="sm" icon={ExternalLink} onClick={() => open(o)}>{t('open_company')}</Button>
            <Button size="sm" icon={o.status === 'active' ? Pause : Play} busy={busy === `p-${o.id}`}
              variant={o.status === 'active' ? 'danger' : ''}
              onClick={() => (o.status !== 'active' || window.confirm(t('confirm_suspend')))
                && patch(o, { status: o.status === 'active' ? 'suspended' : 'active' })}>
              {o.status === 'active' ? t('suspend') : t('activate')}
            </Button>
          </div>
        ))}
      </div>

      <KeysCard platform />
      {adding && <NewOrgModal industries={industries} onClose={() => setAdding(false)} onSaved={() => orgs.reload(true)} />}
    </>
  );
}
