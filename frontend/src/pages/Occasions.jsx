import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { CalendarHeart, Check, Download, Globe2, Pencil, Plus, Search, Settings2, Sparkles, Trash2 } from 'lucide-react';
import { Button, Empty, ErrorBox, Field, Loading, Modal, PageHead, StatusPill, useAction, useLoad, useToast } from '../components/ui';
import { api, mediaUrl } from '../lib/api';
import { useI18n } from '../lib/i18n';

const KINDS = ['weekly', 'religious', 'national', 'international', 'commercial', 'custom'];
const TONES = ['festive', 'spiritual', 'pride', 'appreciation', 'awareness', 'commercial', 'memorial'];
const GROUPS = [
  ['occ_group_arab', (c) => c.arab],
  ['occ_group_asia', (c) => ['MY', 'ID', 'BN', 'SG', 'TH', 'PH', 'TR', 'PK', 'IN', 'CN', 'JP', 'KR'].includes(c.code)],
  ['occ_group_world', (c) => !c.arab && !['MY', 'ID', 'BN', 'SG', 'TH', 'PH', 'TR', 'PK', 'IN', 'CN', 'JP', 'KR'].includes(c.code)],
];
const LOCALE = { ar: 'ar-EG-u-nu-latn', en: 'en-GB', ms: 'ms-MY', fr: 'fr-FR' };

const parseDay = (iso) => { const [y, m, d] = iso.split('-').map(Number); return new Date(y, m - 1, d); };
const todayIso = () => { const n = new Date(); return `${n.getFullYear()}-${String(n.getMonth() + 1).padStart(2, '0')}-${String(n.getDate()).padStart(2, '0')}`; };

