import { useEffect, useRef, useState } from 'react';
import { Link, NavLink, Route, Routes, useNavigate, useParams } from 'react-router-dom';
import { BarChart3, Calendar, Copy, Download, Eye, FileUp, ListPlus, Mail, MailCheck, Plus, RefreshCw, Save,
  Send, Settings2, Trash2, UserMinus, UserPlus, Users, X } from 'lucide-react';
import { BulkBar, Button, Empty, ErrorBox, Field, Loading, Modal, PageHead, SelectAll, Spinner, StatusPill,
  useAction, useLoad, useSelection } from '../components/ui';
import { api, mediaUrl } from '../lib/api';
import { useAuth } from '../lib/auth';
import { fmtDateTime, toLocalInput } from '../lib/format';
import { LANGUAGES, useI18n } from '../lib/i18n';
import { useExample } from '../lib/useExample';

const STATUS_PILL = { draft: 'pending_review', generating: 'generating', scheduled: 'scheduled', sending: 'publishing',
  sent: 'published', failed: 'failed' };

function Tabs() {
  const { t } = useI18n();
  const tabs = [
    { to: '/newsletters', label: t('nl_campaigns'), icon: Mail, end: true },
    { to: '/newsletters/contacts', label: t('nl_contacts'), icon: Users },
    { to: '/newsletters/lists', label: t('nl_lists'), icon: ListPlus },
    { to: '/newsletters/settings', label: t('nl_sending'), icon: Settings2 },
  ];
  return (
    <div className="row" style={{ marginBottom: 16, gap: 8 }}>
      {tabs.map(({ to, label, icon: Icon, end }) => (
        <NavLink key={to} to={to} end={end} className={({ isActive }) => `btn btn-sm ${isActive ? 'btn-primary' : ''}`}>
          <Icon size={14} /> {label}
        </NavLink>
      ))}
    </div>
  );
}

export default function Newsletters() {
  return (
    <Routes>
      <Route index element={<Campaigns />} />
      <Route path="contacts" element={<Contacts />} />
      <Route path="lists" element={<Lists />} />
      <Route path="settings" element={<SendingAccount />} />
      <Route path=":id" element={<Editor />} />
    </Routes>
  );
}

/* ------------------------------------------------------------------ campaigns */
function Campaigns() {
  const { t, lang } = useI18n();
  const list = useLoad(() => api.get('/api/newsletters'), []);
  const types = useLoad(() => api.get('/api/newsletters/types'), []);
  const typeName = (id) => { const x = (types.data || []).find((y) => y.id === id); return x ? (x[lang] || x.en) : ''; };
  const account = useLoad(() => api.get('/api/email/settings'), []);
  const [creating, setCreating] = useState(false);
  useEffect(() => {
    if (!(list.data || []).some((n) => ['generating', 'sending'].includes(n.status))) return undefined;
    const id = setInterval(() => list.reload(true), 4000);
    return () => clearInterval(id);
  }, [list.data]); // eslint-disable-line react-hooks/exhaustive-deps
  if (list.loading && !list.data) return <Loading />;
  return (
    <>
      <PageHead title={t('nl_title')} sub={t('nl_sub')}>
        <Button variant="primary" icon={Plus} onClick={() => setCreating(true)}>{t('nl_new')}</Button>
      </PageHead>
      <Tabs />
      {account.data && !account.data.ready && (
        <div className="banner warn"><Settings2 size={16} /> {t('nl_connect_first')} <Link to="/newsletters/settings">{t('nl_sending')}</Link></div>
      )}
      {list.error && <ErrorBox error={list.error} onRetry={list.reload} />}
      {(list.data || []).length === 0 ? <Empty icon={Mail}>{t('nl_empty')}</Empty> : (
        <div className="stack">
          {list.data.map((n) => (
            <Link key={n.id} to={`/newsletters/${n.id}`} className="card card-pad row" style={{ color: 'inherit', textDecoration: 'none' }}>
              <div style={{ flex: '1 1 260px', minWidth: 0 }}>
                <b dir="auto">{n.subject || '…'}</b>
                <div className="xs muted">
                  {n.status === 'scheduled' && n.scheduled_at ? `${t('nl_scheduled_for')} ${fmtDateTime(n.scheduled_at, lang)}`
                    : n.sent_at ? fmtDateTime(n.sent_at, lang) : fmtDateTime(n.created_at, lang)}
                  {' · '}{t('nl_audience')}: {n.audience}
                </div>
              </div>
              <span className="pill">{TYPE_ICONS[n.kind] || '✉️'} {typeName(n.kind)}</span>
              <StatusPill status={STATUS_PILL[n.status] || n.status} label={t(`nl_st_${n.status}`)} />
              {n.stats.sent > 0 && (
                <div className="row xs" style={{ gap: 14 }}>
                  <span><b>{n.stats.sent}</b> {t('nl_sent')}</span>
                  <span><b>{n.stats.open_rate}%</b> {t('nl_opened')}</span>
                  <span><b>{n.stats.click_rate}%</b> {t('nl_clicked')}</span>
                </div>
              )}
            </Link>
          ))}
        </div>
      )}
      {creating && <NewNewsletter onClose={() => setCreating(false)} />}
    </>
  );
}

