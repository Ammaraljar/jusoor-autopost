import { createClient } from '@supabase/supabase-js';

const url = import.meta.env.VITE_SUPABASE_URL;
const key = import.meta.env.VITE_SUPABASE_ANON_KEY;

// When Supabase is not configured the dashboard runs in local "no-auth" mode
// (the backend must then run with AUTH_DISABLED=true).
export const supabase = url && key ? createClient(url, key) : null;