export default function Occasions() {
  const { t, lang } = useI18n();
  const toast = useToast();
  const thisYear = new Date().getFullYear();
  const [year, setYear] = useState(thisYear);
  const list = useLoad(() => api.get(`/api/occasions?year=${year}`), [year]);
  const [busy, run] = useAction();
  const [kind, setKind] = useState('all');
  const [q, setQ] = useState('');
  const [onlyOn, setOnlyOn] = useState(false);
  const [showPast, setShowPast] = useState(false);
  const [editing, setEditing] = useState(null);
  const [setup, setSetup] = useState(false);

  const data = list.data;
  const cfg = data?.settings || {};
  const catalog = data?.countries || [];
  const byCode = useMemo(() => Object.fromEntries(catalog.map((c) => [c.code, c])), [catalog]);
  const name = (o) => (lang === 'ar' ? o.name_ar : o.name_en) || o.name_ar || o.name_en;
  const today = todayIso();

  const items = data?.items || [];
  const weekly = items.filter((o) => o.recurrence === 'weekly');
  const dated = items.filter((o) => o.recurrence !== 'weekly').filter((o) => {
    if (kind !== 'all' && o.kind !== kind && !(kind === 'custom' && o.source === 'custom')) return false;
    if (onlyOn && !o.enabled) return false;
    if (!showPast && year === thisYear && o.date && o.date < today) return false;
    if (q && !`${o.name_ar} ${o.name_en}`.toLowerCase().includes(q.toLowerCase())) return false;
    return true;
  });
  const months = useMemo(() => {
    const out = {};
    dated.forEach((o) => { const k = o.date.slice(0, 7); (out[k] = out[k] || []).push(o); });
    return Object.entries(out).sort(([a], [b]) => a.localeCompare(b));
  }, [dated]);
  const pastCount = items.filter((o) => o.recurrence !== 'weekly' && o.date && o.date < today).length;

  const reload = () => list.reload(true);
  const importYear = () => run('import', async () => {
    const r = await api.post('/api/occasions/import', { year });
    toast(t('occ_imported').replace('{added}', r.added).replace('{updated}', r.updated), 'success');
    reload();
  });
  const toggle = (o) => run(`on-${o.id}`, async () => {
    await api.patch(`/api/occasions/${o.id}`, { enabled: !o.enabled });
    reload();
  });
  const makePost = (o, date) => run(`post-${o.id}`, async () => {
    await api.post(`/api/occasions/${o.id}/post`, { date: date || o.next_date || o.date });
    toast(t('occ_post_started'), 'success');
    reload();
  });

  if (list.loading && !data) return <Loading />;
  const noCountries = !(cfg.countries || []).length;
  return (
    <>
      <PageHead title={t('occ_title')} sub={t('occ_sub')}>
        <div className="seg" role="tablist" aria-label={t('occ_year')}>
          {[thisYear, thisYear + 1].map((y) => (
            <button key={y} type="button" className={`seg-item ${year === y ? 'on' : ''}`} onClick={() => setYear(y)}>{y}</button>
          ))}
        </div>
        <Button icon={Plus} onClick={() => setEditing({ recurrence: 'once', date: `${year}-${today.slice(5)}` })}>{t('occ_add')}</Button>
        <Button variant="primary" icon={Download} busy={busy === 'import'} disabled={noCountries} onClick={importYear}>
          {(items.some((o) => o.source === 'auto') ? t('occ_update') : t('occ_import')).replace('{year}', year)}
        </Button>
      </PageHead>
      {list.error && <ErrorBox error={list.error} onRetry={list.reload} />}

      <SetupCard cfg={cfg} byCode={byCode} open={setup || noCountries} onToggle={() => setSetup((v) => !v)}
        catalog={catalog} year={year} onSaved={reload} />

      {weekly.length > 0 && (
        <section className="card card-pad occ-weekly">
          <div className="occ-sec-head"><CalendarHeart size={18} /> <b>{t('occ_weekly_title')}</b></div>
          {weekly.map((o) => (
            <OccRow key={o.id} o={o} name={name(o)} byCode={byCode} lang={lang} t={t} busy={busy} today={today}
              onToggle={() => toggle(o)} onPost={() => makePost(o)} onEdit={() => setEditing(o)} />
          ))}
        </section>
      )}

      {items.length > 0 && (
        <div className="occ-filters">
          <div className="seg" role="tablist">
            {['all', ...KINDS.filter((k) => k !== 'weekly')].map((k) => (
              <button key={k} type="button" className={`seg-item ${kind === k ? 'on' : ''}`} onClick={() => setKind(k)}>
                {k === 'all' ? t('occ_all') : t(`kind_${k}`)}
              </button>
            ))}
          </div>
          <div className="search-box">
            <Search size={16} />
            <input className="input" type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t('occ_search')} />
          </div>
          <label className="check small"><input type="checkbox" checked={onlyOn} onChange={(e) => setOnlyOn(e.target.checked)} /> {t('occ_only_on')}</label>
          {year === thisYear && pastCount > 0 && (
            <label className="check small"><input type="checkbox" checked={showPast} onChange={(e) => setShowPast(e.target.checked)} /> {t('occ_show_past')} ({pastCount})</label>
          )}
        </div>
      )}

      {!noCountries && items.length === 0 && (
        <div className="card"><Empty icon={CalendarHeart}>{t('occ_empty')}</Empty></div>
      )}

      <div className="occ-months">
        {months.map(([ym, rows]) => (
          <section key={ym} className="occ-month">
            <h3 className="occ-month-head">
              {parseDay(`${ym}-01`).toLocaleDateString(LOCALE[lang] || 'en-GB', { month: 'long', year: 'numeric' })}
              <span className="muted small">{rows.filter((o) => o.enabled).length}/{rows.length}</span>
            </h3>
            <div className="card occ-list">
              {rows.map((o) => (
                <OccRow key={o.id} o={o} name={name(o)} byCode={byCode} lang={lang} t={t} busy={busy} today={today}
                  onToggle={() => toggle(o)} onPost={() => makePost(o)} onEdit={() => setEditing(o)} />
              ))}
            </div>
          </section>
        ))}
      </div>
      {items.length > 0 && <p className="xs muted occ-note">{t('occ_hijri_note')}</p>}

      {editing && <OccModal item={editing} catalog={catalog} onClose={() => setEditing(null)}
        onSaved={() => { setEditing(null); reload(); }} />}
    </>
  );
}