function NewNewsletter({ onClose }) {
  const { t, lang } = useI18n();
  const { user } = useAuth();
  const ex = useExample();
  const navigate = useNavigate();
  const types = useLoad(() => api.get('/api/newsletters/types'), []);
  const lists = useLoad(() => api.get('/api/contacts/lists'), []);
  const designs = useLoad(() => api.get('/api/newsletters/designs'), []);
  const posts = useLoad(() => api.get('/api/drafts?status=approved,scheduled,published&limit=30'), []);
  const products = useLoad(() => api.get('/api/products').catch(() => []), []);
  const articles = useLoad(() => api.get('/api/newsletters/articles').catch(() => []), []);
  const [f, setF] = useState({ kind: '', topic: '', list_ids: [], draft_ids: [], product_ids: [], article_ids: [],
    design: '', language: user?.org?.language || 'ar',
    event: { date: '', time: '', place: '', url: '' }, poll: { question: '', options: ['', '', ''] } });
  const [busy, run] = useAction();
  const set = (k, v) => setF((x) => ({ ...x, [k]: v }));
  const toggle = (k, id) => setF((x) => ({ ...x, [k]: x[k].includes(id) ? x[k].filter((i) => i !== id) : [...x[k], id] }));
  const kind = (types.data || []).find((x) => x.id === f.kind);
  const wants = (m) => kind?.material.includes(m);
  const create = () => run('create', async () => {
    const body = { ...f, design: f.design || null,
      event: kind?.event ? f.event : null,
      poll: kind?.poll && f.poll.question ? { question: f.poll.question, options: f.poll.options.filter(Boolean) } : null };
    const r = await api.post('/api/newsletters', body);
    navigate(`/newsletters/${r.id}`);
  });
  const postItems = posts.data?.items || posts.data || [];

  if (!f.kind) {
    return (
      <Modal wide title={t('nl_choose_type')} onClose={onClose} footer={<Button onClick={onClose}>{t('cancel')}</Button>}>
        <p className="small muted" style={{ marginTop: 0 }}>{t('nl_choose_type_hint')}</p>
        <div className="type-grid">
          {(types.data || []).map((x) => (
            <button type="button" key={x.id} className="type-card" onClick={() => set('kind', x.id)}>
              <span className="type-icon">{TYPE_ICONS[x.id] || '✉️'}</span>
              <b>{x[lang] || x.en}</b>
              <small>{x.desc[lang] || x.desc.en}</small>
            </button>
          ))}
        </div>
      </Modal>
    );
  }

  return (
    <Modal wide title={`${t('nl_new')} — ${kind?.[lang] || kind?.en || ''}`} onClose={onClose} footer={(
      <>
        <Button onClick={() => set('kind', '')}>{t('back')}</Button>
        <Button variant="primary" icon={Send} busy={busy === 'create'} onClick={create}>{t('nl_generate')}</Button>
      </>
    )}>
      <div className="stack">
        <div className="banner info small" style={{ margin: 0 }}>{TYPE_ICONS[f.kind]} {kind?.desc[lang] || kind?.desc.en}</div>
        <Field label={t('nl_topic')} hint={t('nl_topic_hint')}>
          <input className="input" value={f.topic} placeholder={ex('topic')} onChange={(e) => set('topic', e.target.value)} />
        </Field>
        {kind?.event && (
          <div className="grid grid-2">
            <Field label={t('nl_event_date')}><input className="input" type="date" value={f.event.date} onChange={(e) => set('event', { ...f.event, date: e.target.value })} /></Field>
            <Field label={t('nl_event_time')}><input className="input" type="time" value={f.event.time} onChange={(e) => set('event', { ...f.event, time: e.target.value })} /></Field>
            <Field label={t('nl_event_place')}><input className="input" value={f.event.place} onChange={(e) => set('event', { ...f.event, place: e.target.value })} /></Field>
            <Field label={t('nl_event_url')}><input className="input ltr" value={f.event.url} placeholder="https://" onChange={(e) => set('event', { ...f.event, url: e.target.value })} /></Field>
          </div>
        )}
        {kind?.poll && (
          <Field label={t('nl_poll_question')} hint={t('nl_poll_hint')}>
            <input className="input" value={f.poll.question} onChange={(e) => set('poll', { ...f.poll, question: e.target.value })} />
            <div className="grid grid-2" style={{ marginTop: 8 }}>
              {f.poll.options.map((o, i) => (
                <input key={i} className="input" value={o} placeholder={`${t('nl_poll_option')} ${i + 1}`}
                  onChange={(e) => { const options = [...f.poll.options]; options[i] = e.target.value; set('poll', { ...f.poll, options }); }} />
              ))}
              {f.poll.options.length < 6 && <Button size="sm" icon={Plus} onClick={() => set('poll', { ...f.poll, options: [...f.poll.options, ''] })}>{t('add')}</Button>}
            </div>
          </Field>
        )}
        <div className="grid grid-2">
          <Field label={t('nl_design')}>
            <select className="select" value={f.design} onChange={(e) => set('design', e.target.value)}>
              <option value="">{t('nl_design_auto')}</option>
              {(designs.data || []).map((d) => <option key={d.id} value={d.id}>{d[lang] || d.en}</option>)}
            </select>
          </Field>
          <Field label={t('content_language')}>
            <select className="select" value={f.language} onChange={(e) => set('language', e.target.value)}>
              {LANGUAGES.map((l) => <option key={l.id} value={l.id}>{l.label}</option>)}
            </select>
          </Field>
        </div>
        <Field label={t('nl_to_lists')} hint={t('nl_all_lists_hint')}>
          <div className="row" style={{ gap: 6 }}>
            {(lists.data || []).map((l) => (
              <button type="button" key={l.id} className={`btn btn-sm ${f.list_ids.includes(l.id) ? 'btn-primary' : ''}`}
                onClick={() => toggle('list_ids', l.id)}>{l.name} ({l.subscribed})</button>
            ))}
            {!(lists.data || []).length && <span className="xs muted">{t('nl_no_lists')}</span>}
          </div>
        </Field>
        {wants('articles') && (articles.data || []).length > 0 && (
          <Field label={t('nl_feature_articles')}>
            <div className="pick-grid">
              {articles.data.map((a) => (
                <label key={a.id} className={`pick ${f.article_ids.includes(a.id) ? 'on' : ''}`}>
                  <input type="checkbox" checked={f.article_ids.includes(a.id)} onChange={() => toggle('article_ids', a.id)} />
                  {a.image_url && <img src={mediaUrl(a.image_url)} alt="" />}
                  <span className="clamp-2" dir="auto">{a.title}</span>
                  <small className="muted">{a.source}</small>
                </label>
              ))}
            </div>
          </Field>
        )}
        {wants('posts') && postItems.length > 0 && (
          <Field label={t('nl_feature_posts')}>
            <div className="pick-grid">
              {postItems.map((d) => (
                <label key={d.id} className={`pick ${f.draft_ids.includes(d.id) ? 'on' : ''}`}>
                  <input type="checkbox" checked={f.draft_ids.includes(d.id)} onChange={() => toggle('draft_ids', d.id)} />
                  {d.cover_url && <img src={mediaUrl(d.cover_url)} alt="" />}
                  <span className="clamp-2" dir="auto">{d.hook}</span>
                </label>
              ))}
            </div>
          </Field>
        )}
        {wants('products') && (products.data || []).length > 0 && (
          <Field label={t('nl_feature_products')}>
            <div className="pick-grid">
              {products.data.slice(0, 40).map((p) => (
                <label key={p.id} className={`pick ${f.product_ids.includes(p.id) ? 'on' : ''}`}>
                  <input type="checkbox" checked={f.product_ids.includes(p.id)} onChange={() => toggle('product_ids', p.id)} />
                  {p.image_url && <img src={mediaUrl(p.image_url)} alt="" />}
                  <span className="clamp-2" dir="auto">{p.name}</span>
                </label>
              ))}
            </div>
          </Field>
        )}
      </div>
    </Modal>
  );
}

