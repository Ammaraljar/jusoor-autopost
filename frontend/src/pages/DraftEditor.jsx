import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { AlertTriangle, ArrowRight, Bot, Check, CheckCircle2, ChevronLeft, ChevronRight, Clock, Download, ExternalLink,
  ImagePlus, Images, RotateCcw, Save, Send, Sparkles, Trash2, Wand2, X, XCircle } from 'lucide-react';
import { Button, ErrorBox, Field, Loading, Modal, Spinner, StatusPill, useAction, useLoad } from '../components/ui';
import { api, mediaUrl } from '../lib/api';
import { fmtDate, fmtDateTime, toLocalInput } from '../lib/format';
import { useI18n } from '../lib/i18n';

const TEXT_FIELDS = ['hook', 'subtitle', 'caption', 'hashtags', 'first_comment', 'cta'];
const REGEN_FIELDS = ['hook', 'subtitle', 'caption', 'cta', 'first_comment'];
const BADGES = ['news', 'tips', 'guide', 'offer', 'event', 'culture', 'food'];

export default function DraftEditor() {
  const { id } = useParams();
  const { t, lang } = useI18n();
  const navigate = useNavigate();
  const draft = useLoad(() => api.get(`/api/drafts/${id}`), [id]);
  const campaigns = useLoad(() => api.get('/api/campaigns'), []);
  const [form, setForm] = useState({});
  const [dirty, setDirty] = useState(false);
  const [active, setActive] = useState(0);
  const [busy, run] = useAction();
  const [modal, setModal] = useState(null);
  const d = draft.data;

  useEffect(() => {
    if (d && !dirty) {
      setForm(Object.fromEntries([...TEXT_FIELDS, 'badge', 'campaign_id'].map((k) => [k, d[k] ?? ''])));
    }
  }, [d]); // eslint-disable-line react-hooks/exhaustive-deps

  // Poll while generating / publishing
  useEffect(() => {
    if (!d || !['generating', 'publishing'].includes(d.status)) return undefined;
    const iv = setInterval(() => draft.reload(true), 4000);
    return () => clearInterval(iv);
  }, [d?.status]); // eslint-disable-line react-hooks/exhaustive-deps

  if (draft.loading && !d) return <Loading />;
  if (draft.error) return <ErrorBox error={draft.error} onRetry={draft.reload} />;
  if (!d) return null;

  const slides = d.slides || [];
  const slide = slides[Math.min(active, slides.length - 1)];
  const set = (k, v) => { setForm((f) => ({ ...f, [k]: v })); setDirty(true); };
  const apply = (data) => { draft.setData(data); setDirty(false); };
  const act = (key, fn, msg) => run(key, async () => { const res = await fn(); if (res?.id) apply(res); return res; }, msg);

  const save = () => act('save', () => api.patch(`/api/drafts/${d.id}`, {
    ...form, campaign_id: form.campaign_id ? Number(form.campaign_id) : null,
  }), t('saved'));
  const regen = (field) => act(`regen-${field}`, () => api.post(`/api/drafts/${d.id}/regenerate`, { field }));
  const locked = ['publishing', 'published', 'generating'].includes(d.status);
  const origin = d.origin === 'source' ? d.source_name : d.origin === 'calendar' ? t('calendar_origin') : t('manual');

  return (
    <>
      <div className="page-head">
        <div className="row" style={{ alignItems: 'flex-start' }}>
          <Link to="/" className="btn btn-ghost icon-btn" aria-label={t('back')}>
            <ArrowRight size={18} style={{ transform: lang === 'ar' ? 'none' : 'scaleX(-1)' }} />
          </Link>
          <div>
            <h1 style={{ fontSize: 22 }} dir="auto">{d.hook || d.original_title}</h1>
            <div className="row small muted">
              <StatusPill status={d.status} />
              <span>{origin}</span>
              <span>·</span>
              <span>{fmtDate(d.original_published_at || d.created_at, lang)}</span>
              {d.relevance != null && <span className="pill">{t('relevance')} {d.relevance}/10</span>}
              {d.status === 'scheduled' && <span className="pill info"><Clock size={12} /> {fmtDateTime(d.scheduled_at, lang)}</span>}
            </div>
          </div>
        </div>
        <div className="actions">
          {['pending_review', 'failed', 'rejected'].includes(d.status) && d.status !== 'rejected' && (
            <Button icon={Check} busy={busy === 'approve'} onClick={() => act('approve', () => api.post(`/api/drafts/${d.id}/approve`))}>
              {t('approve')}
            </Button>
          )}
          {['rejected', 'failed', 'approved'].includes(d.status) && (
            <Button icon={RotateCcw} busy={busy === 'restore'} onClick={() => act('restore', () => api.post(`/api/drafts/${d.id}/restore`))}>
              {t('restore')}
            </Button>
          )}
          {!locked && d.status !== 'rejected' && (
            <Button variant="danger" icon={X} onClick={() => setModal('reject')}>{t('reject')}</Button>
          )}
          {d.status === 'scheduled' && (
            <Button icon={XCircle} busy={busy === 'unsched'} onClick={() => act('unsched', () => api.post(`/api/drafts/${d.id}/unschedule`))}>
              {t('unschedule')}
            </Button>
          )}
          {!locked && d.status !== 'rejected' && (
            <Button variant="gold" icon={Send} disabled={!d.qa.passed || dirty} onClick={() => setModal('publish')}>
              {t('publish')}
            </Button>
          )}
        </div>
      </div>

      {d.error && <div className="banner danger"><AlertTriangle size={18} /> {d.error}</div>}
      {d.reject_reason && d.status === 'rejected' && <div className="banner warn">{d.reject_reason}</div>}
      {d.status === 'generating' && <div className="banner info"><Spinner size={16} /> {t('st_generating')}…</div>}

      <div className="editor">
        {/* ---------- slides ---------- */}
        <div className="stage">
          <div className="stage-main">
            {slide?.image_url ? <img src={mediaUrl(slide.image_url)} alt="" /> : <div className="center-page"><Images size={40} /></div>}
            {slides.length > 1 && (
              <>
                <button className="stage-nav prev" onClick={() => setActive((a) => Math.max(0, a - 1))} aria-label="prev">
                  {lang === 'ar' ? <ChevronRight size={20} /> : <ChevronLeft size={20} />}
                </button>
                <button className="stage-nav next" onClick={() => setActive((a) => Math.min(slides.length - 1, a + 1))} aria-label="next">
                  {lang === 'ar' ? <ChevronLeft size={20} /> : <ChevronRight size={20} />}
                </button>
              </>
            )}
            {(busy?.startsWith('slide') || busy === 'render' || busy === 'newbg') && (
              <div className="stage-busy"><Spinner size={30} /></div>
            )}
          </div>
          <div className="strip">
            {slides.map((s, i) => (
              <button key={s.id} className={i === active ? 'on' : ''} onClick={() => setActive(i)} aria-label={`slide ${i + 1}`}>
                {s.image_url && <img src={mediaUrl(s.image_url)} alt="" loading="lazy" />}
              </button>
            ))}
          </div>
          {slide && !locked && <SlideEditor key={slide.id + slide.heading + slide.body} draftId={d.id} slide={slide} busy={busy} act={act} />}
          <div className="row" style={{ marginTop: 12 }}>
            <Button size="sm" icon={Images} busy={busy === 'newbg'} disabled={locked}
              onClick={() => act('newbg', () => api.post(`/api/drafts/${d.id}/render`, { refresh_backgrounds: true }))}>
              {t('new_images')}
            </Button>
            <Button size="sm" icon={Wand2} busy={busy === 'render'} disabled={locked}
              onClick={() => act('render', () => api.post(`/api/drafts/${d.id}/render`, { refresh_backgrounds: false }))}>
              {t('rerender')}
            </Button>
            <Button size="sm" icon={Download} busy={busy === 'dl'}
              onClick={() => run('dl', () => api.download(`/api/drafts/${d.id}/download`, `post-${d.id}.zip`))}>
              {t('download')}
            </Button>
          </div>
        </div>

        {/* ---------- texts ---------- */}
        <div className="stack">
          <div className="card card-pad stack">
            {TEXT_FIELDS.map((k) => (
              <Field key={k} label={t(k)} action={REGEN_FIELDS.includes(k) && !locked && (
                <button type="button" className="btn btn-ghost btn-sm" onClick={(e) => { e.preventDefault(); regen(k); }}
                  disabled={busy === `regen-${k}` || dirty} title={t('regenerate')}>
                  {busy === `regen-${k}` ? <Spinner size={13} /> : <Sparkles size={14} />} {t('regenerate')}
                </button>
              )}>
                {k === 'caption' || k === 'first_comment' ? (
                  <textarea dir="auto" className="textarea" rows={k === 'caption' ? 8 : 3} value={form[k] || ''} disabled={locked}
                    onChange={(e) => set(k, e.target.value)} />
                ) : (
                  <input dir="auto" className="input" value={form[k] || ''} disabled={locked} onChange={(e) => set(k, e.target.value)} />
                )}
              </Field>
            ))}
            <div className="grid grid-2">
              <Field label={t('badge')}>
                <select className="select" value={form.badge || ''} disabled={locked} onChange={(e) => set('badge', e.target.value)}>
                  {BADGES.map((b) => <option key={b} value={b}>{b}</option>)}
                </select>
              </Field>
              <Field label={t('campaign')}>
                <select className="select" value={form.campaign_id || ''} onChange={(e) => set('campaign_id', e.target.value)}>
                  <option value="">{t('none')}</option>
                  {(campaigns.data || []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              </Field>
            </div>
            <div className="row">
              <Button variant="primary" icon={Save} busy={busy === 'save'} disabled={!dirty} onClick={save}>{t('save')}</Button>
              {dirty && <Button variant="ghost" onClick={() => { setDirty(false); draft.reload(true); }}>{t('cancel')}</Button>}
              <div className="spacer" />
              {!locked && (
                <Button size="sm" variant="ghost" icon={Sparkles} busy={busy === 'all'}
                  onClick={() => act('all', () => api.post(`/api/drafts/${d.id}/regenerate-all`).then(() => draft.reload(true)))}>
                  {t('regenerate_all')}
                </Button>
              )}
            </div>
          </div>

          {d.ai_meta && <AiMeta meta={d.ai_meta} />}

          <div className="card card-pad">
            <h3>
              {d.qa.passed ? <CheckCircle2 size={18} color="var(--ok)" /> : <AlertTriangle size={18} color="var(--danger)" />}
              {t('qa')} — {d.qa.passed ? t('qa_passed') : t('qa_failed')}
            </h3>
            {d.qa.items.map((i) => (
              <div className="qa-item" key={i.key}>
                {i.status === 'pass' ? <CheckCircle2 size={16} color="var(--ok)" />
                  : i.status === 'warn' ? <AlertTriangle size={16} color="var(--warn)" /> : <XCircle size={16} color="var(--danger)" />}
                <div><b className="small">{i.label}</b><div className="small muted">{i.message}</div></div>
              </div>
            ))}
          </div>

          <PlatformPosts draft={d} locked={locked} onChange={apply} />

          {(d.original_title || d.source_url) && (
            <div className="card card-pad">
              <div className="row" style={{ marginBottom: 10 }}>
                <h3 style={{ margin: 0 }}>{t('original')}</h3>
                <div className="spacer" />
                {d.source_url && (
                  <a className="btn btn-sm" href={d.source_url} target="_blank" rel="noreferrer">
                    <ExternalLink size={14} /> {t('open_original')}
                  </a>
                )}
              </div>
              <div className="bold small" style={{ marginBottom: 6 }} dir="auto">{d.original_title}</div>
              {d.original_body && <div className="source-box" dir="auto">{d.original_body}</div>}
            </div>
          )}

          {d.logs?.length > 0 && (
            <div className="card card-pad">
              <h3>{t('publish_log')}</h3>
              {d.logs.map((l) => (
                <div className="log" key={l.id}>
                  <StatusPill status={l.status === 'success' ? 'published' : 'failed'} label={l.status === 'success' ? t('success') : t('failed')} />
                  <b>{l.provider}</b> · {l.platform} · <span className="muted">{fmtDateTime(l.created_at, lang)}</span>
                  {l.error && <div className="xs" style={{ color: 'var(--danger)', width: '100%' }}>{l.error}</div>}
                  {l.external_id && <div className="xs muted code" style={{ width: '100%' }}>{l.external_id}</div>}
                </div>
              ))}
            </div>
          )}

          <div className="row">
            <div className="spacer" />
            <Button variant="danger" size="sm" icon={Trash2} disabled={d.status === 'publishing'}
              onClick={() => window.confirm(t('confirm_delete')) &&
                run('del', async () => { await api.del(`/api/drafts/${d.id}`); navigate('/'); })}>
              {t('delete')}
            </Button>
          </div>
        </div>
      </div>

      {modal === 'reject' && <RejectModal draft={d} onClose={() => setModal(null)} onDone={apply} />}
      {modal === 'publish' && <PublishModal draft={d} onClose={() => setModal(null)} onDone={apply} />}
    </>
  );
}

function SlideEditor({ draftId, slide, busy, act }) {
  const { t } = useI18n();
  const [heading, setHeading] = useState(slide.heading);
  const [body, setBody] = useState(slide.body);
  const fileRef = useRef(null);
  const changed = heading !== slide.heading || body !== slide.body;
  const base = `/api/drafts/${draftId}/slides/${slide.id}`;

  return (
    <div className="card card-pad stack" style={{ marginTop: 12 }}>
      <div className="row">
        <span className="pill gold">{slide.position + 1} · {slide.kind}</span>
        <div className="spacer" />
        <Button size="sm" variant="ghost" icon={Sparkles} busy={busy === 'slide-regen'}
          onClick={() => act('slide-regen', () => api.post(`${base}/regenerate`))}>{t('regenerate')}</Button>
        {slide.kind !== 'cta' && (
          <>
            <Button size="sm" variant="ghost" icon={ImagePlus} busy={busy === 'slide-bg'} onClick={() => fileRef.current?.click()}>
              {t('upload_bg')}
            </Button>
            <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp" hidden
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) act('slide-bg', () => api.upload(`${base}/background`, f));
                e.target.value = '';
              }} />
          </>
        )}
      </div>
      <Field label={t('slide_heading')}>
        <input dir="auto" className="input" value={heading} onChange={(e) => setHeading(e.target.value)} />
      </Field>
      {slide.kind !== 'cta' && (
        <Field label={t('slide_body')}>
          <textarea dir="auto" className="textarea" rows={3} value={body} onChange={(e) => setBody(e.target.value)} />
        </Field>
      )}
      {changed && (
        <div className="row">
          <Button size="sm" variant="primary" icon={Check} busy={busy === 'slide-save'}
            onClick={() => act('slide-save', () => api.patch(base, { heading, body }))}>{t('apply')}</Button>
          <Button size="sm" variant="ghost" onClick={() => { setHeading(slide.heading); setBody(slide.body); }}>{t('cancel')}</Button>
        </div>
      )}
    </div>
  );
}

