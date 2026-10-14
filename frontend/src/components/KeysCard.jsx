import { useEffect, useState } from 'react';
import { AlertTriangle, Bot, CheckCircle2, Image as ImageIcon, KeyRound, ListChecks, PlugZap, RefreshCw, Send, Star, XCircle } from 'lucide-react';
import { Button, ConnCard, Field, SaveBar, SecretField, Spinner, useAction, useLoad } from './ui';
import { api } from '../lib/api';
import { useI18n } from '../lib/i18n';

const DEFAULT_ORDER = ['gemini', 'claude', 'openai', 'mistral', 'groq', 'deepseek', 'kimi', 'grok', 'qwen', 'cloudflare', 'openrouter'];
const EXTRA_FIELDS = ['cloudflare_account_id'];
const PHOTO_KEYS = [
  { field: 'pexels_api_key', name: 'Pexels', url: 'https://www.pexels.com/api/' },
  { field: 'pixabay_api_key', name: 'Pixabay', url: 'https://pixabay.com/api/docs/' },
  { field: 'unsplash_api_key', name: 'Unsplash', url: 'https://unsplash.com/oauth/applications' },
];
const PUBLISH_KEYS = [
  { field: 'buffer_api_key', provider: 'buffer', name: 'Buffer', url: 'https://publish.buffer.com/settings/api' },
  { field: 'meta_access_token', provider: 'meta', name: 'Meta (Facebook / Instagram)', url: 'https://developers.facebook.com/tools/explorer/' },
  { field: 'uploadpost_api_key', provider: 'uploadpost', name: 'upload-post.com', url: 'https://app.upload-post.com/' },
];
const CUSTOM = '__custom__';

function initialForm(v, order) {
  return {
    ai_mode: v.ai_mode || 'single',
    ai_primary: v.ai_primary || 'mistral',
    ...Object.fromEntries(order.map((n) => [`${n}_model`, v[`${n}_model`] || ''])),
    ...Object.fromEntries(EXTRA_FIELDS.map((f) => [f, v[f] || ''])),
    secrets: {},
  };
}

