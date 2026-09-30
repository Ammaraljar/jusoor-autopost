import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, Inbox, X } from 'lucide-react';
import { useI18n } from '../lib/i18n';

/* ---------- toasts ---------- */
const ToastContext = createContext(() => {});

export function ToastProvider({ children }) {
  const [items, setItems] = useState([]);
  const push = useCallback((message, type = 'info') => {
    const id = Math.random().toString(36).slice(2);
    setItems((xs) => [...xs, { id, message, type }]);
    setTimeout(() => setItems((xs) => xs.filter((x) => x.id !== id)), 4200);
  }, []);
  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {items.map((x) => (
          <div key={x.id} className={`toast ${x.type}`}>
            {x.type === 'error' ? <AlertTriangle size={16} /> : <CheckCircle2 size={16} />}
            {x.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export const useToast = () => useContext(ToastContext);

/* ---------- data loading ---------- */
export function useLoad(loader, deps = []) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const reload = useCallback(async (silent = false) => {
    if (!silent) setState((s) => ({ ...s, loading: true }));
    try {
      const data = await loader();
      setState({ data, error: null, loading: false });
      return data;
    } catch (error) {
      setState((s) => ({ ...s, error, loading: false }));
      return null;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(() => { reload(); }, [reload]);
  return { ...state, reload, setData: (data) => setState((s) => ({ ...s, data })) };
}

/** Wraps an async action with busy state + error toast. */
export function useAction() {
  const toast = useToast();
  const { t } = useI18n();
  const [busy, setBusy] = useState(null);
  const run = useCallback(async (key, fn, successMsg) => {
    setBusy(key);
    try {
      const res = await fn();
      if (successMsg) toast(successMsg, 'success');
      return res;
    } catch (err) {
      toast(err.message || t('error'), 'error');
      return undefined;
    } finally {
      setBusy(null);
    }
  }, [toast, t]);
  return [busy, run];
}

/* ---------- primitives ---------- */
export const Spinner = ({ size = 18 }) => <span className="spinner" style={{ width: size, height: size }} />;

export function Button({ busy, icon: Icon, children, variant = '', size = '', ...props }) {
  return (
    <button className={`btn ${variant ? `btn-${variant}` : ''} ${size ? `btn-${size}` : ''}`} disabled={busy || props.disabled} {...props}>
      {busy ? <Spinner size={15} /> : Icon ? <Icon size={size === 'sm' ? 14 : 16} /> : null}
      {children}
    </button>
  );
}

export function Field({ label, hint, children, action }) {
  return (
    <label className="field">
      {(label || action) && (
        <span className="field-head" style={{ display: 'flex' }}>
          <span>{label}</span>
          {action}
        </span>
      )}
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}

export function Modal({ title, children, footer, onClose, wide }) {
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose?.();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);
  return (
    <div className="modal-back" onMouseDown={(e) => e.target === e.currentTarget && onClose?.()}>
      <div className={`modal ${wide ? 'wide' : ''}`} role="dialog" aria-modal="true" aria-label={title}>
        <div className="modal-head">
          <h2>{title}</h2>
          <button className="btn btn-ghost icon-btn" onClick={onClose} aria-label="close"><X size={18} /></button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-foot">{footer}</div>}
      </div>
    </div>
  );
}

export function Empty({ icon: Icon = Inbox, children }) {
  return (
    <div className="empty">
      <Icon size={40} />
      <div>{children}</div>
    </div>
  );
}

const STATUS_TONE = {
  generating: 'info', pending_review: 'gold', approved: 'ok', scheduled: 'info', publishing: 'info',
  published: 'ok', failed: 'danger', rejected: '', healthy: 'ok', failing: 'danger', unknown: '',
  planned: '', generated: 'gold',
};

export function StatusPill({ status, label }) {
  const { t } = useI18n();
  const text = label || t(`st_${status}`) || status;
  return (
    <span className={`pill ${STATUS_TONE[status] ?? ''}`}>
      {(status === 'generating' || status === 'publishing') ? <Spinner size={10} /> : <span className="dot" />}
      {text}
    </span>
  );
}

export function Loading() {
  const { t } = useI18n();
  return <div className="center-page"><div className="row"><Spinner /> {t('loading')}</div></div>;
}

export function ErrorBox({ error, onRetry }) {
  return (
    <div className="banner danger">
      <AlertTriangle size={18} /> {error?.message || String(error)}
      {onRetry && <button className="btn btn-sm" onClick={() => onRetry()} style={{ marginInlineStart: 'auto' }}>↻</button>}
    </div>
  );
}

export function PageHead({ title, sub, children }) {
  return (
    <div className="page-head">
      <div>
        <h1>{title}</h1>
        {sub && <p>{sub}</p>}
      </div>
      <div className="actions">{children}</div>
    </div>
  );
}

/* ----------------------------------------------------------------- multi-select */
export function useSelection(items) {
  const [selected, setSelected] = useState(() => new Set());
  const ids = (items || []).map((x) => x.id);
  // Forget ids that are no longer in the list (deleted, filtered out)
  useEffect(() => {
    setSelected((s) => {
      const keep = new Set([...s].filter((id) => ids.includes(id)));
      return keep.size === s.size ? s : keep;
    });
  }, [ids.join(',')]); // eslint-disable-line react-hooks/exhaustive-deps
  const toggle = (id) => setSelected((s) => {
    const n = new Set(s);
    if (n.has(id)) n.delete(id); else n.add(id);
    return n;
  });
  const allOn = ids.length > 0 && ids.every((id) => selected.has(id));
  const toggleAll = () => setSelected(allOn ? new Set() : new Set(ids));
  const clear = () => setSelected(new Set());
  return { selected, ids: [...selected], count: selected.size, has: (id) => selected.has(id), toggle, toggleAll, allOn, clear };
}

export function SelectAll({ sel, label }) {
  return (
    <label className="check small" style={{ whiteSpace: 'nowrap' }}>
      <input type="checkbox" checked={sel.allOn} onChange={sel.toggleAll} /> {label}
    </label>
  );
}

/** Sticky bar shown while items are selected. actions: [{key, label, icon, variant, confirm}] */
export function BulkBar({ sel, actions, onAction, busy, selectedLabel, clearLabel }) {
  if (!sel.count) return null;
  return (
    <div className="bulk-bar">
      <b>{sel.count}</b> <span>{selectedLabel}</span>
      <div className="spacer" />
      {actions.map((a) => (
        <Button key={a.key} size="sm" variant={a.variant || ''} icon={a.icon} busy={busy === `bulk-${a.key}`}
          onClick={() => { if (!a.confirm || window.confirm(a.confirm)) onAction(a.key); }}>
          {a.label}
        </Button>
      ))}
      <Button size="sm" variant="ghost" onClick={sel.clear}>{clearLabel}</Button>
    </div>
  );
}