const TYPE_ICONS = { curated: '🔗', educational: '🎓', reporting: '📰', roundup: '📝', story: '📖', analysis: '📊',
  promotional: '🏷️', update: '🚀', internal: '🏢', survey: '🗳️', event: '📅', hybrid: '🧩' };

/* ------------------------------------------------------------------ editor + stats */
function Editor() {
  const { id } = useParams();
  const { t, lang } = useI18n();
  const navigate = useNavigate();
  const nl = useLoad(() => api.get(`/api/newsletters/${id}`), [id]);
  const designs = useLoad(() => api.get('/api/newsletters/designs'), []);
  const lists = useLoad(() => api.get('/api/contacts/lists'), []);
  const types = useLoad(() => api.get('/api/newsletters/types'), []);
  const [f, setF] = useState(null);
  const [html, setHtml] = useState('');
  const [when, setWhen] = useState('');
  const [testTo, setTestTo] = useState('');
  const [busy, run] = useAction();
  const frame = useRef(null);

  useEffect(() => {
    if (nl.data) setF({ kind: nl.data.kind, subject: nl.data.subject, preheader: nl.data.preheader, design: nl.data.design,
      language: nl.data.language, list_ids: nl.data.list_ids || [], content: structuredClone(nl.data.content || {}) });
  }, [nl.data]);
  useEffect(() => {
    if (nl.data?.status !== 'generating' && nl.data?.status !== 'sending') return undefined;
    const t2 = setInterval(() => nl.reload(true), 3000);
    return () => clearInterval(t2);
  }, [nl.data?.status]); // eslint-disable-line react-hooks/exhaustive-deps
  const loadPreview = (design) => api.get(`/api/newsletters/${id}/preview${design ? `?design=${design}` : ''}`).then((r) => setHtml(r.html)).catch(() => {});
  useEffect(() => { if (nl.data && nl.data.status !== 'generating') loadPreview(); }, [nl.data?.updated_at, nl.data?.status]); // eslint-disable-line

  if (!nl.data || !f) return nl.error ? <ErrorBox error={nl.error} /> : <Loading />;
  const d = nl.data;
  const locked = ['sending', 'sent'].includes(d.status);
  const set = (k, v) => setF((x) => ({ ...x, [k]: v }));
  const setC = (k, v) => setF((x) => ({ ...x, content: { ...x.content, [k]: v } }));
  const setSec = (i, k, v) => setF((x) => {
    const sections = [...(x.content.sections || [])];
    sections[i] = { ...sections[i], [k]: v };
    return { ...x, content: { ...x.content, sections } };
  });
  const sections = f.content.sections || [];
  const save = () => run('save', async () => { await api.patch(`/api/newsletters/${id}`, f); await nl.reload(true); }, t('saved'));
  const send = (schedule) => run('send', async () => {
    await api.patch(`/api/newsletters/${id}`, f);
    const body = schedule && when ? { when: new Date(when).toISOString() } : {};
    if (!schedule && !window.confirm(`${t('nl_confirm_send')} (${d.audience})`)) return;
    await api.post(`/api/newsletters/${id}/send`, body);
    nl.reload(true);
  }, schedule ? t('nl_scheduled_ok') : t('nl_sending_now'));

  if (d.status === 'generating') {
    return (<><PageHead title={t('nl_title')} /><div className="banner info"><Spinner size={16} /> {t('nl_generating')}</div></>);
  }

  return (
    <>
      <PageHead title={f.subject || t('nl_title')} sub={`${t(`nl_st_${d.status}`)} · ${t('nl_audience')}: ${d.audience}`}>
        <Button icon={Copy} busy={busy === 'dup'} onClick={() => run('dup', async () => {
          const r = await api.post(`/api/newsletters/${id}/duplicate`); navigate(`/newsletters/${r.id}`);
        })}>{t('nl_duplicate')}</Button>
        {!locked && <Button variant="danger" icon={Trash2} onClick={() => window.confirm(t('confirm_delete')) && run('del', async () => {
          await api.del(`/api/newsletters/${id}`); navigate('/newsletters');
        })} />}
      </PageHead>
      <Tabs />
      {d.error && <div className="banner danger">{d.error}</div>}
      {(d.stats.recipients > 0) && <Stats id={id} stats={d.stats} />}

      <div className="editor">
        <div className="stack">
          <div className="card card-pad stack">
            <Field label={t('nl_type')}>
              <select className="select" disabled={locked} value={f.kind} onChange={(e) => set('kind', e.target.value)}>
                {(types.data || []).map((x) => <option key={x.id} value={x.id}>{TYPE_ICONS[x.id]} {x[lang] || x.en}</option>)}
              </select>
            </Field>
            <Field label={t('nl_subject')}><input className="input" dir="auto" disabled={locked} value={f.subject} onChange={(e) => set('subject', e.target.value)} /></Field>
            <Field label={t('nl_preheader')} hint={t('nl_preheader_hint')}><input className="input" dir="auto" disabled={locked} value={f.preheader} onChange={(e) => set('preheader', e.target.value)} /></Field>
            <Field label={t('nl_design')}>
              <div className="row" style={{ gap: 6 }}>
                {(designs.data || []).map((x) => (
                  <button type="button" key={x.id} disabled={locked} className={`btn btn-sm ${f.design === x.id ? 'btn-primary' : ''}`}
                    onClick={() => { set('design', x.id); loadPreview(x.id); }}>{x[lang] || x.en}</button>
                ))}
              </div>
            </Field>
            <Field label={t('nl_to_lists')} hint={t('nl_all_lists_hint')}>
              <div className="row" style={{ gap: 6 }}>
                {(lists.data || []).map((l) => (
                  <button type="button" key={l.id} disabled={locked} className={`btn btn-sm ${f.list_ids.includes(l.id) ? 'btn-primary' : ''}`}
                    onClick={() => set('list_ids', f.list_ids.includes(l.id) ? f.list_ids.filter((i) => i !== l.id) : [...f.list_ids, l.id])}>
                    {l.name} ({l.subscribed})
                  </button>
                ))}
              </div>
            </Field>
          </div>
          <div className="card card-pad stack">
            <Field label={t('nl_headline')}><input className="input" dir="auto" disabled={locked} value={f.content.headline || ''} onChange={(e) => setC('headline', e.target.value)} /></Field>
            <Field label={t('nl_intro')}><textarea className="textarea" dir="auto" rows={3} disabled={locked} value={f.content.intro || ''} onChange={(e) => setC('intro', e.target.value)} /></Field>
            <Field label={t('nl_hero')}><input className="input ltr" disabled={locked} value={f.content.hero_image || ''} onChange={(e) => setC('hero_image', e.target.value)} /></Field>
          </div>
          {(f.kind === 'event' || f.content.event) && (
            <div className="card card-pad grid grid-2">
              {['date', 'time', 'place', 'url'].map((k) => (
                <Field key={k} label={t(`nl_event_${k}`)}>
                  <input className={`input ${k === 'url' ? 'ltr' : ''}`} disabled={locked} value={(f.content.event || {})[k] || ''}
                    onChange={(e) => setC('event', { ...(f.content.event || {}), [k]: e.target.value })} />
                </Field>
              ))}
            </div>
          )}
          {(f.kind === 'survey' || f.content.poll) && (
            <div className="card card-pad stack">
              <Field label={t('nl_poll_question')}>
                <input className="input" dir="auto" disabled={locked} value={(f.content.poll || {}).question || ''}
                  onChange={(e) => setC('poll', { options: [], ...(f.content.poll || {}), question: e.target.value })} />
              </Field>
              {((f.content.poll || {}).options || []).map((o, i) => (
                <input key={i} className="input" dir="auto" disabled={locked} value={o} onChange={(e) => {
                  const options = [...f.content.poll.options]; options[i] = e.target.value; setC('poll', { ...f.content.poll, options });
                }} />
              ))}
              {!locked && <Button size="sm" icon={Plus} onClick={() => setC('poll', { question: '', ...(f.content.poll || {}), options: [...((f.content.poll || {}).options || []), ''] })}>{t('nl_poll_option')}</Button>}
            </div>
          )}
          {sections.map((s, i) => (
            <div key={i} className="card card-pad stack">
              <div className="field-head"><b className="small">{t('nl_section')} {i + 1}</b>
                {!locked && <Button size="sm" variant="ghost" icon={X} onClick={() => setC('sections', sections.filter((_, j) => j !== i))} />}</div>
              <input className="input" dir="auto" disabled={locked} placeholder={t('nl_section_title')} value={s.title || ''} onChange={(e) => setSec(i, 'title', e.target.value)} />
              <textarea className="textarea" dir="auto" rows={3} disabled={locked} value={s.text || ''} onChange={(e) => setSec(i, 'text', e.target.value)} />
              <div className="grid grid-2">
                <input className="input ltr" disabled={locked} placeholder={t('nl_image_url')} value={s.image || ''} onChange={(e) => setSec(i, 'image', e.target.value)} />
                <input className="input ltr" disabled={locked} placeholder={t('nl_link')} value={s.link || ''} onChange={(e) => setSec(i, 'link', e.target.value)} />
              </div>
              <input className="input" dir="auto" disabled={locked} placeholder={t('nl_button')} value={s.button || ''} onChange={(e) => setSec(i, 'button', e.target.value)} />
            </div>
          ))}
          {!locked && <Button icon={Plus} onClick={() => setC('sections', [...sections, { title: '', text: '' }])}>{t('nl_add_section')}</Button>}
          <div className="card card-pad stack">
            <div className="grid grid-2">
              <Field label={t('nl_cta_text')}><input className="input" dir="auto" disabled={locked} value={f.content.cta_text || ''} onChange={(e) => setC('cta_text', e.target.value)} /></Field>
              <Field label={t('nl_cta_url')}><input className="input ltr" disabled={locked} value={f.content.cta_url || ''} onChange={(e) => setC('cta_url', e.target.value)} /></Field>
            </div>
            <Field label="P.S."><input className="input" dir="auto" disabled={locked} value={f.content.ps || ''} onChange={(e) => setC('ps', e.target.value)} /></Field>
          </div>
          {!locked && (
            <div className="card card-pad stack">
              <div className="row">
                <Button variant="primary" icon={Save} busy={busy === 'save'} onClick={save}>{t('save')}</Button>
                <Button icon={Eye} onClick={() => run('pv', async () => { await api.patch(`/api/newsletters/${id}`, f); await loadPreview(); })}>{t('nl_refresh_preview')}</Button>
              </div>
              <div className="row" style={{ flexWrap: 'nowrap', gap: 8 }}>
                <input className="input ltr" type="email" placeholder="you@company.com" value={testTo} onChange={(e) => setTestTo(e.target.value)} />
                <Button icon={MailCheck} busy={busy === 'test'} disabled={!testTo} onClick={() => run('test', async () => {
                  await api.patch(`/api/newsletters/${id}`, f); await api.post(`/api/newsletters/${id}/test`, { to: testTo });
                }, t('nl_test_sent'))}>{t('nl_send_test')}</Button>
              </div>
              <div className="divider" />
              {d.status === 'scheduled' ? (
                <div className="row">
                  <span className="pill info"><Calendar size={12} /> {fmtDateTime(d.scheduled_at, lang)}</span>
                  <Button icon={X} busy={busy === 'cancel'} onClick={() => run('cancel', async () => { await api.post(`/api/newsletters/${id}/cancel`); nl.reload(true); })}>{t('unschedule')}</Button>
                </div>
              ) : (
                <div className="row">
                  <Button variant="gold" icon={Send} busy={busy === 'send'} onClick={() => send(false)}>{t('nl_send_now')}</Button>
                  <input className="input ltr" style={{ width: 'auto' }} type="datetime-local" min={toLocalInput(new Date())} value={when} onChange={(e) => setWhen(e.target.value)} />
                  <Button icon={Calendar} disabled={!when} busy={busy === 'send'} onClick={() => send(true)}>{t('nl_schedule')}</Button>
                </div>
              )}
            </div>
          )}
        </div>
        <div className="card" style={{ overflow: 'hidden', position: 'sticky', top: 16, alignSelf: 'start' }}>
          <iframe ref={frame} title="preview" srcDoc={html} style={{ width: '100%', height: '78vh', border: 0, background: '#f2f2f2' }} />
        </div>
      </div>
    </>
  );
}