function RejectModal({ draft, onClose, onDone }) {
  const { t } = useI18n();
  const [reason, setReason] = useState('');
  const [busy, run] = useAction();
  return (
    <Modal title={t('reject')} onClose={onClose} footer={<>
      <Button onClick={onClose}>{t('cancel')}</Button>
      <Button variant="danger" icon={X} busy={busy === 'r'} onClick={() => run('r', async () => {
        onDone(await api.post(`/api/drafts/${draft.id}/reject`, { reason }));
        onClose();
      })}>{t('reject')}</Button>
    </>}>
      <Field label={t('reject_reason')}>
        <textarea className="textarea" value={reason} onChange={(e) => setReason(e.target.value)} autoFocus />
      </Field>
    </Modal>
  );
}

const PLATFORM_ORDER = ['instagram', 'facebook', 'linkedin', 'x', 'threads', 'tiktok'];

/** One post per platform: its own text and its own images (carousel or a single image). */
function PlatformPosts({ draft, locked, onChange }) {
  const { t } = useI18n();
  const variants = draft.variants || {};
  const names = PLATFORM_ORDER.filter((p) => variants[p]);
  const [tab, setTab] = useState(names[0] || 'instagram');
  const [text, setText] = useState('');
  const [edited, setEdited] = useState(false);
  const [busy, run] = useAction();
  const v = variants[tab];

  useEffect(() => { setText(v?.text || ''); setEdited(false); }, [tab, v?.text]);
  if (!names.length) return null;

  const slides = draft.slides || [];
  const picked = v.slides || [];
  const rules = v.images || { best: [1, 10], max: 10 };
  const over = text.length > v.limit;
  const save = () => run('save-v', async () => {
    onChange(await api.patch(`/api/drafts/${draft.id}/variants/${tab}`, { text }));
  }, t('saved'));
  const toggleImage = (pos) => {
    const next = picked.includes(pos) ? picked.filter((p) => p !== pos) : [...picked, pos];
    if (!next.length || next.length > rules.max) return;
    run('img-v', async () => {
      onChange(await api.patch(`/api/drafts/${draft.id}/variants/${tab}`, { slides: next }));
    });
  };
  const regenerate = () => run('regen-v', async () => {
    onChange(await api.post(`/api/drafts/${draft.id}/variants/regenerate`));
  }, t('done'));
  const inBest = picked.length >= rules.best[0] && picked.length <= rules.best[1];

  return (
    <div className="card card-pad stack">
      <div className="row">
        <h3 style={{ margin: 0 }}><Send size={16} /> {t('platform_posts')}</h3>
        <div className="spacer" />
        <Button size="sm" icon={Wand2} busy={busy === 'regen-v'} disabled={locked} onClick={regenerate}>{t('regen_platforms')}</Button>
      </div>
      <p className="xs muted" style={{ margin: 0 }}>
        {draft.variants_generated ? t('platform_posts_hint') : t('platform_posts_derived')}
      </p>
      <div className="tabs" style={{ flexWrap: 'wrap' }}>
        {names.map((p) => (
          <button key={p} className={`tab ${tab === p ? 'active' : ''}`} onClick={() => setTab(p)}>
            {variants[p].label}
            <span className="n">{(variants[p].slides || []).length} 🖼</span>
          </button>
        ))}
      </div>
      <div className="row xs" style={{ gap: 8 }}>
        <span className={`pill ${inBest ? 'ok' : 'warn'}`}>
          {picked.length} {t('images_selected')} · {t('best_for_platform')} {rules.best[0] === rules.best[1] ? rules.best[0] : `${rules.best[0]}–${rules.best[1]}`}
        </span>
        <span className="muted">{t('tap_to_select_images')}</span>
      </div>
      <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
        {slides.map((s) => {
          const on = picked.includes(s.position);
          const order = picked.indexOf(s.position) + 1;
          return s.image_url ? (
            <button key={s.id} type="button" disabled={locked || busy === 'img-v'}
              title={on ? t('remove_image') : t('add_image')} onClick={() => toggleImage(s.position)}
              style={{ position: 'relative', padding: 0, border: on ? '3px solid var(--gold)' : '3px solid transparent',
                borderRadius: 10, opacity: on ? 1 : 0.4, cursor: 'pointer', background: 'none' }}>
              <img src={mediaUrl(s.image_url)} alt="" style={{ width: 64, height: 80, objectFit: 'cover', borderRadius: 7, display: 'block' }} />
              {on && <span style={{ position: 'absolute', top: 3, insetInlineStart: 3, background: 'var(--gold)', color: 'var(--navy)',
                fontSize: 11, fontWeight: 800, borderRadius: 6, padding: '0 5px' }}>{order}</span>}
            </button>
          ) : null;
        })}
      </div>
      <textarea className="textarea" dir="auto" rows={v.limit <= 500 ? 4 : 9} value={text} disabled={locked}
        onChange={(e) => { setText(e.target.value); setEdited(true); }} />
      <div className="row">
        <span className="xs" style={{ color: over ? 'var(--danger)' : 'var(--muted)' }}>{text.length} / {v.limit}</span>
        <div className="spacer" />
        <Button size="sm" variant="primary" icon={Save} busy={busy === 'save-v'} disabled={!edited || over || locked} onClick={save}>
          {t('save')}
        </Button>
      </div>
    </div>
  );
}

