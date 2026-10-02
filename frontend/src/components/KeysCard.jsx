import { useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, KeyRound, PlugZap, Save, Trash2, XCircle } from 'lucide-react';
import { Button, Field, Spinner, useAction, useLoad } from './ui';
import { api } from '../lib/api';
import { useI18n } from '../lib/i18n';

const ENGINE_ORDER = ['gemini', 'mistral', 'groq', 'cloudflare', 'openrouter'];
const EXTRA_FIELDS = ['cloudflare_account_id'];
const MODEL_FIELDS = ENGINE_ORDER.map((n) => `${n}_model`);
const PUBLISH_KEYS = [
  { field: 'pexels_api_key', label: 'stock_photos', hint: 'pexels.com/api' },
  { field: 'pixabay_api_key', label: 'Pixabay', hint: 'pixabay.com/api/docs' },
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

const CUSTOM = '__custom__';

function initialForm(v) {
  return {
    ai_mode: v.ai_mode || 'single',
    ai_primary: v.ai_primary || 'mistral',
    ...Object.fromEntries(MODEL_FIELDS.map((f) => [f, v[f] || ''])),
    ...Object.fromEntries(EXTRA_FIELDS.map((f) => [f, v[f] || ''])),
    secrets: {},
  };
}

export default function KeysCard({ onSaved }) {
  const { t } = useI18n();
  const creds = useLoad(() => api.get('/api/settings/credentials'), []);
  const [form, setForm] = useState(null);
  const [test, setTest] = useState(null);
  const [customModel, setCustomModel] = useState({});
  const [liveModels, setLiveModels] = useState({});
  const [modelsError, setModelsError] = useState({});
  const [busy, run] = useAction();

  useEffect(() => { if (creds.data) setForm(initialForm(creds.data.values)); }, [creds.data]);
  if (!form) return <div className="card card-pad"><Spinner /></div>;

  const values = creds.data.values;
  const engines = values.engines || {};
  const outdated = !engines.mistral;                 // the server still runs a release without these engines
  const ensembleMode = form.ai_mode === 'ensemble';
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const setSecret = (field, value) => setForm((f) => ({ ...f, secrets: { ...f.secrets, [field]: value } }));

  // An engine is active when it has a saved key, or a key typed in this form
  const hasKey = (n) => Boolean(values[`${n}_api_key`]?.set || (form.secrets[`${n}_api_key`] || '').trim())
    && (engines[n]?.extra || []).every((x) => (form[x.field] || '').trim());
  const active = ENGINE_ORDER.filter(hasKey);
  const primary = active.includes(form.ai_primary) ? form.ai_primary : (active[0] || form.ai_primary);

  const payload = () => ({
    ai_mode: form.ai_mode, ai_primary: primary,
    ...Object.fromEntries(MODEL_FIELDS.map((f) => [f, form[f]])),
    ...Object.fromEntries(EXTRA_FIELDS.map((f) => [f, (form[f] || '').trim()])),
    ...form.secrets,
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

  const fetchModels = (name) => run(`models-${name}`, async () => {
    setModelsError((e) => ({ ...e, [name]: '' }));
    try {
      const res = await api.get(`/api/settings/credentials/models/${name}`);
      setLiveModels((m) => ({ ...m, [name]: res.models || [] }));
    } catch (err) {
      setModelsError((e) => ({ ...e, [name]: err.message || String(err) }));
    }
  });

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
    const on = hasKey(name);
    const field = `${name}_model`;
    const suggested = info.models || [];
    const live = liveModels[name];
    const models = live
      ? [...suggested.filter((m) => live.includes(m.id)),
        ...live.filter((id) => !suggested.some((m) => m.id === id)).map((id) => ({ id, note: t('from_account') }))]
      : suggested;
    const current = form[field] || info.default_model || '';
    const known = models.some((m) => m.id === current);
    const showCustom = customModel[name] || (current && !known);
    const typed = (form.secrets[`${name}_api_key`] || '').trim();
    const badPrefix = typed && info.key_prefix && !typed.startsWith(info.key_prefix);
    return (
      <div key={name} className={`target ${on ? 'on' : ''}`} style={on ? {} : { opacity: 0.85 }}>
        <div className="row" style={{ marginBottom: 6 }}>
          <b>{info.label}</b>
          <span className={`pill ${on ? 'ok' : ''}`}>{on ? t('engine_on') : t('engine_off')}</span>
          {on && primary === name && <span className="pill gold">{ensembleMode ? t('judge') : t('primary')}</span>}
          <div className="spacer" />
          {info.key_url && <a className="xs" href={info.key_url} target="_blank" rel="noreferrer">{t('get_key')}</a>}
        </div>
        {info.free && <p className="xs muted" style={{ margin: '0 0 10px' }}>{info.free}</p>}
        <div className="stack" style={{ gap: 10 }}>
          {(info.extra || []).map((x) => (
            <Field key={x.field} label={x.label} hint={x.hint}>
              <input className="input ltr" value={form[x.field] || ''} onChange={(e) => set(x.field, e.target.value)} />
            </Field>
          ))}
          <Field label={t('api_key')}>
            <>
              <div className="row" style={{ flexWrap: 'nowrap', gap: 8 }}>
                <input className="input ltr" type="password" autoComplete="new-password"
                  placeholder={info.key_placeholder || '••••••••'}
                  value={form.secrets[`${name}_api_key`] ?? ''} onChange={(e) => setSecret(`${name}_api_key`, e.target.value)} />
                {values[`${name}_api_key`]?.set && values[`${name}_api_key`]?.source === 'dashboard' && (
                  <Button size="sm" variant="danger" icon={Trash2} busy={busy === `clear-${name}_api_key`}
                    onClick={() => clear(`${name}_api_key`)} title={t('remove_key')} />
                )}
              </div>
              <KeyState state={values[`${name}_api_key`]} />
              {badPrefix && <span className="xs" style={{ color: 'var(--warn)' }}>{t('key_prefix_warn')} {info.key_prefix}</span>}
            </>
          </Field>
          <Field label={t('model')}>
            <>
              <select className="select ltr" value={showCustom ? CUSTOM : current}
                onChange={(e) => {
                  if (e.target.value === CUSTOM) { setCustomModel((c) => ({ ...c, [name]: true })); return; }
                  setCustomModel((c) => ({ ...c, [name]: false }));
                  set(field, e.target.value);
                }}>
                {models.map((m) => <option key={m.id} value={m.id}>{m.id} — {m.note}</option>)}
                <option value={CUSTOM}>{t('other_model')}</option>
              </select>
              {values[`${name}_api_key`]?.set && (
                <div className="row" style={{ gap: 8, marginTop: 6 }}>
                  <Button size="sm" busy={busy === `models-${name}`} onClick={() => fetchModels(name)}>{t('fetch_models')}</Button>
                  {live && <span className="xs muted">{live.length} {t('models_available')}</span>}
                </div>
              )}
              {modelsError[name] && <span className="xs" style={{ color: 'var(--danger)' }}>{modelsError[name]}</span>}
              {showCustom && (
                <input className="input ltr" style={{ marginTop: 6 }} value={form[field]}
                  placeholder={name === 'openrouter' ? 'vendor/model:free' : info.default_model}
                  onChange={(e) => set(field, e.target.value)} />
              )}
            </>
          </Field>
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

      {outdated && (
        <div className="banner danger small" style={{ margin: 0 }}>
          <AlertTriangle size={16} /> {t('server_outdated')}
        </div>
      )}

      <b className="small">{t('engines')}</b>
      <div className="target-grid">{ENGINE_ORDER.map(engineBlock)}</div>

      <div className="grid grid-2">
        <Field label={t('ai_mode')}>
          <select className="select" value={form.ai_mode} onChange={(e) => set('ai_mode', e.target.value)}>
            <option value="single">{t('mode_single')}</option>
            <option value="ensemble">{t('mode_ensemble')}</option>
          </select>
        </Field>
        <Field label={ensembleMode ? t('primary_ensemble') : t('primary_single')}>
          {active.length ? (
            <select className="select" value={primary} onChange={(e) => set('ai_primary', e.target.value)}>
              {active.map((n) => <option key={n} value={n}>{engines[n]?.label || n}</option>)}
            </select>
          ) : <span className="small muted">{t('no_engine_key')}</span>}
        </Field>
      </div>
      <p className="xs muted" style={{ marginTop: -6 }}>
        {active.length === 0 ? t('no_engine_key')
          : ensembleMode
            ? `${t('ensemble_auto')} ${active.map((n) => engines[n]?.label).join(' + ')}`
            : `${t('single_auto')} ${active.filter((n) => n !== primary).map((n) => engines[n]?.label).join('، ') || '—'}`}
      </p>

      {(values.warnings || []).map((w) => (
        <div key={w} className="banner warn small" style={{ margin: 0 }}><AlertTriangle size={16} /> {w}</div>
      ))}

      <div className="row">
        <Button variant="primary" icon={Save} busy={busy === 'save'} disabled={!dirty || outdated} onClick={save}>{t('save')}</Button>
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
        <Button variant="primary" icon={Save} busy={busy === 'save'} disabled={!dirty || outdated} onClick={save}>{t('save')}</Button>
      </div>
    </div>
  );
}
