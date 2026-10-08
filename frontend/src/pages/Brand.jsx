import { useEffect, useRef, useState } from 'react';
import { CheckSquare, Eye, ImagePlus, LayoutTemplate, Plus, RefreshCw, RotateCcw, Save, Square, Star, Trash2 } from 'lucide-react';
import { Button, ErrorBox, Field, Loading, PageHead, Spinner, useAction, useLoad } from '../components/ui';
import { api, mediaUrl } from '../lib/api';
import { useAuth } from '../lib/auth';
import { useExample } from '../lib/useExample';
import { useI18n } from '../lib/i18n';

const COLOR_KEYS = ['navy', 'gold', 'goldLight', 'surface', 'cardTitle', 'cardText'];

const PREVIEWS = [
  { key: 'v0', kind: 'cover', variant: 0 }, { key: 'v1', kind: 'content', variant: 1 },
  { key: 'v2', kind: 'cover', variant: 2 }, { key: 'v3', kind: 'content', variant: 3 },
  { key: 'v4', kind: 'cover', variant: 4 }, { key: 'v5', kind: 'content', variant: 5 },
  { key: 'cta', kind: 'cta', variant: 0 }, { key: 'cta2', kind: 'cta', variant: 3 },
];

export default function Brand() {
  const { t } = useI18n();
  const brands = useLoad(() => api.get('/api/brands'), []);
  const [selected, setSelected] = useState(null);
  const [busy, run] = useAction();

  useEffect(() => {
    if (brands.data && !brands.data.find((b) => b.id === selected)) setSelected(brands.data[0]?.id);
  }, [brands.data]); // eslint-disable-line react-hooks/exhaustive-deps

  if (brands.loading && !brands.data) return <Loading />;
  const brand = brands.data?.find((b) => b.id === selected);

  const addBrand = () => {
    const name = window.prompt(t('name'));
    if (name) run('add', async () => { const b = await api.post('/api/brands', { name }); await brands.reload(true); setSelected(b.id); });
  };

  return (
    <>
      <PageHead title={t('brand_title')} sub={t('brand_sub')}>
        <Button icon={Plus} busy={busy === 'add'} onClick={addBrand}>{t('add_brand')}</Button>
      </PageHead>
      {brands.error && <ErrorBox error={brands.error} onRetry={brands.reload} />}
      {brands.data?.length > 1 && (
        <div className="tabs" style={{ marginBottom: 16, display: 'inline-flex' }}>
          {brands.data.map((b) => (
            <button key={b.id} className={`tab ${b.id === selected ? 'active' : ''}`} onClick={() => setSelected(b.id)}>
              {b.is_default && <Star size={13} />} {b.name}
            </button>
          ))}
        </div>
      )}
      {brand && <BrandForm key={brand.id} brand={brand} onChanged={() => brands.reload(true)} />}
    </>
  );
}