function OccRow({ o, name, byCode, lang, t, busy, today, onToggle, onPost, onEdit }) {
  const weekly = o.recurrence === 'weekly';
  const when = o.next_date || o.date;
  const d = when ? parseDay(when) : null;
  const past = !weekly && o.date && o.date < today;
  const post = o.posts?.find((p) => p.date === when) || (!weekly ? o.posts?.[o.posts.length - 1] : null);
  const flags = (o.countries || []).map((c) => byCode[c]?.flag).filter(Boolean);
  return (
    <div className={`occ-row ${o.enabled ? '' : 'off'} ${past ? 'past' : ''}`}>
      <div className="occ-date" aria-hidden={!d}>
        {weekly ? <><b>{t('occ_every')}</b><small>{d?.toLocaleDateString(LOCALE[lang] || 'en-GB', { weekday: 'long' })}</small></>
          : d && <><b>{d.getDate()}</b><small>{d.toLocaleDateString(LOCALE[lang] || 'en-GB', { weekday: 'short' })}</small></>}
      </div>
      <div className="occ-main">
        <div className="occ-name">
          <span>{name}</span>
          {o.number ? <span className="occ-num">{o.number}</span> : null}
        </div>
        <div className="occ-meta">
          <span className={`occ-kind k-${o.kind}`}>{t(`kind_${o.source === 'custom' && o.kind !== 'weekly' ? 'custom' : o.kind}`)}</span>
          {flags.length > 0 && <span className="occ-flags" title={(o.countries || []).map((c) => byCode[c]?.[lang === 'ar' ? 'ar' : 'en']).join('، ')}>
            {flags.slice(0, 6).join(' ')}{flags.length > 6 ? ` +${flags.length - 6}` : ''}</span>}
          {o.hijri && (o.kind === 'religious' || o.kind === 'weekly') && <span className="muted">{o.hijri}</span>}
          {weekly && o.next_date && <span className="muted">{t('occ_next')}: {parseDay(o.next_date).toLocaleDateString(LOCALE[lang] || 'en-GB', { day: 'numeric', month: 'long' })}</span>}
          {!o.relevant && <span className="muted">· {t('occ_off_field')}</span>}
        </div>
        {o.notes && <div className="xs muted clamp-2">✎ {o.notes}</div>}
      </div>
      <div className="occ-actions">
        {post ? (
          <Link to={`/drafts/${post.draft_id}`} className="occ-post">
            {post.thumb && <img src={mediaUrl(post.thumb)} alt="" />}
            <StatusPill status={post.status} />
          </Link>
        ) : (!past && o.enabled && (
          <Button size="sm" icon={Sparkles} busy={busy === `post-${o.id}`} onClick={onPost}>{t('occ_create_post')}</Button>
        ))}
        <button type="button" className={`switch ${o.enabled ? 'on' : ''}`} role="switch" aria-checked={o.enabled}
          aria-label={t('occ_enabled')} disabled={busy === `on-${o.id}`} onClick={onToggle}><i /></button>
        <button type="button" className="btn btn-sm btn-ghost icon-btn" aria-label={t('edit')} onClick={onEdit}><Pencil size={15} /></button>
      </div>
    </div>
  );
}