function Stats({ id, stats }) {
  const { t, lang } = useI18n();
  const [filter, setFilter] = useState('');
  const rows = useLoad(() => api.get(`/api/newsletters/${id}/recipients${filter ? `?filter=${filter}` : ''}`), [id, filter]);
  const tiles = [
    ['recipients', stats.recipients], ['sent', stats.sent], ['opened', `${stats.opened} · ${stats.open_rate}%`],
    ['clicked', `${stats.clicked} · ${stats.click_rate}%`], ['unsubscribed', stats.unsubscribed], ['failed', stats.failed],
  ];
  return (
    <div className="card card-pad stack" style={{ marginBottom: 16 }}>
      <h3><BarChart3 size={16} /> {t('nl_stats')}</h3>
      <div className="stat-tiles">
        {tiles.map(([k, v]) => <div key={k} className="stat-tile"><b>{v}</b><span>{t(`nl_${k}`)}</span></div>)}
      </div>
      {stats.poll && (
        <div className="stack" style={{ gap: 6 }}>
          <b className="small">{t('nl_poll_results')}</b>
          {stats.poll.map((o) => (
            <div key={o.option} className="poll-bar">
              <span dir="auto">{o.option}</span>
              <div><i style={{ width: `${o.percent}%` }} /></div>
              <b>{o.votes} · {o.percent}%</b>
            </div>
          ))}
        </div>
      )}
      <div className="row" style={{ gap: 6 }}>
        {['', 'opened', 'clicked', 'unopened', 'unsubscribed', 'failed'].map((k) => (
          <button key={k || 'all'} className={`btn btn-sm ${filter === k ? 'btn-primary' : ''}`} onClick={() => setFilter(k)}>
            {k ? t(`nl_${k}`) : t('products_all')}
          </button>
        ))}
      </div>
      <div style={{ maxHeight: 320, overflow: 'auto' }}>
        <table className="table small">
          <thead><tr><th>{t('email')}</th><th>{t('nl_status')}</th><th>{t('nl_opened')}</th><th>{t('nl_clicked')}</th></tr></thead>
          <tbody>
            {(rows.data || []).map((r) => (
              <tr key={r.id}>
                <td className="ltr">{r.email}{r.name ? ` — ${r.name}` : ''}</td>
                <td>{r.unsubscribed_at ? t('nl_unsubscribed') : t(`nl_d_${r.status}`)}{r.error ? <div className="xs muted">{r.error}</div> : null}</td>
                <td>{r.opened_at ? `${fmtDateTime(r.opened_at, lang)} (${r.open_count})` : '—'}</td>
                <td>{r.clicked_at ? `${fmtDateTime(r.clicked_at, lang)} (${r.click_count})` : '—'}</td>
                {stats.poll && <td dir="auto">{r.answer || '—'}</td>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ contacts */
function Contacts() {
  const { t } = useI18n();
  const lists = useLoad(() => api.get('/api/contacts/lists'), []);
  const [listId, setListId] = useState('');
  const [q, setQ] = useState('');
  const [query, setQuery] = useState('');
  const data = useLoad(() => api.get(`/api/contacts?limit=500${listId ? `&list_id=${listId}` : ''}${query ? `&q=${encodeURIComponent(query)}` : ''}`), [listId, query]);
  const [modal, setModal] = useState(null);
  const [target, setTarget] = useState('');
  const [busy, run] = useAction();
  const items = data.data?.items || [];
  const sel = useSelection(items);
  const names = Object.fromEntries((lists.data || []).map((l) => [l.id, l.name]));
  const bulk = (action) => run(`bulk-${action}`, async () => {
    await api.post('/api/contacts/bulk', { ids: sel.ids, action, list_id: target ? Number(target) : null });
    sel.clear(); data.reload(true); lists.reload(true);
  }, t('done'));
  return (
    <>
      <PageHead title={t('nl_contacts')} sub={t('nl_contacts_sub')}>
        <Button icon={Download} onClick={() => api.download(`/api/contacts/export.csv${listId ? `?list_id=${listId}` : ''}`, 'contacts.csv')}>{t('nl_export')}</Button>
        <Button icon={UserPlus} onClick={() => setModal('add')}>{t('nl_add_contact')}</Button>
        <Button variant="primary" icon={FileUp} onClick={() => setModal('import')}>{t('nl_import')}</Button>
      </PageHead>
      <Tabs />
      <div className="row" style={{ marginBottom: 12 }}>
        <select className="select" style={{ width: 'auto' }} value={listId} onChange={(e) => setListId(e.target.value)}>
          <option value="">{t('nl_all_contacts')}</option>
          {(lists.data || []).map((l) => <option key={l.id} value={l.id}>{l.name} ({l.members})</option>)}
        </select>
        <form className="row" style={{ flexWrap: 'nowrap', gap: 6 }} onSubmit={(e) => { e.preventDefault(); setQuery(q.trim()); }}>
          <input className="input" value={q} placeholder={t('nl_search_contacts')} onChange={(e) => setQ(e.target.value)} />
          <Button type="submit" icon={RefreshCw} />
        </form>
        <span className="xs muted">{data.data?.total ?? 0} {t('nl_contacts_count')}</span>
        <div className="spacer" />
        {items.length > 0 && <SelectAll sel={sel} label={t('select_all')} />}
      </div>
      {data.error && <ErrorBox error={data.error} />}
      {items.length === 0 ? <Empty icon={Users}>{t('nl_no_contacts')}</Empty> : (
        <div className="card" style={{ overflow: 'auto' }}>
          <table className="table small">
            <thead><tr><th /><th>{t('email')}</th><th>{t('your_name')}</th><th>{t('nl_lists')}</th><th>{t('nl_status')}</th></tr></thead>
            <tbody>
              {items.map((c) => (
                <tr key={c.id}>
                  <td><input type="checkbox" checked={sel.has(c.id)} onChange={() => sel.toggle(c.id)} /></td>
                  <td className="ltr">{c.email}</td>
                  <td dir="auto">{c.name}</td>
                  <td>{(c.list_ids || []).map((i) => names[i]).filter(Boolean).join('، ')}</td>
                  <td><span className={`pill ${c.status === 'subscribed' ? 'ok' : ''}`}>{t(`nl_c_${c.status}`)}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {sel.count > 0 && (
        <div className="row" style={{ marginTop: 10 }}>
          <select className="select" style={{ width: 'auto' }} value={target} onChange={(e) => setTarget(e.target.value)}>
            <option value="">{t('nl_choose_list')}</option>
            {(lists.data || []).map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
          </select>
        </div>
      )}
      <BulkBar sel={sel} busy={busy} selectedLabel={t('selected')} clearLabel={t('clear_selection')} onAction={bulk}
        actions={[
          { key: 'add_to_list', label: t('nl_add_to_list'), icon: ListPlus },
          { key: 'remove_from_list', label: t('nl_remove_from_list'), icon: X },
          { key: 'unsubscribe', label: t('nl_unsubscribe'), icon: UserMinus },
          { key: 'resubscribe', label: t('nl_resubscribe'), icon: UserPlus },
          { key: 'delete', label: t('delete'), icon: Trash2, variant: 'danger', confirm: t('confirm_delete') },
        ]} />
      {modal === 'import' && <ImportModal lists={lists.data || []} onClose={() => setModal(null)} onDone={() => { data.reload(true); lists.reload(true); }} />}
      {modal === 'add' && <AddContact lists={lists.data || []} onClose={() => setModal(null)} onDone={() => { data.reload(true); lists.reload(true); }} />}
    </>
  );
}

function ListChooser({ lists, value, onChange, newList, setNewList }) {
  const { t } = useI18n();
  return (
    <div className="grid grid-2">
      <Field label={t('nl_add_to_list')}>
        <select className="select" value={value} onChange={(e) => onChange(e.target.value)}>
          <option value="">—</option>
          {lists.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
        </select>
      </Field>
      <Field label={t('nl_or_new_list')}><input className="input" value={newList} onChange={(e) => setNewList(e.target.value)} /></Field>
    </div>
  );
}

function ImportModal({ lists, onClose, onDone }) {
  const { t } = useI18n();
  const [listId, setListId] = useState('');
  const [newList, setNewList] = useState('');
  const [text, setText] = useState('');
  const [result, setResult] = useState(null);
  const [busy, run] = useAction();
  const fileRef = useRef(null);
  const upload = (file) => run('file', async () => {
    const extra = { new_list: newList };
    if (listId) extra.list_id = listId;
    setResult(await api.upload('/api/contacts/import', file, extra));
    onDone();
  });
  const paste = () => run('paste', async () => {
    setResult(await api.post('/api/contacts/import-text', { text, list_id: listId ? Number(listId) : null, new_list: newList }));
    onDone();
  });
  return (
    <Modal title={t('nl_import')} onClose={onClose} footer={<Button onClick={onClose}>{t('close')}</Button>}>
      <div className="stack">
        <ListChooser lists={lists} value={listId} onChange={setListId} newList={newList} setNewList={setNewList} />
        <div className="banner info small" style={{ margin: 0 }}>{t('nl_import_hint')}</div>
        <Button variant="primary" icon={FileUp} busy={busy === 'file'} onClick={() => fileRef.current?.click()}>{t('nl_choose_file')}</Button>
        <input ref={fileRef} type="file" hidden accept=".xlsx,.xlsm,.csv,.tsv,.txt,.vcf"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) upload(f); e.target.value = ''; }} />
        <div className="divider" />
        <Field label={t('nl_paste')} hint={t('nl_paste_hint')}>
          <textarea className="textarea ltr" rows={5} value={text} onChange={(e) => setText(e.target.value)} placeholder={'sara@example.com\nOmar <omar@example.com>'} />
        </Field>
        <Button icon={Plus} busy={busy === 'paste'} disabled={!text.trim()} onClick={paste}>{t('add')}</Button>
        {result && <div className="banner ok small" style={{ margin: 0 }}>{t('nl_added')}: {result.added} · {t('nl_updated')}: {result.updated} · {t('nl_invalid')}: {result.invalid}</div>}
        <p className="xs muted">{t('nl_consent')}</p>
      </div>
    </Modal>
  );
}

function AddContact({ lists, onClose, onDone }) {
  const { t } = useI18n();
  const [f, setF] = useState({ email: '', name: '', list_ids: [] });
  const [busy, run] = useAction();
  return (
    <Modal title={t('nl_add_contact')} onClose={onClose} footer={(
      <>
        <Button onClick={onClose}>{t('cancel')}</Button>
        <Button variant="primary" busy={busy === 'add'} disabled={!f.email} onClick={() => run('add', async () => {
          await api.post('/api/contacts', f); onDone(); onClose();
        }, t('saved'))}>{t('add')}</Button>
      </>
    )}>
      <div className="stack">
        <Field label={t('email')}><input className="input ltr" type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></Field>
        <Field label={t('your_name')}><input className="input" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
        <div className="row" style={{ gap: 6 }}>
          {lists.map((l) => (
            <button type="button" key={l.id} className={`btn btn-sm ${f.list_ids.includes(l.id) ? 'btn-primary' : ''}`}
              onClick={() => setF({ ...f, list_ids: f.list_ids.includes(l.id) ? f.list_ids.filter((i) => i !== l.id) : [...f.list_ids, l.id] })}>{l.name}</button>
          ))}
        </div>
      </div>
    </Modal>
  );
}

/* ------------------------------------------------------------------ lists */
function Lists() {
  const { t } = useI18n();
  const lists = useLoad(() => api.get('/api/contacts/lists'), []);
  const [name, setName] = useState('');
  const [busy, run] = useAction();
  return (
    <>
      <PageHead title={t('nl_lists')} sub={t('nl_lists_sub')} />
      <Tabs />
      <div className="card card-pad row" style={{ marginBottom: 16, flexWrap: 'nowrap', gap: 8 }}>
        <input className="input" value={name} placeholder={t('nl_list_name')} onChange={(e) => setName(e.target.value)} />
        <Button variant="primary" icon={Plus} busy={busy === 'add'} disabled={!name.trim()} onClick={() => run('add', async () => {
          await api.post('/api/contacts/lists', { name }); setName(''); lists.reload(true);
        })}>{t('add')}</Button>
      </div>
      {(lists.data || []).length === 0 ? <Empty icon={ListPlus}>{t('nl_no_lists')}</Empty> : (
        <div className="stack">
          {lists.data.map((l) => (
            <div key={l.id} className="card card-pad row">
              <div style={{ flex: 1 }}><b>{l.name}</b><div className="xs muted">{l.members} {t('nl_contacts_count')} · {l.subscribed} {t('nl_c_subscribed')}</div></div>
              <Link className="btn btn-sm" to={`/newsletters/contacts`}>{t('nl_contacts')}</Link>
              <Button size="sm" onClick={() => { const n = window.prompt(t('nl_list_name'), l.name); if (n) run(`r-${l.id}`, async () => { await api.patch(`/api/contacts/lists/${l.id}`, { name: n }); lists.reload(true); }); }}>{t('edit')}</Button>
              <Button size="sm" variant="danger" icon={Trash2} onClick={() => window.confirm(t('confirm_delete')) && run(`d-${l.id}`, async () => { await api.del(`/api/contacts/lists/${l.id}`); lists.reload(true); })} />
            </div>
          ))}
        </div>
      )}
    </>
  );
}

/* ------------------------------------------------------------------ sending account */
function SendingAccount() {
  const { t } = useI18n();
  const { can } = useAuth();
  const cfg = useLoad(() => api.get('/api/email/settings'), []);
  const [f, setF] = useState(null);
  const [testTo, setTestTo] = useState('');
  const [busy, run] = useAction();
  useEffect(() => {
    if (cfg.data) {
      const { presets, ready, smtp_password, brevo_api_key, resend_api_key, ...rest } = cfg.data; // eslint-disable-line no-unused-vars
      setF({ ...rest, smtp_password: '', brevo_api_key: '', resend_api_key: '' });
    }
  }, [cfg.data]);
  if (!f) return <Loading />;
  const v = cfg.data;
  const set = (k, x) => setF((y) => ({ ...y, [k]: x }));
  const save = () => run('save', async () => { cfg.setData(await api.put('/api/email/settings', f)); }, t('saved'));
  const owner = can('owner');
  const secret = (k) => (
    <>
      <input className="input ltr" type="password" autoComplete="new-password" disabled={!owner} value={f[k]} placeholder={v[k]?.set ? `•••• ${v[k].hint}` : ''} onChange={(e) => set(k, e.target.value)} />
    </>
  );
  return (
    <>
      <PageHead title={t('nl_sending')} sub={t('nl_sending_sub')} />
      <Tabs />
      <div className="grid grid-2" style={{ alignItems: 'start' }}>
        <div className="card card-pad stack">
          <span className={`pill ${v.ready ? 'ok' : ''}`} style={{ alignSelf: 'flex-start' }}>{v.ready ? t('nl_ready') : t('nl_not_ready')}</span>
          <Field label={t('nl_provider')}>
            <div className="row" style={{ gap: 6 }}>
              {[['brevo', 'Brevo'], ['resend', 'Resend'], ['smtp', t('nl_smtp')]].map(([id, label]) => (
                <button key={id} type="button" disabled={!owner} className={`btn btn-sm ${f.provider === id ? 'btn-primary' : ''}`} onClick={() => set('provider', id)}>{label}</button>
              ))}
            </div>
          </Field>
          <p className="xs muted" style={{ marginTop: -6 }}>{t(`nl_provider_${f.provider}`)}</p>
          <div className="grid grid-2">
            <Field label={t('nl_from_name')}><input className="input" disabled={!owner} value={f.from_name} onChange={(e) => set('from_name', e.target.value)} /></Field>
            <Field label={t('nl_from_email')} hint={t('nl_from_hint')}><input className="input ltr" disabled={!owner} value={f.from_email} onChange={(e) => set('from_email', e.target.value)} /></Field>
            <Field label={t('nl_reply_to')}><input className="input ltr" disabled={!owner} value={f.reply_to} onChange={(e) => set('reply_to', e.target.value)} /></Field>
            <Field label={t('nl_per_minute')}><input className="input" type="number" min={1} max={1000} disabled={!owner} value={f.batch_per_minute} onChange={(e) => set('batch_per_minute', e.target.value)} /></Field>
          </div>
          {f.provider === 'brevo' && <Field label="Brevo API key" hint="app.brevo.com → SMTP & API → API keys">{secret('brevo_api_key')}</Field>}
          {f.provider === 'resend' && <Field label="Resend API key" hint="resend.com/api-keys">{secret('resend_api_key')}</Field>}
          {f.provider === 'smtp' && (
            <>
              <Field label={t('nl_preset')}>
                <select className="select" disabled={!owner} defaultValue="" onChange={(e) => {
                  const p = v.presets?.[e.target.value]; if (p) setF((y) => ({ ...y, smtp_host: p.smtp_host, smtp_port: p.smtp_port, smtp_security: p.smtp_security }));
                }}>
                  <option value="">—</option>
                  {Object.entries(v.presets || {}).map(([id, p]) => <option key={id} value={id}>{p.label}</option>)}
                </select>
              </Field>
              <div className="grid grid-2">
                <Field label="SMTP host"><input className="input ltr" disabled={!owner} value={f.smtp_host} onChange={(e) => set('smtp_host', e.target.value)} /></Field>
                <Field label={t('nl_port')}><input className="input ltr" type="number" disabled={!owner} value={f.smtp_port} onChange={(e) => set('smtp_port', e.target.value)} /></Field>
                <Field label={t('nl_security')}>
                  <select className="select" disabled={!owner} value={f.smtp_security} onChange={(e) => set('smtp_security', e.target.value)}>
                    <option value="starttls">STARTTLS (587)</option><option value="ssl">SSL/TLS (465)</option><option value="none">—</option>
                  </select>
                </Field>
                <Field label={t('nl_smtp_user')}><input className="input ltr" disabled={!owner} value={f.smtp_user} onChange={(e) => set('smtp_user', e.target.value)} /></Field>
              </div>
              <Field label={t('password')} hint={t('nl_app_password')}>{secret('smtp_password')}</Field>
              <div className="banner warn small" style={{ margin: 0 }}>{t('nl_smtp_warning')}</div>
            </>
          )}
          <Field label={t('nl_address')} hint={t('nl_address_hint')}><input className="input" disabled={!owner} value={f.company_address} onChange={(e) => set('company_address', e.target.value)} /></Field>
          {owner && <div><Button variant="primary" icon={Save} busy={busy === 'save'} onClick={save}>{t('save')}</Button></div>}
        </div>
        <div className="card card-pad stack">
          <h3><MailCheck size={16} /> {t('nl_send_test')}</h3>
          <div className="row" style={{ flexWrap: 'nowrap', gap: 8 }}>
            <input className="input ltr" type="email" value={testTo} placeholder="you@company.com" onChange={(e) => setTestTo(e.target.value)} />
            <Button icon={Send} busy={busy === 'test'} disabled={!testTo || !v.ready} onClick={() => run('test', () => api.post('/api/email/test', { to: testTo }), t('nl_test_sent'))}>{t('nl_send_test')}</Button>
          </div>
          <p className="xs muted">{t('nl_deliverability')}</p>
        </div>
      </div>
    </>
  );
}