function BrandForm({ brand, onChanged }) {
  const ex = useExample();
  const { user } = useAuth();
  const { t } = useI18n();
  const [f, setF] = useState(() => ({ ...brand, colors: { ...brand.colors }, publish_config: structuredClone(brand.publish_config || {}) }));
  const [previews, setPreviews] = useState({});
  const [channels, setChannels] = useState(null);
  const [busy, run] = useAction();
  const fileRef = useRef(null);
  const set = (k, v) => setF((x) => ({ ...x, [k]: v }));
  const setColor = (k, v) => setF((x) => ({ ...x, colors: { ...x.colors, [k]: v } }));
  const setPub = (section, k, v) => setF((x) => ({
    ...x, publish_config: { ...x.publish_config, [section]: { ...(x.publish_config[section] || {}), [k]: v } },
  }));
  const bufferIds = f.publish_config.buffer_channel_ids || [];

  const refreshPreview = () => run('preview', async () => {
    // Six JUSOOR colour sets / card shapes + the last (call-to-action) slide, rendered in parallel
    const language = user?.org?.language || 'ar';
    const jobs = PREVIEWS.map((p) => api.post(`/api/brands/${brand.id}/preview`, { ...p, language }).then((r) => [p.key, r.image]));
    setPreviews(Object.fromEntries(await Promise.all(jobs)));
  });
  useEffect(() => { refreshPreview(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const save = () => run('save', async () => {
    await api.patch(`/api/brands/${brand.id}`, {
      name: f.name, handle: f.handle, website: f.website, voice: f.voice, cta_text: f.cta_text,
      colors: f.colors, logo_placement: f.logo_placement, card_style: f.card_style, card_theme: f.card_theme || 'magazine', publish_config: f.publish_config,
      color_mode: f.color_mode || 'auto', logo_backdrop: f.logo_backdrop || 'auto',
      font_family: f.font_family || 'Cairo', font_latin: f.font_latin || 'Cairo', templates: f.templates || [],
    });
    onChanged();
    refreshPreview();
  }, t('saved'));

  const loadChannels = () => run('channels', async () => {
    const st = await api.get('/api/providers/buffer/status');
    if (!st.configured) throw new Error(`Buffer: ${t('not_configured')}`);
    if (st.error) throw new Error(st.error);
    setChannels(st.channels || []);
  });

  return (
    <div className="editor">
      <div className="stack">
        <div className="card card-pad stack">
          <div className="grid grid-2">
            <Field label={t('name')}><input className="input" value={f.name} onChange={(e) => set('name', e.target.value)} /></Field>
            <Field label={t('handle')}><input className="input ltr" value={f.handle} onChange={(e) => set('handle', e.target.value)} /></Field>
            <Field label={t('website')}><input className="input ltr" value={f.website} onChange={(e) => set('website', e.target.value)} /></Field>
            <Field label={t('cta_text')}><input className="input" value={f.cta_text} placeholder={ex('cta')} onChange={(e) => set('cta_text', e.target.value)} /></Field>
          </div>
          <Field label={t('voice')}>
            <textarea className="textarea" rows={3} value={f.voice} placeholder={ex('voice')} onChange={(e) => set('voice', e.target.value)} />
          </Field>
        </div>

        <div className="card card-pad stack">
          <div className="field-head">
            <h3 style={{ margin: 0 }}>{t('colors')}</h3>
            {brand.has_default_colors && (
              <Button size="sm" icon={RotateCcw} busy={busy === 'reset'} title={t('reset_colors_hint')}
                onClick={() => window.confirm(t('reset_colors_confirm')) && run('reset', async () => {
                  const b = await api.post(`/api/brands/${brand.id}/colors/reset`);
                  setF((x) => ({ ...x, colors: { ...b.colors }, color_mode: b.color_mode }));
                  onChanged(); refreshPreview();
                }, t('saved'))}>{t('reset_colors')}</Button>
            )}
          </div>
          {(f.color_mode || 'auto') === 'auto' && <p className="xs muted" style={{ marginTop: -8 }}>{t('colors_auto_hint')}</p>}
          <div className="swatches">
            {COLOR_KEYS.map((k) => (
              <Field key={k} label={t(`c_${k}`)} hint={t(`ch_${k}`)}>
                <input className="input" type="color" value={f.colors[k] || '#000000'} onChange={(e) => setColor(k, e.target.value)} />
              </Field>
            ))}
          </div>
          <div className="grid grid-2">
            <Field label={t('color_mode')}>
              <select className="select" value={f.color_mode || 'auto'} onChange={(e) => set('color_mode', e.target.value)}>
                <option value="auto">{t('color_auto')}</option>
                <option value="brand">{t('color_brand')}</option>
              </select>
            </Field>
            <Field label={t('logo_backdrop')}>
              <select className="select" value={f.logo_backdrop || 'auto'} onChange={(e) => set('logo_backdrop', e.target.value)}>
                <option value="auto">{t('backdrop_auto')}</option>
                <option value="always">{t('backdrop_always')}</option>
                <option value="never">{t('backdrop_never')}</option>
              </select>
            </Field>
          </div>
          <div className="grid grid-2">
            <Field label={t('logo_placement')}>
              <select className="select" value={f.logo_placement} onChange={(e) => set('logo_placement', e.target.value)}>
                <option value="top-left">{t('top_left')}</option>
                <option value="top-right">{t('top_right')}</option>
              </select>
            </Field>
            <Field label={t('card_theme')}>
              <select className="select" value={f.card_theme || 'magazine'} onChange={(e) => set('card_theme', e.target.value)}>
                <option value="magazine">{t('theme_magazine')}</option>
                <option value="classic">{t('theme_classic')}</option>
              </select>
            </Field>
            {f.card_theme === 'classic' && (
            <Field label={t('card_style')}>
              <select className="select" value={f.card_style} onChange={(e) => set('card_style', e.target.value)}>
                {['frosted', 'solid', 'band', 'side', 'ribbon', 'outline', 'minimal'].map((s) => <option key={s} value={s}>{t(`card_${s}`)}</option>)}
              </select>
            </Field>
            )}
          </div>
          <Field label={t('logos')} hint={t('logos_hint')}>
            <div className="stack" style={{ gap: 10 }}>
              <div className="logo-grid">
                {(brand.logos || []).map((l) => (
                  <div key={l.key} className={`logo-tile ${l.primary ? 'on' : ''}`}>
                    <div className={`logo-box tone-${l.tone}`}><img src={mediaUrl(l.url)} alt="" /></div>
                    <select className="select" style={{ height: 32, fontSize: 13 }} value={l.tone}
                      onChange={(e) => run(`tone-${l.key}`, async () => { await api.patch(`/api/brands/${brand.id}/logos`, { key: l.key, tone: e.target.value }); onChanged(); refreshPreview(); })}>
                      {['color', 'light', 'dark'].map((x) => <option key={x} value={x}>{t(`logo_${x}`)}</option>)}
                    </select>
                    <div className="row" style={{ gap: 6 }}>
                      {l.primary ? <span className="pill gold"><Star size={12} /> {t('primary_logo')}</span> : (
                        <Button size="sm" icon={Star} busy={busy === `pr-${l.key}`}
                          onClick={() => run(`pr-${l.key}`, async () => { await api.patch(`/api/brands/${brand.id}/logos`, { key: l.key, primary: true }); onChanged(); refreshPreview(); }, t('saved'))}>
                          {t('make_primary')}
                        </Button>
                      )}
                      <Button size="sm" variant="danger" icon={Trash2} busy={busy === `rm-${l.key}`} title={t('delete')}
                        onClick={() => window.confirm(t('confirm_delete')) && run(`rm-${l.key}`, async () => { await api.del(`/api/brands/${brand.id}/logos?key=${encodeURIComponent(l.key)}`); onChanged(); refreshPreview(); })} />
                    </div>
                  </div>
                ))}
                {!(brand.logos || []).length && <div className="logo-box"><span className="xs muted">—</span></div>}
              </div>
              <div>
                <Button size="sm" icon={ImagePlus} busy={busy === 'logo'} onClick={() => fileRef.current?.click()}>{t('upload_logos')}</Button>
              </div>
              <input ref={fileRef} type="file" accept="image/png,image/svg+xml,image/webp" multiple hidden onChange={(e) => {
                const files = e.target.files;
                if (files?.length) run('logo', async () => { await api.uploadMany(`/api/brands/${brand.id}/logos`, files); onChanged(); refreshPreview(); }, t('saved'));
                e.target.value = '';
              }} />
            </div>
          </Field>
        </div>

        <div className="card card-pad stack">
          <h3>{t('fonts')}</h3>
          <div className="grid grid-2">
            <Field label={t('font_arabic')}>
              <select className="select" value={f.font_family || 'Cairo'} onChange={(e) => set('font_family', e.target.value)}>
                {(brand.font_options?.arabic || ['Cairo']).map((x) => <option key={x} value={x}>{x}</option>)}
              </select>
              <div className="font-sample" dir="rtl" style={{ fontFamily: `'${f.font_family || 'Cairo'}', Cairo` }}>عنوان منشورك بهذا الخط</div>
            </Field>
            <Field label={t('font_latin')}>
              <select className="select" value={f.font_latin || 'Cairo'} onChange={(e) => set('font_latin', e.target.value)}>
                {(brand.font_options?.latin || ['Cairo']).map((x) => <option key={x} value={x}>{x}</option>)}
              </select>
              <div className="font-sample" dir="ltr" style={{ fontFamily: `'${f.font_latin || 'Cairo'}', Cairo` }}>Your headline in this font</div>
            </Field>
          </div>
        </div>

        <TemplatePicker brand={brand} value={f.templates || []} onChange={(v) => set('templates', v)} />

        <div className="card card-pad stack">
          <h3>{t('publishing_channels')}</h3>
          <div className="field-head">
            <b className="small">{t('buffer_channels')}</b>
            <Button size="sm" icon={RefreshCw} busy={busy === 'channels'} onClick={loadChannels}>{t('load_channels')}</Button>
          </div>
          {channels && channels.map((c) => (
            <label key={c.id} className="check small">
              <input type="checkbox" checked={bufferIds.includes(c.id)} onChange={() => setF((x) => ({
                ...x, publish_config: { ...x.publish_config,
                  buffer_channel_ids: bufferIds.includes(c.id) ? bufferIds.filter((i) => i !== c.id) : [...bufferIds, c.id] },
              }))} />
              {c.name} <span className="pill">{c.service}</span>
              {c.isDisconnected && <span className="pill danger">{t('disconnected')}</span>}
            </label>
          ))}
          {!channels && bufferIds.length > 0 && <div className="xs muted code">{bufferIds.join(', ')}</div>}
          <div className="divider" />
          <b className="small">Meta Graph API</b>
          <div className="grid grid-2">
            <Field label={t('meta_page')}><input className="input code" value={f.publish_config.meta?.page_id || ''} onChange={(e) => setPub('meta', 'page_id', e.target.value.trim())} /></Field>
            <Field label={t('meta_ig')}><input className="input code" value={f.publish_config.meta?.ig_user_id || ''} onChange={(e) => setPub('meta', 'ig_user_id', e.target.value.trim())} /></Field>
          </div>
          <div className="divider" />
          <b className="small">upload-post.com</b>
          <div className="grid grid-2">
            <Field label={t('up_user')}><input className="input code" value={f.publish_config.uploadpost?.user || ''} onChange={(e) => setPub('uploadpost', 'user', e.target.value.trim())} /></Field>
            <Field label={t('up_fb')}><input className="input code" value={f.publish_config.uploadpost?.facebook_page_id || ''} onChange={(e) => setPub('uploadpost', 'facebook_page_id', e.target.value.trim())} /></Field>
          </div>
        </div>

        <div className="row">
          <Button variant="primary" icon={Save} busy={busy === 'save'} onClick={save}>{t('save')}</Button>
          {!brand.is_default && (
            <>
              <Button icon={Star} busy={busy === 'def'} onClick={() => run('def', async () => { await api.post(`/api/brands/${brand.id}/default`); onChanged(); })}>
                {t('make_default')}
              </Button>
              <div className="spacer" />
              <Button variant="danger" icon={Trash2} onClick={() => window.confirm(t('confirm_delete')) &&
                run('del', async () => { await api.del(`/api/brands/${brand.id}`); onChanged(); })}>{t('delete')}</Button>
            </>
          )}
        </div>
      </div>

      <div className="stage">
        <div className="card card-pad">
          <div className="field-head" style={{ marginBottom: 12 }}>
            <h3 style={{ margin: 0 }}><Eye size={16} /> {t('preview')}</h3>
            <Button size="sm" icon={RefreshCw} busy={busy === 'preview'} onClick={refreshPreview}>{t('refresh_preview')}</Button>
          </div>
          <div className="preview-grid">
            {PREVIEWS.filter((p) => p.kind !== 'cta').map((p) => (
              <div className="ph" key={p.key}>{previews[p.key] ? <img src={previews[p.key]} alt={p.key} /> : <Spinner />}</div>
            ))}
          </div>
          <div className="xs muted" style={{ margin: '10px 0 6px' }}>{t('cta_preview')}</div>
          <div className="preview-grid">
            <div className="ph">{previews.cta ? <img src={previews.cta} alt="cta" /> : <Spinner />}</div>
            <div className="ph">{previews.cta2 ? <img src={previews.cta2} alt="cta" /> : <Spinner />}</div>
          </div>
          <p className="xs muted" style={{ marginTop: 8 }}>{t('preview_hint')} · {t('save')} → {t('refresh_preview')}</p>
        </div>
      </div>
    </div>
  );
}


/** The card templates of the company's field: keep all, or only the ones the company likes. */
function TemplatePicker({ brand, value, onChange }) {
  const { t, lang } = useI18n();
  const { user } = useAuth();
  const list = useLoad(() => api.get(`/api/brands/${brand.id}/templates`), [brand.id]);
  const [thumbs, setThumbs] = useState({});
  const [busy, setBusy] = useState(false);
  const items = list.data || [];
  const kept = value.length ? value : items.map((i) => i.id);
  const toggle = (id) => {
    const next = kept.includes(id) ? kept.filter((x) => x !== id) : [...kept, id];
    if (!next.length) return;
    onChange(next.length === items.length ? [] : next);
  };
  const loadThumbs = async () => {
    setBusy(true);
    const language = user?.org?.language || 'ar';
    const queue = [...items];
    const worker = async () => {
      while (queue.length) {
        const it = queue.shift();
        try {
          const r = await api.post(`/api/brands/${brand.id}/preview`, { kind: 'cover', variant: 0, template: it.id, language });
          setThumbs((x) => ({ ...x, [it.id]: r.image }));
        } catch { /* skip */ }
      }
    };
    await Promise.all([worker(), worker(), worker()]);
    setBusy(false);
  };
  return (
    <div className="card card-pad stack">
      <div className="field-head">
        <h3 style={{ margin: 0 }}><LayoutTemplate size={16} /> {t('templates_title')}</h3>
        <Button size="sm" icon={Eye} busy={busy} disabled={!items.length} onClick={loadThumbs}>{t('templates_preview')}</Button>
      </div>
      <p className="xs muted" style={{ marginTop: -8 }}>{t('templates_hint')} — {kept.length}/{items.length}</p>
      <div className="row" style={{ gap: 8 }}>
        <Button size="sm" icon={CheckSquare} onClick={() => onChange([])}>{t('select_all')}</Button>
      </div>
      <div className="tpl-grid">
        {items.map((it) => {
          const on = kept.includes(it.id);
          return (
            <button type="button" key={it.id} className={`tpl-item ${on ? 'on' : ''}`} onClick={() => toggle(it.id)}>
              <div className="tpl-thumb">{thumbs[it.id] ? <img src={thumbs[it.id]} alt="" /> : <LayoutTemplate size={22} />}</div>
              <span>{on ? <CheckSquare size={14} /> : <Square size={14} />} {it[lang] || it.en}</span>
            </button>
          );
        })}
      </div>
      <p className="xs muted">{t('templates_save_hint')}</p>
    </div>
  );
}