function PublishModal({ draft, onClose, onDone }) {
  const { t } = useI18n();
  const status = useLoad(() => api.get('/api/status'), []);
  const settings = useLoad(() => api.get('/api/settings'), []);
  const [targets, setTargets] = useState({});
  const [mode, setMode] = useState('now');
  const [when, setWhen] = useState(() => toLocalInput(new Date(Date.now() + 3600000)));
  const [busy, run] = useAction();

  useEffect(() => {
    const pub = settings.data?.values.publishing;
    if (pub && Object.keys(targets).length === 0) {
      setTargets({ [pub.default_provider]: pub.default_platforms });
    }
  }, [settings.data]); // eslint-disable-line react-hooks/exhaustive-deps

  const toggle = (provider, platform) => setTargets((cur) => {
    const list = cur[provider] || [];
    return { ...cur, [provider]: list.includes(platform) ? list.filter((p) => p !== platform) : [...list, platform] };
  });
  const chosen = Object.entries(targets)
    .filter(([name, p]) => p.length && status.data?.providers[name]?.configured)
    .map(([provider, platforms]) => ({ provider, platforms }));

  const submit = () => run('pub', async () => {
    const body = { targets: chosen };
    if (mode === 'later') body.scheduled_at = new Date(when).toISOString();
    onDone(await api.post(`/api/drafts/${draft.id}/publish`, body));
    onClose();
  }, mode === 'later' ? t('saved') : t('started'));

  const providers = status.data?.providers || {};
  return (
    <Modal title={t('publish_title')} onClose={onClose} footer={<>
      <Button onClick={onClose}>{t('cancel')}</Button>
      <Button variant="gold" icon={mode === 'later' ? Clock : Send} busy={busy === 'pub'} disabled={!chosen.length} onClick={submit}>
        {mode === 'later' ? t('schedule') : t('publish_now')}
      </Button>
    </>}>
      {!status.data ? <Spinner /> : (
        <div className="stack">
          {!status.data.storage.public && <div className="banner danger"><AlertTriangle size={16} /> {t('public_missing')}</div>}
          <div className="bold small">{t('providers')}</div>
          <div className="target-grid">
            {Object.entries(providers).map(([name, info]) => (
              <div key={name} className={`target ${info.configured && (targets[name] || []).length ? 'on' : ''}`}>
                <div className="row" style={{ marginBottom: 8 }}>
                  <b className="ltr">{{ buffer: 'Buffer', meta: 'Meta (Facebook / Instagram)', uploadpost: 'upload-post.com' }[name]}</b>
                  <span className={`pill ${info.configured ? 'ok' : ''}`}>{info.configured ? t('configured') : t('not_configured')}</span>
                  <div className="spacer" />
                  {info.configured && (
                    <button type="button" className="btn btn-sm btn-ghost"
                      onClick={() => setTargets((cur) => ({ ...cur, [name]: (cur[name] || []).length === info.platforms.length ? [] : [...info.platforms] }))}>
                      {t('all_platforms')}
                    </button>
                  )}
                </div>
                <div className="row">
                  {info.platforms.map((p) => (
                    <label key={p} className="check small">
                      <input type="checkbox" disabled={!info.configured} checked={info.configured && (targets[name] || []).includes(p)}
                        onChange={() => toggle(name, p)} /> {p}
                    </label>
                  ))}
                </div>
              </div>
            ))}
          </div>
          {!chosen.length && <div className="small muted">{t('pick_platform')}</div>}
          {chosen.length > 0 && (
            <div className="stack" style={{ gap: 4 }}>
              <div className="bold small">{t('will_publish')}</div>
              {[...new Set(chosen.flatMap((c) => c.platforms))].map((p) => {
                const v = draft.variants?.[p];
                return (
                  <div key={p} className="xs row" style={{ gap: 6 }}>
                    <b style={{ minWidth: 80 }}>{v?.label || p}</b>
                    <span className="muted">{(v?.slides || []).length} 🖼</span>
                    <span className="muted clamp-2" dir="auto" style={{ flex: 1 }}>{(v?.text || '').slice(0, 90)}</span>
                  </div>
                );
              })}
            </div>
          )}
          <div className="tabs" style={{ alignSelf: 'flex-start' }}>
            <button className={`tab ${mode === 'now' ? 'active' : ''}`} onClick={() => setMode('now')}>{t('publish_now')}</button>
            <button className={`tab ${mode === 'later' ? 'active' : ''}`} onClick={() => setMode('later')}>{t('publish_later')}</button>
          </div>
          {mode === 'later' && (
            <Button size="sm" icon={Clock} busy={busy === 'slot'} disabled={!chosen.length}
              onClick={() => run('slot', async () => {
                onDone(await api.post(`/api/drafts/${draft.id}/schedule`, { targets: chosen }));
                onClose();
              }, t('saved'))}>
              {t('next_free_slot')}
            </Button>
          )}
          {mode === 'later' && (
            <Field label={t('when')}>
              <input className="input ltr" type="datetime-local" value={when} min={toLocalInput(new Date())}
                onChange={(e) => setWhen(e.target.value)} />
            </Field>
          )}
        </div>
      )}
    </Modal>
  );
}