function SetupCard({ cfg, byCode, open, onToggle, catalog, year, onSaved }) {
  const { t, lang } = useI18n();
  const toast = useToast();
  const [f, setF] = useState(null);
  const [picking, setPicking] = useState(false);
  const [busy, run] = useAction();
  const v = f || { countries: cfg.countries || [], kinds: cfg.kinds || {}, auto_create: cfg.auto_create ?? true,
    lead_days: cfg.lead_days ?? 3, auto_schedule: cfg.auto_schedule ?? true, post_time: cfg.post_time || '08:00',
    dialect_by_country: cfg.dialect_by_country ?? true };
  const set = (k, val) => setF({ ...v, [k]: val });
  const save = () => run('save', async () => {
    const changed = JSON.stringify(v.countries) !== JSON.stringify(cfg.countries || [])
      || JSON.stringify(v.kinds) !== JSON.stringify(cfg.kinds || {});
    await api.put('/api/occasions/settings', { ...v, lead_days: Number(v.lead_days) || 0 });
    if (changed && v.countries.length) {
      const r = await api.post('/api/occasions/import', { year });
      toast(t('occ_imported').replace('{added}', r.added).replace('{updated}', r.updated), 'success');
    } else toast(t('saved'), 'success');
    setF(null);
    onSaved();
  });
  const chosen = v.countries.map((c) => byCode[c]).filter(Boolean);
  return (
    <section className="card occ-setup">
      <button type="button" className="occ-setup-head" onClick={onToggle} aria-expanded={open}>
        <Settings2 size={18} />
        <b>{t('occ_setup')}</b>
        <span className="occ-flags">{chosen.slice(0, 10).map((c) => c.flag).join(' ')}{chosen.length > 10 ? ` +${chosen.length - 10}` : ''}</span>
        <span className="spacer" />
        <span className="small muted">{open ? '−' : '+'}</span>
      </button>
      {open && (
        <div className="card-pad stack">
          {!chosen.length && <div className="banner info"><Globe2 size={18} /> {t('occ_no_countries')}</div>}
          <div className="field">
            <span className="field-head">{t('occ_countries')}</span>
            <div className="occ-chips">
              {chosen.map((c) => (
                <span key={c.code} className="occ-chip">{c.flag} {lang === 'ar' ? c.ar : c.en}
                  <button type="button" aria-label={t('delete')} onClick={() => set('countries', v.countries.filter((x) => x !== c.code))}>×</button>
                </span>
              ))}
              <Button size="sm" icon={Plus} onClick={() => setPicking(true)}>{t('occ_pick_countries')}</Button>
            </div>
            <small>{t('occ_countries_hint')}</small>
          </div>
          <div className="field">
            <span className="field-head">{t('occ_kinds')}</span>
            <div className="occ-chips">
              {KINDS.filter((k) => k !== 'custom').map((k) => (
                <label key={k} className={`occ-toggle ${v.kinds[k] !== false ? 'on' : ''}`}>
                  <input type="checkbox" checked={v.kinds[k] !== false} onChange={(e) => set('kinds', { ...v.kinds, [k]: e.target.checked })} />
                  {v.kinds[k] !== false && <Check size={14} />} {t(`kind_${k}`)}
                </label>
              ))}
            </div>
          </div>
          <div className="occ-auto">
            <label className="check">
              <input type="checkbox" checked={v.auto_create} onChange={(e) => set('auto_create', e.target.checked)} />
              {t('occ_auto_create')}
              <input className="input occ-num-input" type="number" min="0" max="30" value={v.lead_days}
                onChange={(e) => set('lead_days', e.target.value)} disabled={!v.auto_create} />
              {t('occ_days')}
            </label>
            <label className="check">
              <input type="checkbox" checked={v.auto_schedule} onChange={(e) => set('auto_schedule', e.target.checked)} />
              {t('occ_auto_schedule')}
              <input className="input occ-time-input" type="time" value={v.post_time} onChange={(e) => set('post_time', e.target.value)} disabled={!v.auto_schedule} />
            </label>
            <label className="check">
              <input type="checkbox" checked={v.dialect_by_country} onChange={(e) => set('dialect_by_country', e.target.checked)} />
              {t('occ_dialect')}
            </label>
          </div>
          <p className="xs muted">{t('occ_auto_hint')}</p>
          <div className="row">
            <Button variant="primary" icon={Check} busy={busy === 'save'} disabled={!f} onClick={save}>{t('occ_save_import')}</Button>
            {f && <Button variant="ghost" onClick={() => setF(null)}>{t('cancel')}</Button>}
          </div>
        </div>
      )}
      {picking && <CountryPicker catalog={catalog} value={v.countries} onClose={() => setPicking(false)}
        onDone={(codes) => { set('countries', codes); setPicking(false); }} />}
    </section>
  );
}

