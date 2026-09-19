import { CheckCircle2, XCircle } from 'lucide-react';
import { Empty, ErrorBox, Loading, PageHead, useLoad } from '../components/ui';
import { api } from '../lib/api';
import { useI18n } from '../lib/i18n';

const STATUS_ORDER = ['pending_review', 'approved', 'scheduled', 'published', 'rejected', 'failed'];

function Bars({ rows }) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  return rows.map((r) => (
    <div className="bar-row" key={r.label} title={`${r.label}: ${r.value}`}>
      <span className="clamp-2">{r.label}</span>
      <div className="bar-track" role="img" aria-label={`${r.label}: ${r.value}`}>
        <div className="bar-fill" style={{ width: `${(100 * r.value) / max}%` }} />
      </div>
      <b style={{ textAlign: 'end' }}>{r.value}</b>
    </div>
  ));
}

export default function Stats() {
  const { t } = useI18n();
  const stats = useLoad(() => api.get('/api/stats?days=30'), []);
  if (stats.loading && !stats.data) return <Loading />;
  if (stats.error) return <ErrorBox error={stats.error} onRetry={stats.reload} />;
  const s = stats.data;
  const total = Object.values(s.by_status).reduce((a, b) => a + b, 0);

  const platforms = {};
  s.by_platform.forEach((r) => {
    platforms[r.platform] ||= { success: 0, error: 0 };
    platforms[r.platform][r.status] += r.count;
  });

  const kpis = [
    [t('collected'), s.articles],
    [t('drafts'), total],
    [t('st_published'), s.by_status.published || 0],
    [t('approval_rate'), s.approval_rate == null ? '—' : `${s.approval_rate}%`],
  ];

  return (
    <>
      <PageHead title={t('stats_title')} sub={t('stats_sub')} />
      <div className="grid grid-4" style={{ marginBottom: 16 }}>
        {kpis.map(([label, value]) => (
          <div key={label} className="card kpi">
            <div className="l">{label}</div>
            <div className="v">{value}</div>
          </div>
        ))}
      </div>
      <div className="grid grid-2">
        <div className="card card-pad">
          <h3>{t('by_status')}</h3>
          {total === 0 ? <Empty>—</Empty> : (
            <Bars rows={STATUS_ORDER.map((k) => ({ label: t(`st_${k}`), value: s.by_status[k] || 0 }))} />
          )}
        </div>
        <div className="card card-pad">
          <h3>{t('by_source')}</h3>
          {s.by_source.length === 0 ? <Empty>—</Empty> : (
            <Bars rows={s.by_source.map((r) => ({ label: r.source, value: r.drafts }))} />
          )}
        </div>
        <div className="card card-pad">
          <h3>{t('by_platform')}</h3>
          {Object.keys(platforms).length === 0 ? <Empty>—</Empty> : (
            <table className="table">
              <thead><tr><th>{t('platform')}</th><th>{t('success')}</th><th>{t('failed')}</th></tr></thead>
              <tbody>
                {Object.entries(platforms).map(([p, v]) => (
                  <tr key={p}>
                    <td className="bold">{p}</td>
                    <td><span className="row"><CheckCircle2 size={15} color="var(--ok)" /> {v.success}</span></td>
                    <td><span className="row"><XCircle size={15} color="var(--danger)" /> {v.error}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </>
  );
}
