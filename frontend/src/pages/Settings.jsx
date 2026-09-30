import { useEffect, useState } from 'react';
import { AlertTriangle, Bot, CheckCircle2, HardDrive, PlugZap, Save } from 'lucide-react';
import KeysCard from '../components/KeysCard';
import { Button, ErrorBox, Field, Loading, PageHead, useAction, useLoad } from '../components/ui';
import { api } from '../lib/api';
import { fmtDateTime } from '../lib/format';
import { useI18n } from '../lib/i18n';

const PROVIDER_NAMES = { buffer: 'Buffer', meta: 'Meta Graph API', uploadpost: 'upload-post.com' };
const ENV_HINT = { buffer: 'BUFFER_API_KEY', meta: 'META_ACCESS_TOKEN', uploadpost: 'UPLOADPOST_API_KEY' };

export default function SettingsPage() {
  const { t, lang } = useI18n();
  const settings = useLoad(() => api.get('/api/settings'), []);
  const status = useLoad(() => api.get('/api/status'), []);
  const [values, setValues] = useState(null);
  const [checks, setChecks] = useState({});
  const [busy, run] = useAction();

  useEffect(() => { if (settings.data) setValues(structuredClone(settings.data.values)); }, [settings.data]);
  if (!values || !status.data) return settings.error ? <ErrorBox error={settings.error} /> : <Loading />;
  const opts = settings.data.options;
  const set = (section, k, v) => setValues((x) => ({ ...x, [section]: { ...x[section], [k]: v } }));
  const save = (section) => run(section, async () => {
    const res = await api.put(`/api/settings/${section}`, values[section]);
    setValues((x) => ({ ...x, [section]: res }));
  }, t('saved'));
  const g = values.generation;
  const s = values.scheduler;
  const p = values.publishing;
  const st = status.data;

  return (
    <>
      <PageHead title={t('settings_title')} sub={t('settings_sub')} />
      <div className="grid grid-2" style={{ alignItems: 'start' }}>
        <div className="stack">
          <div className="card card-pad stack">
            <h3>{t('generation')}</h3>
            <div className="grid grid-2">
              <Field label={t('gen_language')}>
                <select className="select" value={g.language} onChange={(e) => set('generation', 'language', e.target.value)}>
                  {opts.languages.map((o) => <option key={o}>{o}</option>)}
                </select>
              </Field>
              <Field label={t('tone')}>
                <select className="select" value={g.tone} onChange={(e) => set('generation', 'tone', e.target.value)}>
                  {opts.tones.map((o) => <option key={o}>{o}</option>)}
                </select>
              </Field>
              <Field label={t('content_type')}>
                <select className="select" value={g.content_type} onChange={(e) => set('generation', 'content_type', e.target.value)}>
                  {opts.content_types.map((o) => <option key={o}>{o}</option>)}
                </select>
              </Field>
              <Field label={t('platform')}>
                <select className="select" value={g.platform} onChange={(e) => set('generation', 'platform', e.target.value)}>
                  {opts.platforms.map((o) => <option key={o}>{o}</option>)}
                </select>
              </Field>
              <Field label={t('min_relevance')}>
                <input className="input" type="number" min={0} max={10} value={g.min_relevance}
                  onChange={(e) => set('generation', 'min_relevance', Number(e.target.value))} />
              </Field>
              <Field label={t('content_slides')}>
                <input className="input" type="number" min={2} max={8} value={g.content_slides}
                  onChange={(e) => set('generation', 'content_slides', Number(e.target.value))} />
              </Field>
            </div>
            <Field label={t('audience')}>
              <textarea className="textarea" rows={2} value={g.audience} onChange={(e) => set('generation', 'audience', e.target.value)} />
            </Field>
            <Field label={t('objective')}>
              <textarea className="textarea" rows={2} value={g.objective} onChange={(e) => set('generation', 'objective', e.target.value)} />
            </Field>
            <Field label={t('image_source')}>
              <select className="select" value={g.image_source} onChange={(e) => set('generation', 'image_source', e.target.value)}>
                <option value="auto">{t('img_auto')}</option>
                <option value="pexels">{t('img_pexels')}</option>
                <option value="source">{t('img_source')}</option>
              </select>
            </Field>
            <label className="check">
              <input type="checkbox" checked={g.credit_source} onChange={(e) => set('generation', 'credit_source', e.target.checked)} />
              {t('credit_source')}
            </label>
            <div><Button variant="primary" icon={Save} busy={busy === 'generation'} onClick={() => save('generation')}>{t('save')}</Button></div>
          </div>

          <div className="card card-pad stack">
            <h3>{t('scheduler')}</h3>
            <label className="check">
              <input type="checkbox" checked={s.scrape_enabled} onChange={(e) => set('scheduler', 'scrape_enabled', e.target.checked)} />
              {t('scrape_enabled')}
            </label>
            <div className="grid grid-2">
              <Field label={t('max_age')}>
                <input className="input" type="number" min={1} value={s.max_article_age_days}
                  onChange={(e) => set('scheduler', 'max_article_age_days', Number(e.target.value))} />
              </Field>
              <Field label={t('max_drafts')}>
                <input className="input" type="number" min={1} max={50} value={s.max_drafts_per_run}
                  onChange={(e) => set('scheduler', 'max_drafts_per_run', Number(e.target.value))} />
              </Field>
            </div>
            <div><Button variant="primary" icon={Save} busy={busy === 'scheduler'} onClick={() => save('scheduler')}>{t('save')}</Button></div>
          </div>

          <div className="card card-pad stack">
            <h3>{t('publishing')}</h3>
            <div className="grid grid-2">
              <Field label={t('default_provider')}>
                <select className="select" value={p.default_provider} onChange={(e) => set('publishing', 'default_provider', e.target.value)}>
                  {opts.providers.map((o) => <option key={o} value={o}>{PROVIDER_NAMES[o]}</option>)}
                </select>
              </Field>
              <Field label={t('buffer_mode')}>
                <select className="select" value={p.buffer_mode} onChange={(e) => set('publishing', 'buffer_mode', e.target.value)}>
                  <option value="shareNow">{t('share_now')}</option>
                  <option value="addToQueue">{t('add_queue')}</option>
                </select>
              </Field>
            </div>
            <Field label={t('default_platforms')}>
              <div className="row">
                {opts.platforms.map((o) => (
                  <label key={o} className="check small">
                    <input type="checkbox" checked={p.default_platforms.includes(o)} onChange={() => set('publishing', 'default_platforms',
                      p.default_platforms.includes(o) ? p.default_platforms.filter((x) => x !== o) : [...p.default_platforms, o])} />
                    {o}
                  </label>
                ))}
              </div>
            </Field>
            <label className="check">
              <input type="checkbox" checked={p.first_comment_enabled} onChange={(e) => set('publishing', 'first_comment_enabled', e.target.checked)} />
              {t('first_comment_enabled')}
            </label>
            <div><Button variant="primary" icon={Save} busy={busy === 'publishing'} onClick={() => save('publishing')}>{t('save')}</Button></div>
          </div>
        </div>

        <div className="stack">
          <KeysCard onSaved={() => status.reload(true)} />

          <div className="card card-pad stack">
            <h3>{t('system')}</h3>
            <StatusLine icon={Bot} ok={st.ai.configured}
              label={`${t('ai')} — ${st.ai.provider === 'openai_compatible' ? t('ai_compatible') : 'Claude API'}`}
              detail={st.ai.configured
                ? <span className="code">{st.ai.model}{st.ai.base_url ? ` · ${st.ai.base_url}` : ''}</span>
                : (st.ai.provider === 'openai_compatible' ? 'AI_BASE_URL / AI_MODEL' : 'ANTHROPIC_API_KEY')} />
            <StatusLine icon={HardDrive} ok={st.storage.public} label={`${t('storage')} (${st.storage.backend})`}
              detail={st.storage.public ? t('public_ok') : t('public_missing')} />
            <StatusLine icon={PlugZap} ok={st.images.pexels} warn label="Pexels" detail={st.images.pexels ? t('configured') : 'PEXELS_API_KEY'} />
          </div>

          <div className="card card-pad stack">
            <h3>{t('providers')}</h3>
            {Object.entries(st.providers).map(([name, info]) => {
              const c = checks[name];
              return (
                <div key={name} className="target">
                  <div className="row">
                    <b>{PROVIDER_NAMES[name]}</b>
                    <span className={`pill ${info.configured ? 'ok' : ''}`}>{info.configured ? t('configured') : t('not_configured')}</span>
                    <div className="spacer" />
                    <Button size="sm" busy={busy === `chk-${name}`} disabled={!info.configured}
                      onClick={() => run(`chk-${name}`, async () => {
                        const r = await api.get(`/api/providers/${name}/status`);
                        setChecks((x) => ({ ...x, [name]: r }));
                      })}>
                      {t('check')}
                    </Button>
                  </div>
                  {!info.configured && <div className="xs muted" style={{ marginTop: 6 }}>{t('keys_title')} ↑</div>}
                  {c && (
                    <div className="small" style={{ marginTop: 8 }}>
                      {c.connected ? <span className="pill ok">{t('connected')}</span> : c.connected === false ? <span className="pill danger">{t('disconnected')}</span> : null}
                      {c.account && <span className="muted"> {c.account}</span>}
                      {c.error && <div className="xs" style={{ color: 'var(--danger)' }}>{c.error}</div>}
                      {c.channels?.map((ch) => <div key={ch.id} className="xs">• {ch.name} <span className="muted">({ch.service})</span></div>)}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          <div className="card card-pad">
            <h3>{t('jobs')}</h3>
            <div className="small stack" style={{ gap: 4 }}>
              {Object.entries(st.jobs.next_runs || {}).map(([k, v]) => (
                <div key={k}><b className="code">{k}</b> → {fmtDateTime(v, lang)}</div>
              ))}
              {!st.jobs.scheduler && <div className="muted">SCHEDULER_ENABLED=false</div>}
              {st.jobs.last_run && <div className="muted">{t('last_run')}: {fmtDateTime(st.jobs.last_run.finished_at, lang)}</div>}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

function StatusLine({ icon: Icon, ok, warn, label, detail }) {
  const color = ok ? 'var(--ok)' : warn ? 'var(--warn)' : 'var(--danger)';
  return (
    <div className="row" style={{ flexWrap: 'nowrap' }}>
      <Icon size={18} className="muted" />
      <div style={{ flex: 1 }}>
        <div className="bold small">{label}</div>
        <div className="xs muted">{detail}</div>
      </div>
      {ok ? <CheckCircle2 size={18} color={color} /> : <AlertTriangle size={18} color={color} />}
    </div>
  );
}
