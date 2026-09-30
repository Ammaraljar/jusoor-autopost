import { useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, KeyRound, PlugZap, Save, Trash2, XCircle } from 'lucide-react';
import { Button, Field, Spinner, useAction, useLoad } from './ui';
import { api } from '../lib/api';
import { useI18n } from '../lib/i18n';

const SECRET_FIELDS = [
  { field: 'pexels_api_key', label: 'stock_photos', hint: 'pexels.com/api' },
  { field: 'buffer_api_key', label: 'Buffer', hint: 'publish.buffer.com' },
  { field: 'meta_access_token', label: 'Meta (Facebook / Instagram)', hint: 'developers.facebook.com' },
  { field: 'uploadpost_api_key', label: 'upload-post.com', hint: 'upload-post.com' },
];

/** Status chip for a write-only secret. */
function KeyState({ state }) {
  const { t } = useI18n();
  if (!state?.set) return <span className="pill" style={{ alignSelf: 'flex-start' }}>{t('key_missing')}</span>;
  return (
    <span className="pill ok" style={{ alignSelf: 'flex-start' }}>
      {t('key_set')} {state.hint} · {state.source === 'dashboard' ? t('from_db') : t('from_env')}
    </span>
  );
}

export default function KeysCard({ onSaved }) {
  const { t } = useI18n();
  const creds = useLoad(() => api.get('/api/settings/credentials'), []);
  const [form, setForm] = useState(null);
  const [busy, run] = useAction();
  const [test, setTest] = useState(null);

  useEffect(() => {
    if (creds.data) {
      const v = creds.data.values;
      setForm({ ai_provider: v.ai_provider || 'anthropic', ai_base_url: v.ai_base_url || '',
                ai_model: v.ai_model || '', secrets: {} });
    }
  }, [creds.data]);

  if (!form) return <div className="card card-pad"><Spinner /></div>;
  const values = creds.data.values;
  const openaiCompatible = form.ai_provider === 'openai_compatible';
  const setSecret = (field, value) => setForm((f) => ({ ...f, secrets: { ...f.secrets, [field]: value } }));

  const save = () => run('save', async () => {
    const payload = { ai_provider: form.ai_provider, ai_base_url: form.ai_base_url, ai_model: form.ai_model,
                      ...form.secrets };
    const res = await api.put('/api/settings/credentials', payload);
    creds.setData({ ...creds.data, values: res.values });
    setForm((f) => ({ ...f, secrets: {} }));
    onSaved?.();
  }, t('saved'));

  const dirty = form && creds.data && (
    form.ai_provider !== (creds.data.values.ai_provider || 'anthropic')
    || form.ai_base_url !== (creds.data.values.ai_base_url || '')
    || form.ai_model !== (creds.data.values.ai_model || '')
    || Object.values(form.secrets).some(Boolean));

  const runTest = () => run('test', async () => {
    setTest(null);
    setTest(await api.post('/api/settings/credentials/test-ai'));
  });

  const clear = (field) => run(`clear-${field}`, async () => {
    const res = await api.put('/api/settings/credentials', { [field]: null });
    creds.setData({ ...creds.data, values: res.values });
    onSaved?.();
  }, t('saved'));

  const secretRow = ({ field, label, hint }) => (
    <Field key={field} label={t(label) === label ? label : t(label)} hint={hint}>
      <div className="row" style={{ flexWrap: 'nowrap', gap: 8 }}>
        <input className="input ltr" type="password" autoComplete="new-password" placeholder="••••••••"
          value={form.secrets[field] ?? ''} onChange={(e) => setSecret(field, e.target.value)} />
        {values[field]?.set && values[field]?.source === 'dashboard' && (
          <Button size="sm" variant="danger" icon={Trash2} busy={busy === `clear-${field}`}
            onClick={() => clear(field)} title={t('remove_key')} />
        )}
      </div>
      <KeyState state={values[field]} />
    </Field>
  );

  return (
    <div className="card card-pad stack">
      <div>
        <h3><KeyRound size={16} /> {t('keys_title')}</h3>
        <p className="small muted" style={{ marginTop: -8 }}>{t('keys_sub')}</p>
      </div>

      <b className="small">{t('ai_engine')}</b>
      <Field label={t('provider')}>
        <select className="select" value={form.ai_provider}
          onChange={(e) => setForm((f) => ({ ...f, ai_provider: e.target.value }))}>
          <option value="anthropic">{t('anthropic')}</option>
          <option value="openai_compatible">{t('openai_compatible')}</option>
        </select>
      </Field>
      {openaiCompatible && (
        <div className="grid grid-2">
          <Field label={t('base_url')} hint="https://…/api/v1/openai">
            <input className="input ltr" value={form.ai_base_url}
              onChange={(e) => setForm((f) => ({ ...f, ai_base_url: e.target.value }))} />
          </Field>
          <Field label={t('model')} hint="workspace slug">
            <input className="input ltr" value={form.ai_model}
              onChange={(e) => setForm((f) => ({ ...f, ai_model: e.target.value }))} />
          </Field>
        </div>
      )}
      {!openaiCompatible && (
        <Field label={t('model')} hint="claude-sonnet-5">
          <input className="input ltr" value={form.ai_model} placeholder="claude-sonnet-5"
            onChange={(e) => setForm((f) => ({ ...f, ai_model: e.target.value }))} />
        </Field>
      )}
      {secretRow({ field: 'ai_api_key', label: 'api_key',
                   hint: openaiCompatible ? 'AnythingLLM API key' : 'console.anthropic.com → sk-ant-…' })}

      {(values.warnings || []).map((w) => (
        <div key={w} className="banner warn small" style={{ margin: 0 }}><AlertTriangle size={16} /> {w}</div>
      ))}

      <div className="row">
        <Button size="sm" icon={PlugZap} busy={busy === 'test'} disabled={dirty} onClick={runTest}>
          {t('test_connection')}
        </Button>
        {dirty && <span className="xs muted">{t('save_first')}</span>}
      </div>
      {test && (
        <div className={`banner ${test.ok ? 'ok' : 'danger'} small`} style={{ margin: 0 }}>
          {test.ok ? <CheckCircle2 size={16} /> : <XCircle size={16} />}
          <div>
            <b>{test.ok ? t('connection_ok') : t('connection_failed')}</b>
            <div>{test.ok ? `${test.model} — ${test.reply}` : test.error}</div>
          </div>
        </div>
      )}

      <div className="divider" />
      <b className="small">{t('publishers_keys')}</b>
      {SECRET_FIELDS.map(secretRow)}

      <p className="xs muted">{t('key_hint')}</p>
      <div>
        <Button variant="primary" icon={Save} busy={busy === 'save'} onClick={save}>{t('save')}</Button>
      </div>
    </div>
  );
}
