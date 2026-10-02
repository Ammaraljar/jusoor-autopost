import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CheckSquare, ChevronLeft, ChevronRight, Clock, ExternalLink, Plus, Sparkles, Trash2 } from 'lucide-react';
import { BulkBar, Button, ErrorBox, Field, Modal, PageHead, StatusPill, useAction, useLoad, useSelection } from '../components/ui';
import { api, mediaUrl } from '../lib/api';
import { isoDay } from '../lib/format';
import { useI18n } from '../lib/i18n';

const CONTENT_TYPES = ['travel', 'tips', 'news', 'educational', 'promotional', 'storytelling', 'announcement', 'event', 'comparison', 'product'];
const PLATFORMS = ['instagram', 'facebook', 'linkedin', 'tiktok'];

function monthGrid(anchor, lang) {
  // Week starts on Saturday for Arabic, Monday otherwise.
  const weekStart = lang === 'ar' ? 6 : 1;
  const first = new Date(anchor.getFullYear(), anchor.getMonth(), 1);
  const offset = (first.getDay() - weekStart + 7) % 7;
  const start = new Date(first);
  start.setDate(first.getDate() - offset);
  return Array.from({ length: 42 }, (_, i) => {
    const d = new Date(start);
    d.setDate(start.getDate() + i);
    return d;
  });
}

