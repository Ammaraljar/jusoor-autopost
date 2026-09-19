import { createContext, useContext, useEffect, useState } from 'react';
import { supabase } from './supabase';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [session, setSession] = useState(undefined);

  useEffect(() => {
    if (!supabase) {
      setSession({ user: { email: 'local' }, local: true });
      return undefined;
    }
    supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data } = supabase.auth.onAuthStateChange((_event, s) => setSession(s));
    return () => data.subscription.unsubscribe();
  }, []);

  const value = {
    session,
    loading: session === undefined,
    user: session?.user || null,
    local: !supabase,
    signIn: (email, password) => supabase.auth.signInWithPassword({ email, password }),
    signOut: () => supabase?.auth.signOut(),
  };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
