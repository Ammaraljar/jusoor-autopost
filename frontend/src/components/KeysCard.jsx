import { useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, KeyRound, PlugZap, Save, Trash2, XCircle } from 'lucide-react';
import { Button, Field, Spinner, useAction, useLoad } from './ui';
import { api } from '../lib/api';
import { useI18n } from '../lib/i18n';

const ENGINE_ORDER = ['claude', 'gemini', 'deepseek', 'mistral', 'openrouter', 'groq', 'custom'];
const MODEL_FIELDS = ENGINE_ORDER.map((n) => `${n}_model`);
const PUBLISH_KEYS = [
  { field: 'pexels_api_key', label: 'stock_photos', hint: 'pexels.com/api' },
  { field: 'buffer_api_key', label: 'Buffer', hint: 'publish.buffer.com' },
  { field: 'meta_access_token', label: 'Meta (Facebook / Instagram)', hint: 'developers.facebook.com' },
  { field: 'uploadpost_api_key', label: 'upload-post.com', hint: 'upload-post.com' },
];

function KeyState({ state }) {
  const { t } = useI18n();
  if (!state?.set) return <span className="pill" style={{ alignSelf: 'flex-start' }}>{t('key_missing')}</span>;
  return (
    <span className="pill ok" style={{ alignSelf: 'flex-start' }}>
      {t('key_set')} {state.hint} · {state.source === 'dashboard' ? t('from_db') : t('from_env')}
    </span>
  );
}

function initialForm(v) {
  return {
    ai_mode: v.ai_mode || 'single',
    ai_primary: v.ai_primary || 'claude',
    ensemble: (v.ai_ensemble || '').split(',').map((x) => x.trim()).filter(Boolean),
    ...Object.fromEntries(MODEL_FIELDS.map((f) => [f, v[f] || ''])),
    custom_base_url: v.custom_base_url || '',
    secrets: {},
  };
}