export default function CalendarPage() {
  const { t, lang } = useI18n();
  const navigate = useNavigate();
  const [anchor, setAnchor] = useState(() => { const d = new Date(); d.setDate(1); return d; });
  const days = useMemo(() => monthGrid(anchor, lang), [anchor, lang]);
  const range = `start=${isoDay(days[0])}&end=${isoDay(days[41])}`;
  const cal = useLoad(() => api.get(`/api/calendar?${range}`), [range]);
  const campaigns = useLoad(() => api.get('/api/campaigns'), []);
  const [editing, setEditing] = useState(null);
  const [selectMode, setSelectMode] = useState(false);
  const [dropDay, setDropDay] = useState(null);
  const [movingPost, setMovingPost] = useState(null);
  const sel = useSelection(cal.data?.items);
  const [busy, run] = useAction();
  const moveToDay = (postId, day) => run(`move-${postId}`, async () => {
    await api.post(`/api/drafts/${postId}/schedule`, { date: day });
    cal.reload(true);
  }, t('saved'));
  const plan = cal.data?.plan;
  const bulkDelete = () => run('bulk-delete', async () => {
    await api.post('/api/calendar/bulk-delete', { ids: sel.ids });
    sel.clear();
    cal.reload(true);
  }, t('done'));

  const byDay = useMemo(() => {
    const map = {};
    (cal.data?.items || []).forEach((i) => { (map[i.date] ||= { items: [], posts: [] }).items.push(i); });
    (cal.data?.posts || []).forEach((p) => {
      const key = isoDay(new Date(p.at));
      (map[key] ||= { items: [], posts: [] }).posts.push(p);
    });
    return map;
  }, [cal.data]);

  const locale = lang === 'ar' ? 'ar-u-nu-latn' : lang;
  const title = new Intl.DateTimeFormat(locale, { month: 'long', year: 'numeric' }).format(anchor);
  const dow = days.slice(0, 7).map((d) => new Intl.DateTimeFormat(locale, { weekday: 'short' }).format(d));
  const today = isoDay(new Date());
  const shift = (n) => setAnchor((a) => new Date(a.getFullYear(), a.getMonth() + n, 1));
  const Prev = lang === 'ar' ? ChevronRight : ChevronLeft;
  const Next = lang === 'ar' ? ChevronLeft : ChevronRight;
  const campaignColor = (id) => campaigns.data?.find((c) => c.id === id)?.color;

  return (
    <>
      <PageHead title={t('calendar_title')} sub={t('calendar_sub')}>
        <Button icon={CheckSquare} variant={selectMode ? 'primary' : ''}
          onClick={() => { setSelectMode((m) => !m); sel.clear(); }}>{t('select')}</Button>
        <Button variant="primary" icon={Plus} onClick={() => setEditing({ date: today, time: '10:00' })}>{t('add_item')}</Button>
      </PageHead>
      {plan && (
        <div className="small muted" style={{ marginBottom: 8 }}>
          {t('plan_summary')}: <b>{plan.posts_per_day}</b> {t('per_day')} · {plan.day_start}–{plan.day_end} · {t('gap')} {plan.min_gap_hours}h
          {plan.today_slots?.length ? ` · ${plan.today_slots.join(' · ')}` : ''} — {t('drag_hint')}
        </div>
      )}
      {selectMode && !sel.count && <div className="banner info small">{t('calendar_select_hint')}</div>}
      <BulkBar sel={sel} busy={busy} onAction={bulkDelete} selectedLabel={t('selected')} clearLabel={t('clear_selection')}
        actions={[{ key: 'delete', label: t('delete_forever'), icon: Trash2, variant: 'danger', confirm: t('confirm_bulk_delete') }]} />
      {cal.error && <ErrorBox error={cal.error} onRetry={cal.reload} />}
      <div className="row" style={{ marginBottom: 12 }}>
        <button className="btn icon-btn" onClick={() => shift(-1)} aria-label="prev"><Prev size={18} /></button>
        <h2 style={{ fontSize: 20, minWidth: 170, textAlign: 'center' }}>{title}</h2>
        <button className="btn icon-btn" onClick={() => shift(1)} aria-label="next"><Next size={18} /></button>
        <Button size="sm" variant="ghost" onClick={() => { const d = new Date(); d.setDate(1); setAnchor(d); }}>{t('today')}</Button>
        <div className="spacer" />
        <span className="chip">{t('planned')}</span>
        <span className="chip scheduled">{t('scheduled')}</span>
        <span className="chip post">{t('published')}</span>
      </div>
      <div className="cal">
        {dow.map((d) => <div key={d} className="cal-dow">{d}</div>)}
        {days.map((d) => {
          const key = isoDay(d);
          const entry = byDay[key] || { items: [], posts: [] };
          const out = d.getMonth() !== anchor.getMonth();
          return (
            <div key={key} className={`cal-day ${out ? 'out' : ''} ${key === today ? 'today' : ''} ${dropDay === key ? 'drop' : ''}`}
              onClick={() => { if (!selectMode) setEditing({ date: key, time: '10:00' }); }}
              onDragOver={(e) => { if (key >= today) { e.preventDefault(); setDropDay(key); } }}
              onDragLeave={() => setDropDay((cur) => (cur === key ? null : cur))}
              onDrop={(e) => {
                e.preventDefault(); setDropDay(null);
                const id = Number(e.dataTransfer.getData('text/post'));
                if (id) moveToDay(id, key);
              }}>
              <span className="num">{d.getDate()}</span>
              {plan && entry.posts.filter((p) => p.status !== 'failed').length > 0 && (
                <span className={`count-badge ${entry.posts.length >= plan.posts_per_day ? 'full' : ''}`}>
                  {entry.posts.filter((p) => p.status !== 'failed').length}/{plan.posts_per_day}
                </span>
              )}
              {entry.items.map((i) => (
                <div key={`i${i.id}`} className="chip" title={i.topic} dir="auto"
                  style={{ ...(campaignColor(i.campaign_id) ? { borderInlineStartColor: campaignColor(i.campaign_id) } : {}),
                    ...(sel.has(i.id) ? { outline: '2px solid var(--gold)', background: 'var(--gold-tint)' } : {}) }}
                  onClick={(e) => { e.stopPropagation(); if (selectMode) sel.toggle(i.id); else setEditing(i); }}>
                  {selectMode && <input type="checkbox" readOnly checked={sel.has(i.id)} style={{ marginInlineEnd: 4, pointerEvents: 'none' }} />}
                  {i.time} {i.topic}
                </div>
              ))}
              {entry.posts.map((p) => (
                <div key={`p${p.id}`} className={`chip ${p.status === 'published' ? 'post' : p.status === 'failed' ? 'failed' : 'scheduled'}`}
                  title={p.hook} dir="auto" draggable={p.status === 'scheduled'}
                  onDragStart={(e) => { e.dataTransfer.setData('text/post', String(p.id)); e.stopPropagation(); }}
                  onClick={(e) => { e.stopPropagation(); if (p.status === 'scheduled') setMovingPost(p); else navigate(`/drafts/${p.id}`); }}>
                  {new Date(p.at).toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' })} {p.hook}
                </div>
              ))}
            </div>
          );
        })}
      </div>
      {movingPost && (
        <MovePostModal post={movingPost} onClose={() => setMovingPost(null)}
          onChanged={() => { setMovingPost(null); cal.reload(true); }} />
      )}
      {editing && (
        <ItemModal item={editing} campaigns={campaigns.data || []} onClose={() => setEditing(null)}
          onChanged={() => { setEditing(null); cal.reload(true); }} />
      )}
    </>
  );
}

function MovePostModal({ post, onClose, onChanged }) {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [busy, run] = useAction();
  const local = new Date(post.at);
  const pad = (n) => String(n).padStart(2, '0');
  const [when, setWhen] = useState(
    `${local.getFullYear()}-${pad(local.getMonth() + 1)}-${pad(local.getDate())}T${pad(local.getHours())}:${pad(local.getMinutes())}`);
  const move = (body) => run('move', async () => {
    await api.post(`/api/drafts/${post.id}/schedule`, body);
    onChanged();
  }, t('saved'));
  return (
    <Modal title={t('move_post')} onClose={onClose} footer={<>
      <Button onClick={() => navigate(`/drafts/${post.id}`)} icon={ExternalLink}>{t('open_post')}</Button>
      <Button variant="danger" busy={busy === 'un'} onClick={() => run('un', async () => {
        await api.post(`/api/drafts/${post.id}/unschedule`); onChanged();
      }, t('saved'))}>{t('unschedule')}</Button>
      <div className="spacer" />
      <Button onClick={onClose}>{t('cancel')}</Button>
      <Button variant="primary" busy={busy === 'move'} onClick={() => move({ scheduled_at: new Date(when).toISOString() })}>{t('save')}</Button>
    </>}>
      <div className="stack">
        <div className="bold small" dir="auto">{post.hook}</div>
        {post.cover_url && <img src={mediaUrl(post.cover_url)} alt="" style={{ width: 120, borderRadius: 10 }} />}
        <Field label={t('when')}>
          <input className="input ltr" type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} />
        </Field>
        <Button size="sm" icon={Clock} busy={busy === 'move'} onClick={() => move({})}>{t('next_free_slot')}</Button>
      </div>
    </Modal>
  );
}