/** Keys & connections: AI engines, photo libraries and publishing accounts — one place for every secret. */
export default function KeysCard({ onSaved, platform = false }) {
  const { t, lang } = useI18n();
  const endpoint = platform ? '/api/admin/credentials' : '/api/settings/credentials';
  const creds = useLoad(() => api.get(endpoint), [endpoint]);
  const [showAll, setShowAll] = useState(false);
  const [form, setForm] = useState(null);
  const [test, setTest] = useState(null);
  const [checks, setChecks] = useState({});
  const [customModel, setCustomModel] = useState({});
  const [liveModels, setLiveModels] = useState({});
  const [modelsError, setModelsError] = useState({});
  const [busy, run] = useAction();

  const orderOf = (v) => (Object.keys(v?.engines || {}).length ? Object.keys(v.engines) : DEFAULT_ORDER);
  useEffect(() => { if (creds.data) setForm(initialForm(creds.data.values, orderOf(creds.data.values))); }, [creds.data]);
  if (!form) return <div className="card card-pad"><Spinner /></div>;

  const values = creds.data.values;
  const engines = values.engines || {};
  const ORDER = orderOf(values);
  const outdated = !engines.mistral;
  const ensemble = form.ai_mode === 'ensemble';
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const setSecret = (field, value) => setForm((f) => ({ ...f, secrets: { ...f.secrets, [field]: value } }));
  const hasKey = (n) => Boolean(values[`${n}_api_key`]?.set || (form.secrets[`${n}_api_key`] || '').trim())
    && (engines[n]?.extra || []).every((x) => (form[x.field] || '').trim());
  const active = ORDER.filter(hasKey);
  const primary = active.includes(form.ai_primary) ? form.ai_primary : (active[0] || form.ai_primary);
  const initial = initialForm(values, ORDER);
  const dirty = JSON.stringify({ ...form, secrets: {} }) !== JSON.stringify(initial) || Object.values(form.secrets).some(Boolean);
  const canRemove = (field) => values[field]?.set && values[field]?.source !== 'environment' && (values[field]?.source === 'dashboard' || platform);

  const save = () => run('save', async () => {
    const res = await api.put(endpoint, {
      ai_mode: form.ai_mode, ai_primary: primary,
      ...Object.fromEntries(ORDER.map((n) => [`${n}_model`, form[`${n}_model`]])),
      ...Object.fromEntries(EXTRA_FIELDS.map((f) => [f, (form[f] || '').trim()])),
      ...form.secrets,
    });
    creds.setData({ ...creds.data, values: res.values });
    setTest(null);
    onSaved?.();
  }, t('saved'));
  const clear = (field) => window.confirm(t('remove_key_confirm')) && run(`clear-${field}`, async () => {
    const res = await api.put(endpoint, { [field]: null });
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
  const runTest = () => run('test', async () => { setTest(null); setTest(await api.post('/api/settings/credentials/test-ai')); });
  const check = (provider) => run(`chk-${provider}`, async () => {
    const r = await api.get(`/api/providers/${provider}/status`);
    setChecks((x) => ({ ...x, [provider]: r }));
  });
  const testOf = (name) => (test?.engines || []).find((r) => r.engine === name);

  const engineCard = (name) => {
    const info = engines[name] || {};
    const on = hasKey(name);
    const field = `${name}_model`;
    const suggested = info.models || [];
    const live = liveModels[name];
    const models = live
      ? [...suggested.filter((m) => live.includes(m.id)), ...live.filter((id) => !suggested.some((m) => m.id === id)).map((id) => ({ id, note: t('from_account') }))]
      : suggested;
    const current = form[field] || info.default_model || '';
    const showCustom = customModel[name] || (current && !models.some((m) => m.id === current));
    const typed = (form.secrets[`${name}_api_key`] || '').trim();
    const result = testOf(name);
    return (
      <ConnCard key={name} name={info.label || name} on={on} sub={info.free_i18n?.[lang] || info.free}
        badges={on && primary === name ? <span className="pill gold"><Star size={12} /> {ensemble ? t('judge') : t('primary')}</span> : null}
        actions={on && primary !== name ? (
          <Button size="sm" variant="ghost" icon={Star} onClick={() => set('ai_primary', name)}>{ensemble ? t('make_judge') : t('make_primary')}</Button>
        ) : null}>
        {(info.extra || []).map((x) => (
          <Field key={x.field} label={x.label} hint={x.hint_i18n?.[lang] || x.hint}>
            <input className="input ltr" dir="ltr" value={form[x.field] || ''} onChange={(e) => set(x.field, e.target.value)} />
          </Field>
        ))}
        <SecretField value={form.secrets[`${name}_api_key`]} onChange={(v) => setSecret(`${name}_api_key`, v)}
          state={values[`${name}_api_key`]} placeholder={info.key_placeholder} getUrl={info.key_url}
          onRemove={canRemove(`${name}_api_key`) ? () => clear(`${name}_api_key`) : null} removing={busy === `clear-${name}_api_key`}
          warn={typed && info.key_prefix && !typed.startsWith(info.key_prefix) ? `${t('key_prefix_warn')} ${info.key_prefix}` : ''} />
        <div className="model-row">
          <label className="xs bold" htmlFor={`m-${name}`}>{t('model')}</label>
          <select id={`m-${name}`} className="select ltr" value={showCustom ? CUSTOM : current} onChange={(e) => {
            if (e.target.value === CUSTOM) { setCustomModel((c) => ({ ...c, [name]: true })); return; }
            setCustomModel((c) => ({ ...c, [name]: false }));
            set(field, e.target.value);
          }}>
            {models.map((m) => <option key={m.id} value={m.id}>{m.id} — {m.note_i18n?.[lang] || m.note}</option>)}
            <option value={CUSTOM}>{t('other_model')}</option>
          </select>
          {values[`${name}_api_key`]?.set && (
            <Button size="sm" variant="ghost" icon={RefreshCw} busy={busy === `models-${name}`} onClick={() => fetchModels(name)}>
              {live ? `${live.length} ${t('models_available')}` : t('fetch_models')}
            </Button>
          )}
        </div>
        {showCustom && (
          <input className="input ltr" dir="ltr" value={form[field]} placeholder={name === 'openrouter' ? 'vendor/model:free' : info.default_model}
            onChange={(e) => set(field, e.target.value)} />
        )}
        {modelsError[name] && <span className="xs" style={{ color: 'var(--danger)' }}>{modelsError[name]}</span>}
        {result && (
          <div className={`banner ${result.ok ? 'ok' : 'danger'} small`} style={{ margin: 0 }}>
            {result.ok ? <CheckCircle2 size={16} /> : <XCircle size={16} />}
            <div><b>{result.ok ? t('connection_ok') : t('connection_failed')}</b> <span className="code">{result.model}</span>
              <div className="xs">{result.ok ? result.reply : result.error}</div></div>
          </div>
        )}
      </ConnCard>
    );
  };

  const hidden = ORDER.filter((n) => !(showAll || hasKey(n) || active.length === 0));
  return (
    <div className="stack keys" id="keys">
      <section className="card card-pad stack">
        <div className="sec-head">
          <span className="sec-ico"><Bot size={18} /></span>
          <div>
            <h3>{platform ? t('platform_keys_title') : t('ai_engines_title')}</h3>
            <p>{platform ? t('platform_keys_sub') : t('ai_engines_sub')}</p>
          </div>
        </div>
        {outdated && <div className="banner danger small" style={{ margin: 0 }}><AlertTriangle size={16} /> {t('server_outdated')}</div>}
        <div className="row" style={{ gap: 10 }}>
          <span className="small bold">{t('ai_mode')}</span>
          <div className="seg" role="radiogroup" aria-label={t('ai_mode')}>
            {['single', 'ensemble'].map((m) => (
              <button key={m} type="button" role="radio" aria-checked={form.ai_mode === m} className={`seg-item ${form.ai_mode === m ? 'on' : ''}`}
                onClick={() => set('ai_mode', m)}>{t(m === 'single' ? 'mode_single' : 'mode_ensemble')}</button>
            ))}
          </div>
        </div>
        <p className="xs muted" style={{ margin: 0 }}>
          {active.length === 0 ? t('no_engine_key')
            : ensemble ? `${t('ensemble_auto')} ${active.map((n) => engines[n]?.label).join(' + ')}`
              : `${t('single_auto')} ${active.filter((n) => n !== primary).map((n) => engines[n]?.label).join(lang === 'ar' ? '، ' : ', ') || '—'}`}
        </p>
        <div className="conn-grid">{ORDER.filter((n) => !hidden.includes(n)).map(engineCard)}</div>
        {hidden.length > 0 && (
          <div className="conn-more">
            <span className="xs muted">{t('add_engine')}:</span>
            {hidden.map((n) => (
              <button key={n} type="button" className="chip-btn" onClick={() => setShowAll(true)}>+ {engines[n]?.label || n}</button>
            ))}
          </div>
        )}
        {showAll && active.length > 0 && (
          <button type="button" className="btn btn-ghost btn-sm" style={{ alignSelf: 'flex-start' }} onClick={() => setShowAll(false)}>{t('hide_engines')}</button>
        )}
        {(values.warnings || []).map((w) => <div key={w} className="banner warn small" style={{ margin: 0 }}><AlertTriangle size={16} /> {w}</div>)}
        <div className="row">
          <Button icon={PlugZap} busy={busy === 'test'} disabled={dirty || !active.length} onClick={runTest}>{t('test_connection')}</Button>
          {dirty && <span className="xs muted">{t('save_first')}</span>}
        </div>
      </section>

      <section className="card card-pad stack">
        <div className="sec-head">
          <span className="sec-ico"><ImageIcon size={18} /></span>
          <div><h3>{t('photo_keys')}</h3><p>{t('photo_keys_sub')}</p></div>
        </div>
        <div className="conn-grid two">
          {PHOTO_KEYS.map(({ field, name, url }) => (
            <ConnCard key={field} name={name} on={Boolean(values[field]?.set || (form.secrets[field] || '').trim())}>
              <SecretField value={form.secrets[field]} onChange={(v) => setSecret(field, v)} state={values[field]} getUrl={url}
                onRemove={canRemove(field) ? () => clear(field) : null} removing={busy === `clear-${field}`} />
            </ConnCard>
          ))}
          <ConnCard name="Openverse · Wikimedia Commons" on sub={t('lib_free')} />
        </div>
      </section>

      {!platform && (
        <section className="card card-pad stack">
          <div className="sec-head">
            <span className="sec-ico"><Send size={18} /></span>
            <div><h3>{t('publishers_keys')}</h3><p>{t('publishers_keys_sub')}</p></div>
          </div>
          <div className="conn-grid">
            {PUBLISH_KEYS.map(({ field, provider, name, url }) => {
              const c = checks[provider];
              const saved = values[field]?.set;
              return (
                <ConnCard key={field} name={name} on={Boolean(saved)}
                  actions={(
                    <Button size="sm" icon={ListChecks} busy={busy === `chk-${provider}`} disabled={!saved || dirty} onClick={() => check(provider)}>
                      {t('check_connection')}
                    </Button>
                  )}>
                  <SecretField value={form.secrets[field]} onChange={(v) => setSecret(field, v)} state={values[field]} getUrl={url}
                    onRemove={canRemove(field) ? () => clear(field) : null} removing={busy === `clear-${field}`} />
                  {c && (
                    <div className={`banner ${c.connected === false || c.error ? 'danger' : 'ok'} small`} style={{ margin: 0 }}>
                      {c.connected === false || c.error ? <XCircle size={16} /> : <CheckCircle2 size={16} />}
                      <div>
                        <b>{c.connected === false ? t('disconnected') : t('connected')}</b>{c.account && <span> · {c.account}</span>}
                        {c.error && <div className="xs">{c.error}</div>}
                        {c.channels?.map((ch) => <div key={ch.id} className="xs">• {ch.name} <span className="muted">({ch.service})</span></div>)}
                      </div>
                    </div>
                  )}
                </ConnCard>
              );
            })}
          </div>
        </section>
      )}
      <p className="xs muted" style={{ margin: 0 }}><KeyRound size={12} /> {t('key_hint')}</p>
      <SaveBar dirty={dirty} busy={busy === 'save'} onSave={save} onReset={() => setForm(initialForm(values, ORDER))} />
    </div>
  );
}