/** Which engine wrote the post — and, in parallel mode, why it won. */
function AiMeta({ meta }) {
  const { t } = useI18n();
  if (meta.mode === 'demo') {
    return <div className="banner warn small" style={{ margin: 0 }}><Bot size={16} /> {t('demo_text')}</div>;
  }
  if (meta.mode !== 'ensemble') {
    return (
      <div className="small muted row" style={{ gap: 6 }}>
        <Bot size={14} /> {t('written_by')}: <b>{meta.engine_label}</b>
      </div>
    );
  }
  const scores = Object.entries(meta.scores || {});
  const errors = Object.entries(meta.errors || {});
  return (
    <div className="card card-pad stack" style={{ gap: 8 }}>
      <h3 style={{ margin: 0 }}><Bot size={16} /> {t('ensemble_winner')}: {meta.engine_label}</h3>
      {scores.length > 0 && (
        <div className="row">
          {scores.map(([name, score]) => (
            <span key={name} className={`pill ${name === meta.engine_label ? 'ok' : ''}`}>{name} {score ?? '—'}/10</span>
          ))}
        </div>
      )}
      {meta.reason && (
        <div className="small">
          {meta.method === 'judge' ? <>{t('judged_by')} <b>{meta.judge}</b>: </> : null}
          {meta.method === 'rules' ? t('by_rules') : meta.reason}
        </div>
      )}
      {errors.length > 0 && (
        <div className="xs" style={{ color: 'var(--warn)' }}>
          {t('engine_errors')}: {errors.map(([n, e]) => `${n} — ${e}`).join(' · ')}
        </div>
      )}
    </div>
  );
}