function ItemModal({ item, campaigns, onClose, onChanged }) {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [f, setF] = useState({ topic: '', notes: '', content_type: 'travel', platform: 'instagram', campaign_id: '', ...item });
  const [busy, run] = useAction();
  const set = (k, v) => setF((x) => ({ ...x, [k]: v }));
  const payload = () => ({
    date: f.date, time: f.time, topic: f.topic, notes: f.notes, content_type: f.content_type, platform: f.platform,
    campaign_id: f.campaign_id ? Number(f.campaign_id) : null, brand_id: f.brand_id || null,
  });

  const save = () => run('save', async () => {
    if (item.id) await api.patch(`/api/calendar/${item.id}`, payload());
    else await api.post('/api/calendar', payload());
    onChanged();
  }, t('saved'));

  return (
    <Modal title={item.id ? t('edit') : t('add_item')} onClose={onClose} footer={<>
      {item.id && (
        <Button variant="danger" icon={Trash2} busy={busy === 'del'} onClick={() => window.confirm(t('confirm_delete')) &&
          run('del', async () => { await api.del(`/api/calendar/${item.id}`); onChanged(); })}>{t('delete')}</Button>
      )}
      <div className="spacer" />
      {item.id && item.draft_id && (
        <Button icon={ExternalLink} onClick={() => navigate(`/drafts/${item.draft_id}`)}>{t('open_draft')}</Button>
      )}
      {item.id && !item.draft_id && (
        <Button variant="gold" icon={Sparkles} busy={busy === 'gen'}
          onClick={() => run('gen', async () => { await api.post(`/api/calendar/${item.id}/generate`); onChanged(); }, t('started'))}>
          {t('generate')}
        </Button>
      )}
      <Button variant="primary" busy={busy === 'save'} disabled={f.topic.trim().length < 3} onClick={save}>{t('save')}</Button>
    </>}>
      <div className="stack">
        {item.id && <div><StatusPill status={item.status} label={t(item.status)} /></div>}
        <Field label={t('topic')}>
          <input className="input" value={f.topic} onChange={(e) => set('topic', e.target.value)} autoFocus
            placeholder="دليل التسوق في كوالالمبور خلال موسم التخفيضات" />
        </Field>
        <Field label={t('notes')}>
          <textarea className="textarea" rows={3} value={f.notes} onChange={(e) => set('notes', e.target.value)} />
        </Field>
        <div className="grid grid-2">
          <Field label={t('date')}><input className="input" type="date" value={f.date} onChange={(e) => set('date', e.target.value)} /></Field>
          <Field label={t('time')}><input className="input" type="time" value={f.time} onChange={(e) => set('time', e.target.value)} /></Field>
          <Field label={t('content_type')}>
            <select className="select" value={f.content_type} onChange={(e) => set('content_type', e.target.value)}>
              {CONTENT_TYPES.map((c) => <option key={c}>{c}</option>)}
            </select>
          </Field>
          <Field label={t('platform')}>
            <select className="select" value={f.platform} onChange={(e) => set('platform', e.target.value)}>
              {PLATFORMS.map((c) => <option key={c}>{c}</option>)}
            </select>
          </Field>
        </div>
        <Field label={t('campaign')}>
          <select className="select" value={f.campaign_id || ''} onChange={(e) => set('campaign_id', e.target.value)}>
            <option value="">{t('none')}</option>
            {campaigns.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </Field>
      </div>
    </Modal>
  );
}