export default function KeysCard({ onSaved }) {
  const { t } = useI18n();
  const creds = useLoad(() => api.get('/api/settings/credentials'), []);
  const [form, setForm] = useState(null);
  const [test, setTest] = useState(null);
  const [busy, run] = useAction();

  useEffect(() => { if (creds.data) setForm(initialForm(creds.data.values)); }, [creds.data]);
  if (!form) return <div className="card card-pad"><Spinner /></div>;

  const values = creds.data.values;
  const engines = values.engines || {};
  const ensembleMode = form.ai_mode === 'ensemble';
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const setSecret = (field, value) => setForm((f) => ({ ...f, secrets: { ...f.secrets, [field]: value } }));
  const toggleEnsemble = (name) => setForm((f) => ({
    ...f, ensemble: f.ensemble.includes(name) ? f.ensemble.filter((n) => n !== name) : [...f.ensemble, name],
  }));

  const payload = () => ({
    ai_mode: form.ai_mode, ai_primary: form.ai_primary, ai_ensemble: form.ensemble.join(','),
    ...Object.fromEntries(MODEL_FIELDS.map((f) => [f, form[f]])),
    custom_base_url: form.custom_base_url, ...form.secrets,
  });
  const initial = initialForm(values);
  const dirty = JSON.stringify({ ...form, secrets: {} }) !== JSON.stringify(initial)
    || Object.values(form.secrets).some(Boolean);

  const save = () => run('save', async () => {
    const res = await api.put('/api/settings/credentials', payload());
    creds.setData({ ...creds.data, values: res.values });
    setTest(null);
    onSaved?.();
  }, t('saved'));

  const clear = (field) => run(`clear-${field}`, async () => {
    const res = await api.put('/api/settings/credentials', { [field]: null });
    creds.setData({ ...creds.data, values: res.values });
    onSaved?.();
  }, t('saved'));

  const runTest = () => run('test', async () => {
    setTest(null);
    setTest(await api.post('/api/settings/credentials/test-ai'));
  });

  const secretInput = (field) => (
    <>
      <div className="row" style={{ flexWrap: 'nowrap', gap: 8 }}>
        <input className="input ltr" type="password" autoComplete="new-password" placeholder="••••••••"
          value={form.secrets[field] ?? ''} onChange={(e) => setSecret(field, e.target.value)} />
        {values[field]?.set && values[field]?.source === 'dashboard' && (
          <Button size="sm" variant="danger" icon={Trash2} busy={busy === `clear-${field}`}
            onClick={() => clear(field)} title={t('remove_key')} />
        )}
      </div>
      <KeyState state={values[field]} />
    </>
  );

  const engineBlock = (name) => {
    const info = engines[name] || {};
    return (
      <div key={name} className={`target ${info.ready ? 'on' : ''}`}>
        <div className="row" style={{ marginBottom: 10 }}>
          <b>{info.label}</b>
          <span className={`pill ${info.ready ? 'ok' : ''}`}>{info.ready ? t('ready') : t('not_ready')}</span>
          <div className="spacer" />
          {ensembleMode && (
            <label className="check small">
              <input type="checkbox" checked={form.ensemble.includes(name)} onChange={() => toggleEnsemble(name)} />
              {t('participates')}
            </label>
          )}
        </div>
        <div className="stack" style={{ gap: 10 }}>
          {name === 'custom' && (
            <Field label={t('base_url')} hint="https://…/api/v1/openai">
              <input className="input ltr" value={form.custom_base_url}
                onChange={(e) => set('custom_base_url', e.target.value)} />
            </Field>
          )}
          <Field label={t('model')} hint={name === 'custom' ? 'workspace slug' : info.default_model}>
            <input className="input ltr" value={form[`${name}_model`]} placeholder={info.default_model}
              onChange={(e) => set(`${name}_model`, e.target.value)} />
          </Field>
          <Field label={t('api_key')} hint={info.key_hint}>{secretInput(`${name}_api_key`)}</Field>
        </div>
      </div>
    );
  };

  return (
    <div className="card card-pad stack">
      <div>
        <h3><KeyRound size={16} /> {t('keys_title')}</h3>
        <p className="small muted" style={{ marginTop: -8 }}>{t('keys_sub')}</p>
      </div>

      <div className="grid grid-2">
        <Field label={t('ai_mode')}>
          <select className="select" value={form.ai_mode} onChange={(e) => set('ai_mode', e.target.value)}>
            <option value="single">{t('mode_single')}</option>
            <option value="ensemble">{t('mode_ensemble')}</option>
          </select>
        </Field>
        <Field label={ensembleMode ? t('primary_ensemble') : t('primary_single')}>
          <select className="select" value={form.ai_primary} onChange={(e) => set('ai_primary', e.target.value)}>
            {ENGINE_ORDER.map((n) => <option key={n} value={n}>{engines[n]?.label || n}</option>)}
          </select>
        </Field>
      </div>

      <b className="small">{t('engines')}</b>
      <div className="target-grid">{ENGINE_ORDER.map(engineBlock)}</div>

      {(values.warnings || []).map((w) => (
        <div key={w} className="banner warn small" style={{ margin: 0 }}><AlertTriangle size={16} /> {w}</div>
      ))}

      <div className="row">
        <Button variant="primary" icon={Save} busy={busy === 'save'} disabled={!dirty} onClick={save}>{t('save')}</Button>
        <Button icon={PlugZap} busy={busy === 'test'} disabled={dirty} onClick={runTest}>{t('test_connection')}</Button>
        {dirty && <span className="xs muted">{t('save_first')}</span>}
      </div>
      {test && (test.engines || []).map((r) => (
        <div key={r.engine} className={`banner ${r.ok ? 'ok' : 'danger'} small`} style={{ margin: 0 }}>
          {r.ok ? <CheckCircle2 size={16} /> : <XCircle size={16} />}
          <div>
            <b>{r.label}</b> <span className="code">{r.model}</span> — {r.ok ? t('connection_ok') : t('connection_failed')}
            <div>{r.ok ? r.reply : r.error}</div>
          </div>
        </div>
      ))}

      <div className="divider" />
      <b className="small">{t('publishers_keys')}</b>
      {PUBLISH_KEYS.map(({ field, label, hint }) => (
        <Field key={field} label={t(label) === label ? label : t(label)} hint={hint}>{secretInput(field)}</Field>
      ))}
      <p className="xs muted">{t('key_hint')}</p>
      <div>
        <Button variant="primary" icon={Save} busy={busy === 'save'} disabled={!dirty} onClick={save}>{t('save')}</Button>
      </div>
    </div>
  );
}
