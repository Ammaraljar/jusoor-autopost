import { useState } from 'react';
import { KeyRound, Plus, Trash2, UserCheck, UserX, Users } from 'lucide-react';
import { Button, Empty, ErrorBox, Field, Loading, Modal, PageHead, useAction, useLoad } from '../components/ui';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { fmtDateTime } from '../lib/format';
import { useI18n } from '../lib/i18n';

const ROLES = ['owner', 'editor', 'reviewer'];

function MemberModal({ onClose, onSaved }) {
  const { t } = useI18n();
  const [f, setF] = useState({ name: '', email: '', role: 'editor', password: '' });
  const [busy, run] = useAction();
  const set = (k, v) => setF((x) => ({ ...x, [k]: v }));
  const save = () => run('save', async () => {
    await api.post('/api/team', { ...f, email: f.email.trim() });
    onSaved();
    onClose();
  }, t('saved'));
  return (
    <Modal title={t('add_member')} onClose={onClose} footer={(
      <>
        <Button onClick={onClose}>{t('cancel')}</Button>
        <Button variant="primary" busy={busy === 'save'} disabled={!f.email || f.password.length < 8} onClick={save}>{t('add')}</Button>
      </>
    )}>
      <div className="stack">
        <Field label={t('your_name')}><input className="input" value={f.name} onChange={(e) => set('name', e.target.value)} /></Field>
        <Field label={t('email')}><input className="input ltr" type="email" value={f.email} onChange={(e) => set('email', e.target.value)} /></Field>
        <Field label={t('role')} hint={t(`role_${f.role}_hint`)}>
          <select className="select" value={f.role} onChange={(e) => set('role', e.target.value)}>
            {ROLES.map((r) => <option key={r} value={r}>{t(`role_${r}`)}</option>)}
          </select>
        </Field>
        <Field label={t('temp_password')} hint={t('temp_password_hint')}>
          <input className="input ltr" type="text" autoComplete="new-password" value={f.password}
            onChange={(e) => set('password', e.target.value)} />
        </Field>
      </div>
    </Modal>
  );
}

function PasswordModal({ member, onClose }) {
  const { t } = useI18n();
  const [pw, setPw] = useState('');
  const [busy, run] = useAction();
  const save = () => run('pw', async () => {
    await api.patch(`/api/team/${member.id}`, { password: pw });
    onClose();
  }, t('saved'));
  return (
    <Modal title={`${t('reset_password')} — ${member.email}`} onClose={onClose} footer={(
      <>
        <Button onClick={onClose}>{t('cancel')}</Button>
        <Button variant="primary" busy={busy === 'pw'} disabled={pw.length < 8} onClick={save}>{t('save')}</Button>
      </>
    )}>
      <Field label={t('temp_password')} hint={t('temp_password_hint')}>
        <input className="input ltr" type="text" autoComplete="new-password" value={pw} onChange={(e) => setPw(e.target.value)} />
      </Field>
    </Modal>
  );
}

export default function Team() {
  const { t } = useI18n();
  const { user } = useAuth();
  const team = useLoad(() => api.get('/api/team'), []);
  const [adding, setAdding] = useState(false);
  const [pwFor, setPwFor] = useState(null);
  const [busy, run] = useAction();

  if (team.loading && !team.data) return <Loading />;
  const patch = (m, body) => run(`p-${m.id}`, async () => { await api.patch(`/api/team/${m.id}`, body); team.reload(true); }, t('saved'));
  const remove = (m) => window.confirm(t('confirm_delete')) &&
    run(`d-${m.id}`, async () => { await api.del(`/api/team/${m.id}`); team.reload(true); });

  return (
    <>
      <PageHead title={t('team_title')} sub={t('team_sub')}>
        <Button variant="primary" icon={Plus} onClick={() => setAdding(true)}>{t('add_member')}</Button>
      </PageHead>
      {team.error && <ErrorBox error={team.error} onRetry={team.reload} />}
      <div className="card card-pad small muted" style={{ marginBottom: 16 }}>
        {ROLES.map((r) => <div key={r}><b>{t(`role_${r}`)}</b> — {t(`role_${r}_hint`)}</div>)}
      </div>
      {(team.data || []).length === 0 ? <Empty icon={Users}>{t('team_empty')}</Empty> : (
        <div className="stack">
          {team.data.map((m) => (
            <div key={m.id} className="card card-pad row" style={{ opacity: m.active ? 1 : 0.6 }}>
              <div style={{ minWidth: 0, flex: '1 1 220px' }}>
                <b>{m.name || m.email}</b> {m.id === user?.id && <span className="pill">{t('you')}</span>}
                {!m.active && <span className="pill">{t('inactive')}</span>}
                <div className="xs muted ltr">{m.email}</div>
                <div className="xs muted">{t('last_login')}: {m.last_login_at ? fmtDateTime(m.last_login_at) : '—'}</div>
              </div>
              <select className="select" style={{ width: 'auto' }} value={m.role} disabled={busy === `p-${m.id}`}
                onChange={(e) => patch(m, { role: e.target.value })}>
                {ROLES.map((r) => <option key={r} value={r}>{t(`role_${r}`)}</option>)}
              </select>
              <Button size="sm" icon={KeyRound} onClick={() => setPwFor(m)}>{t('reset_password')}</Button>
              {m.id !== user?.id && (
                <>
                  <Button size="sm" icon={m.active ? UserX : UserCheck} busy={busy === `p-${m.id}`}
                    onClick={() => patch(m, { active: !m.active })}>{m.active ? t('deactivate') : t('activate')}</Button>
                  <Button size="sm" variant="danger" icon={Trash2} busy={busy === `d-${m.id}`} onClick={() => remove(m)} />
                </>
              )}
            </div>
          ))}
        </div>
      )}
      {adding && <MemberModal onClose={() => setAdding(false)} onSaved={() => team.reload(true)} />}
      {pwFor && <PasswordModal member={pwFor} onClose={() => setPwFor(null)} />}
    </>
  );
}
