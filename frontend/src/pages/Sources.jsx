import { useState } from 'react';
import { Download, FlaskConical, ImageOff, List, Pause, Pencil, Play, Plus, RefreshCw, Rss, Sparkles, Trash2 } from 'lucide-react';
import { BulkBar, Button, Empty, ErrorBox, Field, Loading, Modal, PageHead, SelectAll, StatusPill, useAction, useLoad, useSelection } from '../components/ui';
import { api } from '../lib/api';
import ScrapeModal from '../components/ScrapeModal';
import { fmtDateTime, relative } from '../lib/format';
import { useI18n } from '../lib/i18n';

const EMPTY = {
  name: '', kind: 'website', base_url: '', feed_url: '', listing_urls: [], link_pattern: '', link_selector: '',
  body_selector: '', purpose: 'news', dialect: '', category: 'general', country: '', language: 'en', priority: 5, enabled: true,
  check_interval_minutes: 120, max_items_per_run: 5, brand_id: null,
};

export default function Sources() {
  const { t, lang } = useI18n();
  const sources = useLoad(() => api.get('/api/sources'), []);
  const presets = useLoad(() => api.get('/api/sources/presets'), []);
  const [editing, setEditing] = useState(null);
  const [articlesFor, setArticlesFor] = useState(null);
  const [testResult, setTestResult] = useState(null);
  const [scrapeFor, setScrapeFor] = useState(null);
  const [busy, run] = useAction();
  const sel = useSelection(sources.data);

  if (sources.loading && !sources.data) return <Loading />;
  const bulk = (action) => run(`bulk-${action}`, async () => {
    await api.post('/api/sources/bulk', { ids: sel.ids, action });
    if (action === 'delete') sel.clear();
    sources.reload(true);
  }, action === 'scrape' ? t('started') : t('done'));
  const bulkActions = [
    { key: 'scrape', label: t('scrape_now'), icon: RefreshCw },
    { key: 'enable', label: t('enable_sel'), icon: Play },
    { key: 'disable', label: t('disable_sel'), icon: Pause },
    { key: 'delete', label: t('delete_forever'), icon: Trash2, variant: 'danger', confirm: t('confirm_delete_sources') },
  ];
  const existing = new Set((sources.data || []).map((s) => s.name));
  const missingPresets = (presets.data || []).filter((p) => !existing.has(p.name));

  const test = (s) => run(`test-${s.id}`, async () => setTestResult({ name: s.name, ...(await api.post(`/api/sources/${s.id}/test`)) }));
  const scrape = (s) => run(`scrape-${s.id}`, () => api.post(`/api/sources/${s.id}/scrape`), t('started'));
  const toggle = (s) => run(`tog-${s.id}`, async () => { await api.patch(`/api/sources/${s.id}`, { enabled: !s.enabled }); sources.reload(true); });
  const remove = (s) => window.confirm(t('confirm_delete_sources')) &&
    run(`del-${s.id}`, async () => { await api.del(`/api/sources/${s.id}`); sources.reload(true); });

  return (
    <>
      <PageHead title={t('sources_title')} sub={t('sources_sub')}>
        <Button variant="primary" icon={Plus} onClick={() => setEditing({ ...EMPTY })}>{t('add_source')}</Button>
      </PageHead>
      {sources.error && <ErrorBox error={sources.error} onRetry={sources.reload} />}

      {missingPresets.length > 0 && (
        <div className="card card-pad" style={{ marginBottom: 16 }}>
          <h3><Sparkles size={16} /> {t('presets')}</h3>
          <div className="row">
            {missingPresets.map((p) => (
              <Button key={p.name} size="sm" icon={Plus} busy={busy === `preset-${p.name}`}
                onClick={() => run(`preset-${p.name}`, async () => { await api.post('/api/sources', p); sources.reload(true); })}>
                {p.name}
              </Button>
            ))}
          </div>
        </div>
      )}

      <BulkBar sel={sel} actions={bulkActions} onAction={bulk} busy={busy}
        selectedLabel={t('selected')} clearLabel={t('clear_selection')} />

      {sources.data?.length === 0 ? <div className="card"><Empty icon={Rss}>{t('add_source')}</Empty></div> : (
        <div className="card table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th style={{ width: 36 }}><input type="checkbox" checked={sel.allOn} onChange={sel.toggleAll} title={t('select_all')} /></th>
                <th>{t('name')}</th><th>{t('kind')}</th><th>{t('health')}</th><th>{t('last_check')}</th>
                <th>{t('articles')}</th><th>{t('enabled')}</th><th />
              </tr>
            </thead>
            <tbody>
              {sources.data?.map((s) => (
                <tr key={s.id} style={{ opacity: s.enabled ? 1 : 0.55, background: sel.has(s.id) ? 'var(--gold-tint)' : undefined }}>
                  <td><input type="checkbox" checked={sel.has(s.id)} onChange={() => sel.toggle(s.id)} /></td>
                  <td>
                    <div className="bold">{s.name}</div>
                    <div className="xs muted code">{(s.kind === 'rss' ? s.feed_url : (s.listing_urls?.[0] || s.base_url))}</div>
                  </td>
                  <td>
                    <span className="pill">{s.kind === 'rss' ? 'RSS' : t('website')}</span>{' '}
                    {s.purpose === 'programs' && <span className="pill gold">{t('purpose_programs')}</span>}
                    {s.dialect && <span className="pill info">{t(`dialect_${s.dialect}`)}</span>}
                  </td>
                  <td>
                    <StatusPill status={s.health} label={t(`health_${s.health}`)} />
                    {s.last_error && <div className="xs clamp-2" style={{ color: 'var(--danger)', maxWidth: 220 }}>{s.last_error}</div>}
                  </td>
                  <td className="small" title={fmtDateTime(s.last_checked_at, lang)}>
                    {s.last_checked_at ? relative(s.last_checked_at, lang) : '—'}
                    {s.last_http_status && <div className="xs muted">HTTP {s.last_http_status}</div>}
                  </td>
                  <td className="small">
                    {s.stats.articles} {t('articles')} · {s.stats.drafts} {t('drafts')} · {s.stats.published} {t('published')}
                  </td>
                  <td>
                    <label className="check"><input type="checkbox" checked={s.enabled} onChange={() => toggle(s)} /></label>
                  </td>
                  <td>
                    <div className="row" style={{ flexWrap: 'nowrap', justifyContent: 'flex-end' }}>
                      <Button size="sm" icon={FlaskConical} busy={busy === `test-${s.id}`} onClick={() => test(s)}>{t('test')}</Button>
                      <Button size="sm" icon={RefreshCw} onClick={() => setScrapeFor(s)}>{t('scrape_now')}</Button>
                      <button className="btn btn-sm btn-ghost icon-btn" title={t('view_articles')} onClick={() => setArticlesFor(s)}><List size={15} /></button>
                      <button className="btn btn-sm btn-ghost icon-btn" title={t('edit')} onClick={() => setEditing({ ...EMPTY, ...s })}><Pencil size={15} /></button>
                      <button className="btn btn-sm btn-danger btn-ghost icon-btn" title={t('delete')} onClick={() => remove(s)}><Trash2 size={15} /></button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {editing && <SourceModal initial={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); sources.reload(true); }} />}
      {scrapeFor && <ScrapeModal source={scrapeFor} onClose={() => setScrapeFor(null)} onStarted={() => sources.reload(true)} />}
      {testResult && <TestModal result={testResult} onClose={() => setTestResult(null)} />}
      {articlesFor && <ArticlesModal source={articlesFor} onClose={() => setArticlesFor(null)} />}
    </>
  );
}

function SourceModal({ initial, onClose, onSaved }) {
  const { t } = useI18n();
  const [f, setF] = useState({ ...initial, listing_text: (initial.listing_urls || []).join('\n') });
  const [result, setResult] = useState(null);
  const [busy, run] = useAction();
  const brands = useLoad(() => api.get('/api/brands'), []);
  const set = (k, v) => setF((x) => ({ ...x, [k]: v }));

  const payload = () => {
    const out = {};
    Object.keys(EMPTY).forEach((k) => { out[k] = f[k]; });
    out.listing_urls = f.listing_text.split('\n').map((x) => x.trim()).filter(Boolean);
    ['feed_url', 'link_pattern', 'link_selector', 'body_selector', 'dialect'].forEach((k) => { out[k] = out[k] || null; });
    out.priority = Number(out.priority);
    out.check_interval_minutes = Number(out.check_interval_minutes);
    out.max_items_per_run = Number(out.max_items_per_run);
    out.brand_id = out.brand_id ? Number(out.brand_id) : null;
    if (!out.base_url && out.listing_urls[0]) {
      try { out.base_url = new URL(out.listing_urls[0]).origin; } catch { /* ignore */ }
    }
    return out;
  };

  const save = () => run('save', async () => {
    if (initial.id) await api.patch(`/api/sources/${initial.id}`, payload());
    else await api.post('/api/sources', payload());
    onSaved();
  }, t('saved'));

  return (
    <Modal wide title={initial.id ? t('edit') : t('add_source')} onClose={onClose} footer={<>
      <Button icon={FlaskConical} busy={busy === 'test'} onClick={() => run('test', async () => setResult(await api.post('/api/sources/test', payload())))}>
        {t('test')}
      </Button>
      {initial.id && (
        <Button variant="danger" icon={Trash2} busy={busy === 'delete'}
          onClick={() => window.confirm(t('confirm_delete_sources')) && run('delete', async () => {
            await api.del(`/api/sources/${initial.id}`);
            onSaved();
          }, t('done'))}>
          {t('delete_source')}
        </Button>
      )}
      <div className="spacer" />
      <Button onClick={onClose}>{t('cancel')}</Button>
      <Button variant="primary" busy={busy === 'save'} disabled={!f.name} onClick={save}>{t('save')}</Button>
    </>}>
      <div className="stack">
        <div className="grid grid-2">
          <Field label={t('name')}><input className="input" value={f.name} onChange={(e) => set('name', e.target.value)} /></Field>
          <Field label={t('kind')}>
            <select className="select" value={f.kind} onChange={(e) => set('kind', e.target.value)}>
              <option value="website">{t('website')}</option>
              <option value="rss">RSS</option>
            </select>
          </Field>
        </div>
        {f.kind === 'rss' ? (
          <Field label={t('feed_url')}><input className="input ltr" value={f.feed_url || ''} onChange={(e) => set('feed_url', e.target.value)} placeholder="https://example.com/feed" /></Field>
        ) : (
          <>
            <Field label={t('listing_urls')}>
              <textarea className="textarea ltr" rows={2} value={f.listing_text} onChange={(e) => set('listing_text', e.target.value)}
                placeholder="https://www.thestar.com.my/lifestyle/travel" />
            </Field>
            <div className="grid grid-2">
              <Field label={t('link_pattern')} hint="/lifestyle/travel/\d{4}/">
                <input className="input code" value={f.link_pattern || ''} onChange={(e) => set('link_pattern', e.target.value)} />
              </Field>
              <Field label={t('link_selector')} hint="article h2 a">
                <input className="input code" value={f.link_selector || ''} onChange={(e) => set('link_selector', e.target.value)} />
              </Field>
            </div>
          </>
        )}
        <Field label={t('body_selector')} hint="div.story-body">
          <input className="input code" value={f.body_selector || ''} onChange={(e) => set('body_selector', e.target.value)} />
        </Field>
        <div className="grid grid-2">
          <Field label={t('source_purpose')} hint={f.purpose === 'programs' ? t('programs_hint') : ''}>
            <select className="select" value={f.purpose || 'news'} onChange={(e) => set('purpose', e.target.value)}>
              <option value="news">{t('purpose_news')}</option>
              <option value="programs">{t('purpose_programs')}</option>
            </select>
          </Field>
          <Field label={t('dialect')}>
            <select className="select" value={f.dialect || ''} onChange={(e) => set('dialect', e.target.value)}>
              <option value="">{t('dialect_default')}</option>
              {['msa', 'gulf', 'maghreb', 'algeria'].map((x) => <option key={x} value={x}>{t(`dialect_${x}`)}</option>)}
            </select>
          </Field>
        </div>
        <div className="grid grid-3">
          <Field label={t('category')}><input className="input" value={f.category} onChange={(e) => set('category', e.target.value)} /></Field>
          <Field label={t('country')}><input className="input" value={f.country} onChange={(e) => set('country', e.target.value)} /></Field>
          <Field label={t('src_language')}>
            <select className="select" value={f.language} onChange={(e) => set('language', e.target.value)}>
              {['en', 'ar', 'ms', 'fr', 'id'].map((l) => <option key={l}>{l}</option>)}
            </select>
          </Field>
          <Field label={t('interval')}><input className="input" type="number" min={15} value={f.check_interval_minutes} onChange={(e) => set('check_interval_minutes', e.target.value)} /></Field>
          <Field label={t('max_items')}><input className="input" type="number" min={1} max={30} value={f.max_items_per_run} onChange={(e) => set('max_items_per_run', e.target.value)} /></Field>
          <Field label={t('priority')}><input className="input" type="number" min={1} max={10} value={f.priority} onChange={(e) => set('priority', e.target.value)} /></Field>
        </div>
        {brands.data?.length > 1 && (
          <Field label={t('brand')}>
            <select className="select" value={f.brand_id || ''} onChange={(e) => set('brand_id', e.target.value)}>
              <option value="">{t('default')}</option>
              {brands.data.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
            </select>
          </Field>
        )}
        {result && <TestResult result={result} />}
      </div>
    </Modal>
  );
}

function TestResult({ result }) {
  const { t } = useI18n();
  return (
    <div className="result-box stack">
      <div className="row">
        <b>{t('test_result')}</b>
        <span className={`pill ${result.ok ? 'ok' : 'danger'}`}>{result.ok ? 'OK' : '✕'}</span>
        {result.http_status && <span className="pill">HTTP {result.http_status}</span>}
        {result.count != null && <span className="pill">{result.count} {t('found_links')}</span>}
      </div>
      {result.error && <div style={{ color: 'var(--danger)' }}>{result.error}</div>}
      {(result.samples || []).map((s) => (
        <div key={s.url} className="small">
          <div className="bold" dir="auto">{s.title || '—'}</div>
          <div className="xs muted code">{s.url}</div>
          {s.chars != null && <div className="xs muted">{s.chars} chars · {s.image ? '🖼' : 'no image'} · {s.published_at || ''}</div>}
        </div>
      ))}
      {result.links && result.links.length > 0 && (
        <details>
          <summary className="small">{t('found_links')} ({result.links.length})</summary>
          {result.links.map((l) => <div key={l} className="xs code">{l}</div>)}
        </details>
      )}
    </div>
  );
}

function TestModal({ result, onClose }) {
  return <Modal title={result.name} onClose={onClose}><TestResult result={result} /></Modal>;
}

function ArticlesModal({ source, onClose }) {
  const { t, lang } = useI18n();
  const articles = useLoad(() => api.get(`/api/sources/${source.id}/articles`), [source.id]);
  const [busy, run] = useAction();
  const sel = useSelection(articles.data);
  const tone = { new: 'info', drafted: 'ok', skipped: '', error: 'danger' };
  const bulk = (action) => run(`bulk-${action}`, async () => {
    await api.post('/api/sources/articles/bulk', { ids: sel.ids, action });
    sel.clear();
    articles.reload(true);
  }, action === 'draft' ? t('started') : t('done'));
  return (
    <Modal wide title={`${t('view_articles')} — ${source.name}`} onClose={onClose}>
      {articles.loading ? <Loading /> : articles.data?.length === 0 ? <Empty>—</Empty> : (
        <div className="stack">
          <SelectAll sel={sel} label={t('select_all')} />
          <BulkBar sel={sel} busy={busy} onAction={bulk} selectedLabel={t('selected')} clearLabel={t('clear_selection')}
            actions={[
              { key: 'draft', label: t('make_drafts'), icon: Sparkles },
              { key: 'delete', label: t('delete_forever'), icon: Trash2, variant: 'danger', confirm: t('confirm_bulk_delete') },
            ]} />
          {articles.data?.map((a) => (
            <div key={a.id} className="row" style={{ borderBottom: '1px dashed var(--border)', paddingBottom: 8, flexWrap: 'nowrap',
              background: sel.has(a.id) ? 'var(--gold-tint)' : undefined, borderRadius: 8 }}>
              <input type="checkbox" checked={sel.has(a.id)} onChange={() => sel.toggle(a.id)} />
              {a.image_url
                ? <img className="art-thumb" src={a.image_url} alt="" loading="lazy" referrerPolicy="no-referrer" />
                : <span className="art-thumb" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }} title={t('no_image')}><ImageOff size={20} className="muted" /></span>}
              <div style={{ flex: 1, minWidth: 0 }}>
                <a className="bold small" href={a.url} target="_blank" rel="noreferrer" dir="auto">{a.title}</a>
                <div className="xs muted">{fmtDateTime(a.published_at || a.fetched_at, lang)} {a.note ? `· ${a.note}` : ''}</div>
              </div>
              <span className={`pill ${tone[a.status] || ''}`}>{a.status}</span>
              {a.status === 'skipped' && (
                <Button size="sm" icon={Download} busy={busy === a.id}
                  onClick={() => run(a.id, async () => { await api.post(`/api/sources/articles/${a.id}/draft`); articles.reload(true); }, t('started'))}>
                  {t('make_draft')}
                </Button>
              )}
            </div>
          ))}
        </div>
      )}
    </Modal>
  );
}
