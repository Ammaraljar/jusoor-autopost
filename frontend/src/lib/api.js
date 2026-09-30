import { supabase } from './supabase';

const BASE = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '');
const TOKEN_KEY = 'autopost-token';

let internalToken = (() => {
  try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
})();

/** Store (or clear) the session token issued by our own backend. */
export function setInternalToken(token) {
  internalToken = token || null;
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch { /* ignore */ }
}

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function authHeader() {
  if (!supabase) return internalToken ? { Authorization: `Bearer ${internalToken}` } : {};
  const { data } = await supabase.auth.getSession();
  const token = data?.session?.access_token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request(method, path, body, { raw = false } = {}) {
  const headers = { ...(await authHeader()) };
  const init = { method, headers };
  if (body instanceof FormData) {
    init.body = body;
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(`${BASE}${path}`, init);
  } catch (err) {
    throw new ApiError('تعذّر الاتصال بالخادم', 0);
  }
  if (!res.ok) {
    let message = `HTTP ${res.status}`;
    try {
      const data = await res.json();
      message = typeof data.detail === 'string' ? data.detail
        : Array.isArray(data.detail) ? data.detail.map((d) => d.msg).join('، ') : message;
    } catch { /* not json */ }
    if (res.status === 401 && !path.startsWith('/api/auth/')) {
      // A session that the server rejected: end it and keep the reason for the login screen
      // instead of looping silently. A plain "not signed in" answer is not an error worth showing.
      const hadSession = Boolean(internalToken || supabase);
      if (hadSession) {
        try { sessionStorage.setItem('auth-error', message); } catch { /* ignore */ }
      }
      if (supabase) await supabase.auth.signOut();
      else if (internalToken) { setInternalToken(null); window.location.reload(); }
    }
    throw new ApiError(message, res.status);
  }
  if (raw) return res;
  return res.status === 204 ? null : res.json();
}

export const api = {
  get: (p) => request('GET', p),
  post: (p, b = {}) => request('POST', p, b),
  patch: (p, b) => request('PATCH', p, b),
  put: (p, b) => request('PUT', p, b),
  del: (p) => request('DELETE', p),
  upload: (p, file, extra = {}) => {
    const fd = new FormData();
    fd.append('file', file);
    Object.entries(extra).forEach(([k, v]) => fd.append(k, v));
    return request('POST', p, fd);
  },
  async download(p, filename) {
    const res = await request('GET', p, undefined, { raw: true });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  },
};

/** Media URLs from local storage are relative to the backend. */
export function mediaUrl(url) {
  if (!url) return null;
  if (/^https?:\/\//.test(url) && BASE === '') {
    try {
      const u = new URL(url);
      if (u.pathname.startsWith('/media/')) return u.pathname; // served via the Vite proxy in dev
    } catch { /* ignore */ }
  }
  return url;
}
