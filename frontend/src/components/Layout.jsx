import { useEffect, useState } from 'react';
import { Suspense } from 'react';
import { Loading } from './ui';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { BarChart3, CalendarDays, Eye, Globe, Images, Inbox, Languages, LogOut, Menu, Moon, Palette, Rss, Settings,
  Shield, Sun, SunMoon, Target, Users } from 'lucide-react';
import { api, getActingOrg, setActingOrg } from '../lib/api';
import { useAuth } from '../lib/auth';
import { useI18n } from '../lib/i18n';

export default function Layout() {
  const { t, lang, setLang, theme, setTheme } = useI18n();
  const { user, signOut, local, can, isSuperadmin } = useAuth();
  const [orgs, setOrgs] = useState([]);
  useEffect(() => {
    if (isSuperadmin) api.get('/api/admin/orgs').then(setOrgs).catch(() => {});
  }, [isSuperadmin]);
  const org = user?.org;
  const switchOrg = (id) => {
    setActingOrg(String(id) === String(user?.home_org_id || '') ? null : id);
    window.location.assign('/');
  };
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(null);
  const location = useLocation();

  useEffect(() => { setOpen(false); }, [location.pathname]);
  useEffect(() => {
    let alive = true;
    const load = () => api.get('/api/drafts/counts').then((c) => alive && setPending(c.pending_review)).catch(() => {});
    load();
    const id = setInterval(load, 30000);
    return () => { alive = false; clearInterval(id); };
  }, [location.pathname]);

  const nextTheme = { auto: 'light', light: 'dark', dark: 'auto' }[theme];
  const ThemeIcon = { auto: SunMoon, light: Sun, dark: Moon }[theme];
  const editor = can('editor');
  const links = [
    { to: '/', icon: Inbox, label: t('nav_review'), count: pending, end: true },
    editor && { to: '/sources', icon: Rss, label: t('nav_sources') },
    { to: '/calendar', icon: CalendarDays, label: t('nav_calendar') },
    editor && { to: '/campaigns', icon: Target, label: t('nav_campaigns') },
    editor && { to: '/library', icon: Images, label: t('nav_library') },
    editor && { to: '/brand', icon: Palette, label: t('nav_brand') },
    { to: '/stats', icon: BarChart3, label: t('nav_stats') },
    can('owner') && { to: '/team', icon: Users, label: t('nav_team') },
    can('owner') && { to: '/settings', icon: Settings, label: t('nav_settings') },
    isSuperadmin && { to: '/admin', icon: Shield, label: t('nav_admin') },
  ].filter(Boolean);
  const companyName = org?.name || (lang === 'ar' ? 'جسور' : 'JUSOOR');

  return (
    <div className="app">
      <div className="topbar">
        <button onClick={() => setOpen(true)} aria-label="menu"><Menu size={22} /></button>
        <b>{t('appName')}</b>
      </div>
      <aside className={`sidebar ${open ? 'open' : ''}`}>
        <div className="brandmark">
          <div className="mark">{(companyName || 'ج').trim().charAt(0).toUpperCase()}</div>
          <div style={{ minWidth: 0 }}>
            <b style={{ display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{companyName}</b>
            <small>{user?.role && !isSuperadmin ? t(`role_${user.role}`) : t('appSub')}</small>
          </div>
        </div>
        {isSuperadmin && orgs.length > 1 && (
          <div style={{ padding: '0 14px 10px' }}>
            <select className="select" style={{ fontSize: 13 }} value={getActingOrg() || org?.id || ''}
              onChange={(e) => switchOrg(e.target.value)} aria-label={t('switch_company')}>
              {orgs.map((o) => <option key={o.id} value={o.id}>{o.name}{o.status !== 'active' ? ` (${t('suspended')})` : ''}</option>)}
            </select>
          </div>
        )}
        {user?.role === 'reviewer' && (
          <div className="xs muted" style={{ padding: '0 14px 10px' }}><Eye size={12} /> {t('reviewer_mode')}</div>
        )}
        <nav className="nav">
          {links.map(({ to, icon: Icon, label, count, end }) => (
            <NavLink key={to} to={to} end={end}>
              <Icon size={18} /> {label}
              {count ? <span className="count">{count}</span> : null}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div className="row">
            <button onClick={() => setLang(lang === 'ar' ? 'en' : 'ar')}><Languages size={14} /> {t('language')}</button>
            <button onClick={() => setTheme(nextTheme)} aria-label={t('theme')}><ThemeIcon size={14} /></button>
          </div>
          {!local && (
            <>
              <div className="xs ltr" style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{user?.email}</div>
              <button onClick={signOut}><LogOut size={14} /> {t('logout')}</button>
            </>
          )}
          {local && <div className="xs"><Globe size={12} /> {t('local_mode')}</div>}
        </div>
      </aside>
      {open && <div className="modal-back" style={{ zIndex: 55 }} onClick={() => setOpen(false)} />}
      <main className="main"><Suspense fallback={<Loading />}><Outlet /></Suspense></main>
    </div>
  );
}
