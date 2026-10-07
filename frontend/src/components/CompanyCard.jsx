import { useEffect, useState } from 'react';
import { Building2, Save } from 'lucide-react';
import { Button, Field, Spinner, useAction, useLoad } from './ui';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { DIALECTS, LANGUAGES, useI18n } from '../lib/i18n';


/** The company profile: its field decides the AI's audience, tone, rules and photo keywords. */
export default function CompanyCard({ onSaved }) {
  const { t, lang } = useI18n();
  const { refresh } = useAuth();
  const org = useLoad(() => api.get('/api/org'), []);
  const [f, setF] = useState(null);
  const [applyDefaults, setApplyDefaults] = useState(true);
  const [busy, run] = useAction();
  useEffect(() => {
    if (org.data) setF({ name: org.data.name, industry: org.data.industry, language: org.data.language, dialect: org.data.dialect || 'msa' });
  }, [org.data]);
  if (!f) return <div className="card card-pad"><Spinner /></div>;
  const set = (k, v) => setF((x) => ({ ...x, [k]: v }));
  const changedField = f.industry !== org.data.industry || f.language !== org.data.language;
  const save = () => run('org', async () => {
    const res = await api.patch('/api/org', { ...f, dialect: f.language === 'ar' ? f.dialect : '',
      apply_industry_defaults: changedField && applyDefaults });
    org.setData({ ...org.data, ...res });
    refresh().catch(() => {});
    onSaved?.();
  }, t('saved'));

  return (
    <div className="card card-pad stack">
      <h3><Building2 size={16} /> {t('company_profile')}</h3>
      <p className="small muted" style={{ marginTop: -8 }}>{t('company_profile_sub')}</p>
      <Field label={t('company_name')}><input className="input" value={f.name} onChange={(e) => set('name', e.target.value)} /></Field>
      <div className="grid grid-2">
        <Field label={t('industry')}>
          <select className="select" value={f.industry} onChange={(e) => set('industry', e.target.value)}>
            {(org.data.industries || []).map((i) => <option key={i.id} value={i.id}>{i[lang] || i.en}</option>)}
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
      </div>
      {changedField && (
        <label className="check small">
          <input type="checkbox" checked={applyDefaults} onChange={(e) => setApplyDefaults(e.target.checked)} /> {t('apply_industry_defaults')}
        </label>
      )}
      <div><Button variant="primary" icon={Save} busy={busy === 'org'} onClick={save}>{t('save')}</Button></div>
    </div>
  );
}
