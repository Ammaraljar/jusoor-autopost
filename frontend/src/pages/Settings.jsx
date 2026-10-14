import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, ArrowDown, ArrowUp, Building2, CalendarClock, CheckCircle2, HardDrive, Images, KeyRound,
  LayoutTemplate, PenLine, Rss, Server, Send } from 'lucide-react';
import CompanyCard from '../components/CompanyCard';
import KeysCard from '../components/KeysCard';
import TemplatePicker from '../components/TemplatePicker';
import { Button, ErrorBox, Field, Loading, PageHead, SaveBar, useAction, useLoad } from '../components/ui';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { channelsOf, platformLabel } from '../lib/platforms';
import { fmtDateTime } from '../lib/format';
import { useI18n } from '../lib/i18n';

const PROVIDER_NAMES = { buffer: 'Buffer', meta: 'Meta Graph API', uploadpost: 'upload-post.com' };
const TABS = [
  { id: 'content', icon: PenLine }, { id: 'designs', icon: LayoutTemplate }, { id: 'photos', icon: Images }, { id: 'publishing', icon: Send },
  { id: 'keys', icon: KeyRound }, { id: 'system', icon: Server },
];
const PHOTO_SOURCES = ['article', 'library', 'pexels', 'pixabay', 'unsplash', 'openverse', 'wikimedia'];
const KEYED = { pexels: 'pexels', pixabay: 'pixabay', unsplash: 'unsplash' };

function sourcesOf(g) {
  const chosen = (g.image_sources || []).filter((x) => PHOTO_SOURCES.includes(x));
  if (chosen.length) return chosen;
  if (g.image_source === 'source') return ['article', 'library'];
  if (g.image_source === 'pexels') return PHOTO_SOURCES.filter((x) => x !== 'article');
  return [...PHOTO_SOURCES];
}

