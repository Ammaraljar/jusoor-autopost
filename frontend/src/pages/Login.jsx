import { useEffect, useState } from 'react';
import { Building2, LogIn } from 'lucide-react';
import { Button, Field } from '../components/ui';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { DIALECTS, LANGUAGES, useI18n } from '../lib/i18n';


function SignupForm({ onBack }) {
  const { signUp } = useAuth();
  const { t, lang } = useI18n();
  const [industries, setIndustries] = useState([]);
  const [form, setForm] = useState({ company: '', industry: 'general', language: lang, dialect: 'msa',
    name: '', email: '', password: '' });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  useEffect(() => { api.get('/api/auth/industries').then(setIndustries).catch(() => {}); }, []);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError('');
    const { error: err } = await signUp({ ...form, email: form.email.trim(),
      dialect: form.language === 'ar' ? form.dialect : null });
    if (err) setError(err.message || t('error'));
    setBusy(false);
  };

  return (
    <form className="card stack" onSubmit={submit}>
      <h2 style={{ fontSize: 20 }}><Building2 size={18} /> {t('signup_title')}</h2>
      <p className="small muted" style={{ marginTop: -8 }}>{t('signup_sub')}</p>
      <Field label={t('company_name')}>
        <input className="input" required minLength={2} value={form.company} onChange={(e) => set('company', e.target.value)} />
      </Field>
      <Field label={t('industry')} hint={t('industry_hint')}>
        <select className="select" value={form.industry} onChange={(e) => set('industry', e.target.value)}>
          {industries.map((i) => <option key={i.id} value={i.id}>{i[lang] || i.en}</option>)}
        </select>
      </Field>
      <div className="grid grid-2">
        <Field label={t('content_language')}>
          <select className="select" value={form.language} onChange={(e) => set('language', e.target.value)}>
            {LANGUAGES.map((l) => <option key={l.id} value={l.id}>{l.label}</option>)}
          </select>
        </Field>
        {form.language === 'ar' && (
          <Field label={t('dialect')}>
            <select className="select" value={form.dialect} onChange={(e) => set('dialect', e.target.value)}>
              {DIALECTS.map((o) => <option key={o} value={o}>{t(`dialect_${o}`)}</option>)}
            </select>
          </Field>
        )}
      </div>
      <Field label={t('your_name')}>
        <input className="input" value={form.name} onChange={(e) => set('name', e.target.value)} />
      </Field>
      <Field label={t('email')}>
        <input className="input ltr" type="email" required autoComplete="username" value={form.email}
          onChange={(e) => set('email', e.target.value)} />
      </Field>
      <Field label={t('password')} hint={t('password_min')}>
        <input className="input ltr" type="password" required minLength={8} autoComplete="new-password"
          value={form.password} onChange={(e) => set('password', e.target.value)} />
      </Field>
      {error && <div className="banner danger">{error}</div>}
      <Button variant="primary" type="submit" busy={busy} icon={Building2}>{t('create_company')}</Button>
      <button type="button" className="btn btn-ghost btn-sm" onClick={onBack}>{t('have_account')}</button>
    </form>
  );
}

export default function Login() {
  const { signIn, allowSignup } = useAuth();
  const { t, lang, setLang } = useI18n();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [serverError, setServerError] = useState('');
  const [signup, setSignup] = useState(false);

  useEffect(() => {
    try {
      const stored = sessionStorage.getItem('auth-error');
      if (stored) {
        setServerError(stored);
        sessionStorage.removeItem('auth-error');
      }
    } catch { /* ignore */ }
  }, []);
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError('');
    const { error: err } = await signIn(email.trim(), password);
    if (err) setError(err.message || t('error'));
    setBusy(false);
  };

  const langToggle = (
    <select className="select" style={{ maxWidth: 200, alignSelf: 'center' }} value={lang}
      onChange={(e) => setLang(e.target.value)} aria-label={t('ui_language')}>
      {LANGUAGES.map((l) => <option key={l.id} value={l.id}>{l.label}</option>)}
    </select>
  );

  if (signup) {
    return (
      <div className="login">
        <div className="stack" style={{ width: '100%', maxWidth: 440 }}>
          <SignupForm onBack={() => setSignup(false)} />
          {langToggle}
        </div>
      </div>
    );
  }

  return (
    <div className="login">
      <form className="card stack" onSubmit={submit}>
        <div className="brandmark" style={{ padding: 0 }}>
          <div className="mark">ج</div>
          <div>
            <b>{t('appName')}</b>
            <small className="muted">{t('appSub')}</small>
          </div>
        </div>
        <h2 style={{ fontSize: 20 }}>{t('login_title')}</h2>
        <Field label={t('email')}>
          <input className="input ltr" type="email" required autoComplete="username" value={email}
            onChange={(e) => setEmail(e.target.value)} />
        </Field>
        <Field label={t('password')}>
          <input className="input ltr" type="password" required autoComplete="current-password" value={password}
            onChange={(e) => setPassword(e.target.value)} />
        </Field>
        {serverError && <div className="banner warn">{serverError}</div>}
        {error && <div className="banner danger">{error}</div>}
        <Button variant="primary" type="submit" busy={busy} icon={LogIn}>{t('sign_in')}</Button>
        {allowSignup && (
          <button type="button" className="btn btn-sm" onClick={() => setSignup(true)}>
            <Building2 size={14} /> {t('new_company')}
          </button>
        )}
        {langToggle}
      </form>
    </div>
  );
}