function CountryPicker({ catalog, value, onClose, onDone }) {
  const { t, lang } = useI18n();
  const [sel, setSel] = useState(value);
  const [q, setQ] = useState('');
  const match = (c) => !q || `${c.ar} ${c.en} ${c.code}`.toLowerCase().includes(q.toLowerCase());
  const flip = (code) => setSel((s) => (s.includes(code) ? s.filter((x) => x !== code) : [...s, code]));
  return (
    <Modal title={t('occ_pick_countries')} onClose={onClose} wide
      footer={<><span className="small muted">{sel.length} {t('selected')}</span><span className="spacer" />
        <Button variant="ghost" onClick={onClose}>{t('cancel')}</Button>
        <Button variant="primary" icon={Check} onClick={() => onDone(sel)}>{t('done')}</Button></>}>
      <div className="search-box" style={{ marginBottom: 12 }}>
        <Search size={16} />
        <input className="input" type="search" autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder={t('occ_search_country')} />
      </div>
      {GROUPS.map(([label, test]) => {
        const rows = catalog.filter(test).filter(match);
        if (!rows.length) return null;
        const all = rows.every((c) => sel.includes(c.code));
        return (
          <div key={label} className="occ-group">
            <div className="row occ-group-head">
              <b>{t(label)}</b><span className="spacer" />
              <button type="button" className="btn btn-sm btn-ghost" onClick={() => setSel((s) => (all
                ? s.filter((x) => !rows.some((c) => c.code === x)) : [...new Set([...s, ...rows.map((c) => c.code)])]))}>
                {all ? t('clear_selection') : t('select_all')}
              </button>
            </div>
            <div className="occ-country-grid">
              {rows.map((c) => (
                <label key={c.code} className={`occ-country ${sel.includes(c.code) ? 'on' : ''}`}>
                  <input type="checkbox" checked={sel.includes(c.code)} onChange={() => flip(c.code)} />
                  <span className="occ-flag">{c.flag}</span> {lang === 'ar' ? c.ar : c.en}
                </label>
              ))}
            </div>
          </div>
        );
      })}
    </Modal>
  );
}