function ChannelsTable({ p, providers, platforms, onChange }) {
  const { t } = useI18n();
  const channels = channelsOf(p);
  const setRow = (platform, patch) => {
    const row = { provider: '', limit: 0, period: 'week', ...(channels[platform] || {}), ...patch };
    onChange({ ...channels, [platform]: row });
  };
  return (
    <div className="channels" role="table">
      <div className="ch-row ch-head" role="row">
        <span role="columnheader">{t('platform')}</span>
        <span role="columnheader">{t('channel_service')}</span>
        <span role="columnheader">{t('channel_limit')}</span>
      </div>
      {platforms.map((pl) => {
        const row = channels[pl] || {};
        const options = Object.entries(providers).filter(([, info]) => (info.platforms || []).includes(pl));
        const on = !!row.provider;
        return (
          <div key={pl} className={`ch-row ${on ? 'on' : 'off'}`} role="row">
            <b role="cell">{platformLabel(pl)}</b>
            <select role="cell" className="select sm" aria-label={t('channel_service')} value={row.provider || ''}
              onChange={(e) => setRow(pl, { provider: e.target.value })}>
              <option value="">{t('channel_off')}</option>
              {options.map(([name, info]) => (
                <option key={name} value={name}>{PROVIDER_NAMES[name]}{info.configured ? '' : ` (${t('not_configured')})`}</option>
              ))}
            </select>
            <div role="cell" className="ch-limit">
              <input className="input sm" type="number" min={0} max={100} disabled={!on} aria-label={t('channel_limit')}
                value={row.limit || ''} placeholder="∞" onChange={(e) => setRow(pl, { limit: Number(e.target.value) || 0 })} />
              <select className="select sm" disabled={!on} value={row.period || 'week'} onChange={(e) => setRow(pl, { period: e.target.value })}>
                <option value="day">{t('per_day')}</option>
                <option value="week">{t('per_week')}</option>
                <option value="month">{t('per_month')}</option>
              </select>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function SectionHead({ icon: Icon, title, sub }) {
  return (
    <div className="sec-head">
      <span className="sec-ico"><Icon size={18} /></span>
      <div><h3>{title}</h3>{sub && <p>{sub}</p>}</div>
    </div>
  );
}

/** Where a post's photos come from, in order; each source can be switched off. */
function PhotoSources({ g, images, onChange }) {
  const { t } = useI18n();
  const order = sourcesOf(g);
  const all = [...order, ...PHOTO_SOURCES.filter((x) => !order.includes(x))];
  const on = new Set(order);
  const move = (id, d) => {
    const list = [...all];
    const i = list.indexOf(id);
    const j = i + d;
    if (j < 0 || j >= list.length) return;
    [list[i], list[j]] = [list[j], list[i]];
    onChange(list.filter((x) => on.has(x)));
  };
  const toggle = (id) => onChange(all.filter((x) => (x === id ? !on.has(x) : on.has(x))));
  return (
    <ol className="src-list">
      {all.map((id, i) => {
        const keyed = KEYED[id];
        const ready = keyed ? images?.[keyed] : true;
        return (
          <li key={id} className={`src-item ${on.has(id) ? 'on' : ''}`}>
            <button type="button" className={`switch ${on.has(id) ? 'on' : ''}`} role="switch" aria-checked={on.has(id)}
              aria-label={t(`src_${id}`)} onClick={() => toggle(id)}><i /></button>
            <div className="src-text">
              <b>{t(`src_${id}`)}</b>
              <small>{t(`src_${id}_hint`)}</small>
            </div>
            {keyed && (ready
              ? <span className="key-chip ok"><CheckCircle2 size={13} /> {t('configured')}</span>
              : <a className="key-chip warn" href="#keys"><AlertTriangle size={13} /> {t('key_missing')}</a>)}
            <div className="src-move">
              <button type="button" className="btn btn-ghost btn-sm icon-btn" aria-label={t('move_up')} disabled={i === 0} onClick={() => move(id, -1)}><ArrowUp size={15} /></button>
              <button type="button" className="btn btn-ghost btn-sm icon-btn" aria-label={t('move_down')} disabled={i === all.length - 1} onClick={() => move(id, 1)}><ArrowDown size={15} /></button>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

export default function SettingsPage() {
  const { t, lang } = useI18n();
  const { user } = useAuth();
  const settings = useLoad(() => api.get('/api/settings'), []);
  const status = useLoad(() => api.get('/api/status'), []);
  const [values, setValues] = useState(null);
  const [tab, setTab] = useState(() => {
    const h = (typeof window !== 'undefined' ? window.location.hash : '').replace('#', '');
    return TABS.some((x) => x.id === h) ? h : 'content';
  });
  const [busy, run] = useAction();

  useEffect(() => { if (settings.data) setValues(structuredClone(settings.data.values)); }, [settings.data]);
  useEffect(() => {
    const onHash = () => { const h = window.location.hash.replace('#', ''); if (TABS.some((x) => x.id === h)) setTab(h); };
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);
  useEffect(() => {
    document.querySelector('.settings-tabs .tab.active')?.scrollIntoView({ inline: 'center', block: 'nearest' });
  }, [tab, values]);
  if (!values || !status.data) return settings.error ? <ErrorBox error={settings.error} /> : <Loading />;

  const opts = settings.data.options;
  const saved = settings.data.values;
  const set = (section, k, v) => setValues((x) => ({ ...x, [section]: { ...x[section], [k]: v } }));
  const dirtyOf = (...sections) => sections.some((s) => JSON.stringify(values[s]) !== JSON.stringify(saved[s]));
  const save = (...sections) => run('save', async () => {
    const out = {};
    for (const s of sections) {
      if (JSON.stringify(values[s]) !== JSON.stringify(saved[s])) out[s] = await api.put(`/api/settings/${s}`, values[s]);
    }
    settings.setData({ ...settings.data, values: { ...saved, ...out } });
    setValues((x) => ({ ...x, ...out }));
  }, t('saved'));
  const reset = (...sections) => setValues((x) => ({ ...x, ...Object.fromEntries(sections.map((s) => [s, structuredClone(saved[s])])) }));
  const go = (id) => { setTab(id); window.history.replaceState(null, '', `#${id}`); };

  const g = values.generation;
  const s = values.scheduler;
  const p = values.publishing;
  const st = status.data;
  const industry = user?.org?.industry || g.industry || 'general';
  const fieldTypes = opts.content_types_by_industry?.[industry] || opts.content_types || [];
  const typeLabel = (id) => opts.content_type_labels?.[id]?.[lang] || opts.content_type_labels?.[id]?.en || id;
  const contentTypes = fieldTypes.includes(g.content_type) || !g.content_type ? fieldTypes : [g.content_type, ...fieldTypes];
  const maxDaily = Math.max(0, ...Object.values(channelsOf(p)).filter((c) => c.provider && c.period === 'day').map((c) => c.limit || 0));

  return (
    <>
      <PageHead title={t('settings_title')} sub={t('settings_sub')} />
      <nav className="tabs settings-tabs" role="tablist" aria-label={t('settings_title')}>
        {TABS.map(({ id, icon: Icon }) => (
          <button key={id} type="button" role="tab" aria-selected={tab === id} className={`tab ${tab === id ? 'active' : ''}`} onClick={() => go(id)}>
            <Icon size={16} /> {t(`set_tab_${id}`)}
          </button>
        ))}
      </nav>

      {tab === 'content' && (
        <div className="settings-grid">
          <CompanyCard onSaved={() => settings.reload(true)} />
          <section className="card card-pad stack">
            <SectionHead icon={PenLine} title={t('generation')} sub={t('generation_sub')} />
            <div className="grid grid-2">
              <Field label={t('tone')}>
                <select className="select" value={g.tone} onChange={(e) => set('generation', 'tone', e.target.value)}>
                  {opts.tones.map((o) => <option key={o} value={o}>{t(`voice_${o}`)}</option>)}
                </select>
              </Field>
              <Field label={t('content_type')} hint={t('content_type_hint')}>
                <select className="select" value={g.content_type} onChange={(e) => set('generation', 'content_type', e.target.value)}>
                  {contentTypes.map((o) => <option key={o} value={o}>{typeLabel(o)}</option>)}
                </select>
              </Field>
              <Field label={t('min_relevance')} hint={t('min_relevance_hint')}>
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
            <label className="check">
              <input type="checkbox" checked={g.credit_source} onChange={(e) => set('generation', 'credit_source', e.target.checked)} />
              {t('credit_source')}
            </label>
          </section>
          <section className="card card-pad stack">
            <SectionHead icon={Rss} title={t('scheduler')} sub={t('scheduler_sub')} />
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
          </section>
          <SaveBar dirty={dirtyOf('generation', 'scheduler')} busy={busy === 'save'} onSave={() => save('generation', 'scheduler')}
            onReset={() => reset('generation', 'scheduler')} />
        </div>
      )}

      {tab === 'designs' && <DesignsTab />}

      {tab === 'photos' && (
        <div className="settings-grid">
          <section className="card card-pad stack">
            <SectionHead icon={Images} title={t('image_source')} sub={t('image_sources_sub')} />
            <PhotoSources g={g} images={st.images} onChange={(list) => setValues((x) => ({ ...x, generation: { ...x.generation, image_sources: list } }))} />
            <div className="row">
              <Link className="btn btn-sm" to="/library"><Images size={15} /> {t('lib_open')}</Link>
              <button type="button" className="btn btn-sm" onClick={() => go('keys')}><KeyRound size={15} /> {t('lib_add_keys')}</button>
            </div>
          </section>
          <SaveBar dirty={dirtyOf('generation')} busy={busy === 'save'} onSave={() => save('generation')} onReset={() => reset('generation')} />
        </div>
      )}

      {tab === 'publishing' && (
        <div className="settings-grid">
          <section className="card card-pad stack">
            <SectionHead icon={Send} title={t('channels_title')} sub={t('channels_hint')} />
            <ChannelsTable p={p} providers={st.providers || {}} platforms={opts.platforms}
              onChange={(channels) => set('publishing', 'channels', channels)} />
            {Object.values(channelsOf(p)).some((c) => c.provider === 'buffer') && (
              <Field label={t('buffer_mode')}>
                <select className="select" value={p.buffer_mode} onChange={(e) => set('publishing', 'buffer_mode', e.target.value)}>
                  <option value="shareNow">{t('share_now')}</option>
                  <option value="addToQueue">{t('add_queue')}</option>
                </select>
              </Field>
            )}
            <label className="check">
              <input type="checkbox" checked={p.first_comment_enabled} onChange={(e) => set('publishing', 'first_comment_enabled', e.target.checked)} />
              {t('first_comment_enabled')}
            </label>
          </section>
          <section className="card card-pad stack">
            <SectionHead icon={CalendarClock} title={t('daily_plan')} sub={t('daily_plan_sub')} />
            <div className="grid grid-2">
              <Field label={t('posts_per_day')} hint={t('posts_per_day_hint')}>
                <input className="input" type="number" min={1} max={24} value={p.posts_per_day ?? 5}
                  onChange={(e) => set('publishing', 'posts_per_day', Number(e.target.value))} />
              </Field>
              <Field label={t('min_gap_hours')}>
                <input className="input" type="number" min={0} max={12} step={0.5} value={p.min_gap_hours ?? 2}
                  onChange={(e) => set('publishing', 'min_gap_hours', Number(e.target.value))} />
              </Field>
              <Field label={t('day_start')}>
                <input className="input ltr" type="time" value={p.day_start || '09:00'} onChange={(e) => set('publishing', 'day_start', e.target.value)} />
              </Field>
              <Field label={t('day_end')}>
                <input className="input ltr" type="time" value={p.day_end || '22:00'} onChange={(e) => set('publishing', 'day_end', e.target.value)} />
              </Field>
              <Field label={t('timezone')}>
                <select className="select ltr" value={p.timezone || 'Asia/Kuala_Lumpur'} onChange={(e) => set('publishing', 'timezone', e.target.value)}>
                  {['Asia/Kuala_Lumpur', 'Asia/Riyadh', 'Asia/Dubai', 'Asia/Qatar', 'Asia/Kuwait', 'Africa/Cairo', 'Asia/Amman',
                    'Africa/Casablanca', 'Asia/Jakarta', 'Asia/Singapore', 'Asia/Bangkok', 'Europe/Istanbul', 'Europe/London', 'UTC'].map((z) => <option key={z}>{z}</option>)}
                </select>
              </Field>
            </div>
            {maxDaily > (p.posts_per_day ?? 5) && (
              <div className="banner warn small" style={{ margin: 0 }}><AlertTriangle size={16} /> {t('plan_conflict').replace('{n}', maxDaily)}</div>
            )}
          </section>
          <section className="card card-pad stack">
            <SectionHead icon={CheckCircle2} title={t('automation')} sub={t('automation_sub')} />
            <label className="check">
              <input type="checkbox" checked={!!p.auto_schedule_approved} onChange={(e) => set('publishing', 'auto_schedule_approved', e.target.checked)} />
              {t('auto_schedule_approved')}
            </label>
            <Field label={t('auto_approve_min_relevance')} hint={t('auto_approve_hint')}>
              <select className="select" value={p.auto_approve_min_relevance ?? 0}
                onChange={(e) => set('publishing', 'auto_approve_min_relevance', Number(e.target.value))}>
                <option value={0}>{t('off')}</option>
                {[7, 8, 9, 10].map((n) => <option key={n} value={n}>{n}/10 {t('or_more')}</option>)}
              </select>
            </Field>
            <p className="xs muted" style={{ margin: 0 }}>{t('occasions_settings_note')} <Link to="/occasions">{t('nav_occasions')}</Link></p>
          </section>
          <SaveBar dirty={dirtyOf('publishing')} busy={busy === 'save'} onSave={() => save('publishing')} onReset={() => reset('publishing')} />
        </div>
      )}

      {tab === 'keys' && <KeysCard onSaved={() => status.reload(true)} />}

      {tab === 'system' && (
        <div className="settings-grid">
          <section className="card card-pad stack">
            <SectionHead icon={HardDrive} title={t('system')} />
            <div className={`banner ${st.storage.public ? 'ok' : 'warn'} small`} style={{ margin: 0 }}>
              {st.storage.public ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
              <div><b>{t('storage')} ({st.storage.backend})</b><div className="xs">{st.storage.public ? t('public_ok') : t('public_missing')}</div></div>
            </div>
            <b className="small">{t('jobs')}</b>
            <div className="small stack" style={{ gap: 4 }}>
              {Object.entries(st.jobs.next_runs || {}).map(([k, v]) => (
                <div key={k}><b className="code">{k}</b> → {fmtDateTime(v, lang)}</div>
              ))}
              {!st.jobs.scheduler && <div className="muted">SCHEDULER_ENABLED=false</div>}
              {st.jobs.last_run && <div className="muted">{t('last_run')}: {fmtDateTime(st.jobs.last_run.finished_at, lang)}</div>}
            </div>
          </section>
          <BackupCard />
        </div>
      )}
    </>
  );
}

/** Post designs: which of the field's 40+ designs the company keeps (per brand identity). */
function DesignsTab() {
  const { t } = useI18n();
  const brands = useLoad(() => api.get('/api/brands'), []);
  const [bid, setBid] = useState(null);
  const [value, setValue] = useState(null);
  const [busy, run] = useAction();
  const list = brands.data || [];
  const brand = list.find((b) => b.id === bid) || list.find((b) => b.is_default) || list[0];
  useEffect(() => { if (brand) setValue(brand.templates || []); }, [brand?.id, brands.data]); // eslint-disable-line react-hooks/exhaustive-deps
  if (brands.error) return <ErrorBox error={brands.error} onRetry={brands.reload} />;
  if (!brand || value === null) return <Loading />;
  const saved = brand.templates || [];
  const dirty = JSON.stringify(value) !== JSON.stringify(saved);
  const save = () => run('save', async () => { await api.patch(`/api/brands/${brand.id}`, { templates: value }); await brands.reload(true); }, t('saved'));
  return (
    <div className="stack">
      {list.length > 1 && (
        <div className="tabs" style={{ display: 'inline-flex' }}>
          {list.map((b) => (
            <button key={b.id} type="button" className={`tab ${b.id === brand.id ? 'active' : ''}`} onClick={() => setBid(b.id)}>{b.name}</button>
          ))}
        </div>
      )}
      <TemplatePicker key={brand.id} brand={brand} value={value} onChange={setValue} classic={brand.card_theme === 'classic'}
        onUseTemplates={() => run('theme', async () => { await api.patch(`/api/brands/${brand.id}`, { card_theme: 'magazine' }); await brands.reload(true); }, t('saved'))} />
      <p className="xs muted" style={{ margin: 0 }}>{t('designs_other_hint')}</p>
      <SaveBar dirty={dirty} busy={busy === 'save'} onSave={save} onReset={() => setValue(saved)} />
    </div>
  );
}

function BackupCard() {
  const { t } = useI18n();
  const [busy, run] = useAction();
  const download = () => run('bk', async () => {
    const data = await api.get('/api/backup');
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `jusoor-autopost-backup-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  });
  const restore = (file) => run('rs', async () => api.post('/api/backup/restore', JSON.parse(await file.text())), t('restore_done'));
  return (
    <section className="card card-pad stack">
      <SectionHead icon={Building2} title={t('backup_title')} sub={t('backup_hint')} />
      <div className="row">
        <Button busy={busy === 'bk'} onClick={download}>{t('backup_download')}</Button>
        <label className="btn" style={{ cursor: 'pointer' }}>
          {busy === 'rs' ? '…' : t('backup_restore')}
          <input type="file" accept="application/json" hidden onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) restore(f);
            e.target.value = '';
          }} />
        </label>
      </div>
    </section>
  );
}
