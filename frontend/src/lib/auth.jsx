import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { api, setInternalToken } from './api';
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
      .then((r) => setMode(r.mode === 'disabled' ? 'disabled' : r.mode))
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
      setSession({ user: { email: res.email } });
      return { error: null };
    } catch (error) {
      return { error };
    }
  }, []);

  const signOut = useCallback(async () => {
    if (supabase) return supabase.auth.signOut();
    setInternalToken(null);
    setSession(null);
    return undefined;
  }, []);

  return (
    <AuthContext.Provider value={{
      session, loading: session === undefined, user: session?.user || null,
      local: !supabase && session?.local === true, mode, signIn, signOut,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
