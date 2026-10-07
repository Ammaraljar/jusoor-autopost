import { useEffect, useRef, useState } from 'react';
import { Eye, ImagePlus, Plus, RefreshCw, Save, Star, Trash2 } from 'lucide-react';
import { Button, ErrorBox, Field, Loading, PageHead, Spinner, useAction, useLoad } from '../components/ui';
import { api, mediaUrl } from '../lib/api';
import { useAuth } from '../lib/auth';
import { useI18n } from '../lib/i18n';

const COLOR_KEYS = ['navy', 'gold', 'goldLight', 'cardTitle', 'cardText'];

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
            <Field label={t('cta_text')}><input className="input" value={f.cta_text} onChange={(e) => set('cta_text', e.target.value)} /></Field>
          </div>
          <Field label={t('voice')}>
            <textarea className="textarea" rows={3} value={f.voice} onChange={(e) => set('voice', e.target.value)} />
          </Field>
        </div>

        <div className="card card-pad stack">
          <h3>{t('colors')}</h3>
          {(f.color_mode || 'auto') === 'auto' && <p className="xs muted" style={{ marginTop: -8 }}>{t('colors_auto_hint')}</p>}
          <div className="swatches">
            {COLOR_KEYS.map((k) => (
              <Field key={k} label={t(`c_${k}`)}>
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
          <Field label={t('logo')}>
            <div className="row">
              <div className="logo-box">{brand.logo_url ? <img src={mediaUrl(brand.logo_url)} alt="" /> : <span className="xs muted">—</span>}</div>
              <div className="stack" style={{ gap: 6 }}>
                <Button size="sm" icon={ImagePlus} busy={busy === 'logo'} onClick={() => fileRef.current?.click()}>{t('upload_logo')}</Button>
                {brand.logo_url && (
                  <Button size="sm" variant="danger" icon={Trash2} busy={busy === 'rmlogo'}
                    onClick={() => run('rmlogo', async () => { await api.del(`/api/brands/${brand.id}/logo`); onChanged(); refreshPreview(); })}>
                    {t('remove_logo')}
                  </Button>
                )}
              </div>
              <input ref={fileRef} type="file" accept="image/png,image/svg+xml" hidden onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) run('logo', async () => { await api.upload(`/api/brands/${brand.id}/logo`, file); onChanged(); refreshPreview(); }, t('saved'));
                e.target.value = '';
              }} />
            </div>
          </Field>
        </div>

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