function OccModal({ item, catalog, onClose, onSaved }) {
  const { t, lang } = useI18n();
  const isNew = !item.id;
  const custom = isNew || item.source === 'custom';
  const [f, setF] = useState({ name_ar: '', name_en: '', notes: '', tone: 'festive', countries: [], weekday: 4,
    ...item, number: item.number ?? '', post_time: item.post_time || '' });
  const [busy, run] = useAction();
  const set = (k, v) => setF((x) => ({ ...x, [k]: v }));
  const weekly = f.recurrence === 'weekly';
  const save = () => run('save', async () => {
    const number = f.number === '' ? null : Number(f.number);
    if (isNew) {
      await api.post('/api/occasions', { name: f.name_ar, name_en: f.name_en, recurrence: f.recurrence,
        date: weekly ? null : f.date, weekday: weekly ? Number(f.weekday) : null, tone: f.tone,
        countries: f.countries, number, notes: f.notes, post_time: f.post_time || null });
    } else {
      await api.patch(`/api/occasions/${item.id}`, { name_ar: f.name_ar, name_en: f.name_en,
        ...(weekly ? { weekday: Number(f.weekday) } : { date: f.date }), notes: f.notes, post_time: f.post_time || '',
        ...(number === null ? { clear_number: true } : { number }), ...(custom ? { tone: f.tone, countries: f.countries } : {}) });
    }
    onSaved();
  });
  const remove = () => window.confirm(t('confirm_delete')) && run('del', async () => { await api.del(`/api/occasions/${item.id}`); onSaved(); });
  const days = [0, 1, 2, 3, 4, 5, 6].map((i) => new Date(2024, 0, 1 + i).toLocaleDateString(LOCALE[lang] || 'en-GB', { weekday: 'long' }));
  return (
    <Modal title={isNew ? t('occ_add') : t('occ_edit')} onClose={onClose}
      footer={<>
        {!isNew && custom && <Button variant="ghost" className="btn btn-ghost btn-danger" icon={Trash2} busy={busy === 'del'} onClick={remove}>{t('delete')}</Button>}
        <span className="spacer" />
        <Button variant="ghost" onClick={onClose}>{t('cancel')}</Button>
        <Button variant="primary" icon={Check} busy={busy === 'save'} disabled={!f.name_ar.trim() || (!weekly && !f.date)} onClick={save}>{t('save')}</Button>
      </>}>
      <div className="stack">
        {isNew && (
          <Field label={t('occ_recurrence')}>
            <div className="seg">
              {['once', 'yearly', 'weekly'].map((r) => (
                <button key={r} type="button" className={`seg-item ${f.recurrence === r ? 'on' : ''}`} onClick={() => set('recurrence', r)}>{t(`rec_${r}`)}</button>
              ))}
            </div>
          </Field>
        )}
        <div className="grid grid-2">
          <Field label={t('occ_name_ar')}><input className="input" value={f.name_ar} onChange={(e) => set('name_ar', e.target.value)} /></Field>
          <Field label={t('occ_name_en')}><input className="input ltr" dir="ltr" value={f.name_en} onChange={(e) => set('name_en', e.target.value)} /></Field>
        </div>
        <div className="grid grid-2">
          {weekly ? (
            <Field label={t('occ_weekday')}>
              <select className="select" value={f.weekday ?? 4} onChange={(e) => set('weekday', e.target.value)}>
                {days.map((d, i) => <option key={d} value={i}>{d}</option>)}
              </select>
            </Field>
          ) : (
            <Field label={t('date')}><input className="input" type="date" value={f.date || ''} onChange={(e) => set('date', e.target.value)} /></Field>
          )}
          <Field label={t('occ_post_time')} hint={t('occ_post_time_hint')}>
            <input className="input" type="time" value={f.post_time} onChange={(e) => set('post_time', e.target.value)} />
          </Field>
        </div>
        <div className="grid grid-2">
          <Field label={t('occ_number')} hint={t('occ_number_hint')}>
            <input className="input" type="number" min="0" value={f.number} onChange={(e) => set('number', e.target.value)} />
          </Field>
          {custom && (
            <Field label={t('occ_identity')}>
              <select className="select" value={f.tone} onChange={(e) => set('tone', e.target.value)}>
                {TONES.map((x) => <option key={x} value={x}>{t(`tone_${x}`)}</option>)}
              </select>
            </Field>
          )}
        </div>
        {custom && (
          <Field label={t('occ_countries')}>
            <select className="select" multiple size={5} value={f.countries}
              onChange={(e) => set('countries', [...e.target.selectedOptions].map((o) => o.value))}>
              {catalog.map((c) => <option key={c.code} value={c.code}>{c.flag} {lang === 'ar' ? c.ar : c.en}</option>)}
            </select>
          </Field>
        )}
        <Field label={t('occ_notes')} hint={t('occ_notes_hint')}>
          <textarea className="textarea" rows={3} value={f.notes} onChange={(e) => set('notes', e.target.value)} />
        </Field>
      </div>
    </Modal>
  );
}
