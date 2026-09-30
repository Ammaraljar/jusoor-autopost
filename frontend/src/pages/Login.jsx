import { useEffect, useState } from 'react';
import { LogIn } from 'lucide-react';
import { Button, Field } from '../components/ui';
import { useAuth } from '../lib/auth';
import { useI18n } from '../lib/i18n';

export default function Login() {
  const { signIn } = useAuth();
  const { t, lang, setLang } = useI18n();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [serverError, setServerError] = useState('');

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
    if (err) setError(err.message);
    setBusy(false);
  };

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
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => setLang(lang === 'ar' ? 'en' : 'ar')}>
          {t('language')}
        </button>
      </form>
    </div>
  );
}
