import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { api, setActingOrg, setInternalToken } from './api';
import { supabase } from './supabase';

const AuthContext = createContext(null);
const TOKEN_KEY = 'autopost-token';

function readStored() {
  try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
}

/**
 * Two login modes:
 *  - internal  : e-mail + password checked by our own backend (no Supabase at all)
 *  - supabase  : Supabase Auth, used when the site is built with VITE_SUPABASE_URL
 */
export function AuthProvider({ children }) {
  const [session, setSession] = useState(undefined);
  const [mode, setMode] = useState(supabase ? 'supabase' : 'internal');
  const [allowSignup, setAllowSignup] = useState(false);

  useEffect(() => {
    if (supabase) {
      supabase.auth.getSession().then(({ data }) => setSession(data.session));
      const { data } = supabase.auth.onAuthStateChange((_e, s) => setSession(s));
      return () => data.subscription.unsubscribe();
    }
    // Internal mode: trust the stored token until the backend rejects it.
    const token = readStored();
    setInternalToken(token);
    api.get('/api/auth/mode')
      .then((r) => { setMode(r.mode === 'disabled' ? 'disabled' : r.mode); setAllowSignup(Boolean(r.allow_signup)); })
      .catch(() => {});
    if (!token) {
      // No token: still allow local servers running with AUTH_DISABLED=true.
      api.get('/api/me')
        .then((user) => setSession({ user, local: true }))
        .catch(() => setSession(null));
      return undefined;
    }
    api.get('/api/me')
      .then((user) => setSession({ user }))
      .catch(() => { setInternalToken(null); setSession(null); });
    return undefined;
  }, []);

  const signIn = useCallback(async (email, password) => {
    if (supabase) return supabase.auth.signInWithPassword({ email, password });
    try {
      const res = await api.post('/api/auth/login', { email, password });
      setInternalToken(res.token);
      setActingOrg(null);
      const user = await api.get('/api/me').catch(() => ({ email: res.email }));
      setSession({ user });
      return { error: null };
    } catch (error) {
      return { error };
    }
  }, []);

  const signUp = useCallback(async (body) => {
    try {
      const res = await api.post('/api/auth/signup', body);
      setInternalToken(res.token);
      setActingOrg(null);
      const user = await api.get('/api/me').catch(() => ({ email: res.email }));
      setSession({ user });
      return { error: null };
    } catch (error) {
      return { error };
    }
  }, []);

  const refresh = useCallback(async () => {
    const user = await api.get('/api/me');
    setSession((s) => ({ ...(s || {}), user }));
    return user;
  }, []);

  const signOut = useCallback(async () => {
    setActingOrg(null);
    if (supabase) return supabase.auth.signOut();
    setInternalToken(null);
    setSession(null);
    return undefined;
  }, []);

  return (
    <AuthContext.Provider value={{
      session, loading: session === undefined, user: session?.user || null,
      local: !supabase && session?.local === true, mode, allowSignup, signIn, signUp, signOut, refresh,
      role: session?.user?.role || 'owner', isSuperadmin: Boolean(session?.user?.is_superadmin),
      can: (min) => ({ reviewer: 1, editor: 2, owner: 3 }[session?.user?.role || 'owner'] || 0)
        >= ({ reviewer: 1, editor: 2, owner: 3 }[min] || 0),
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
