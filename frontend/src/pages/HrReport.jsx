import React, { useEffect, useState } from 'react';
import { api, download, qs } from '../api.js';
import { inr } from '../format.js';
import MonthSelect from '../components/MonthSelect.jsx';
import { Alert, Badge, Button, Card, DataTable, Empty, Pagination, Spinner, Stat, useAsync } from '../components/ui.jsx';

const PAGE = 25;
const FILTERS = [['', 'All'], ['pending', 'Pending'], ['approved', 'Approved'], ['rejected', 'Rejected'], ['partial', 'Partial'], ['hr_direct', 'HR direct approved']];

export default function HrReport() {
  const [month, setMonth] = useState('');
  const [status, setStatus] = useState('');
  const [partner, setPartner] = useState('');
  const [manager, setManager] = useState('');
  const [q, setQ] = useState('');
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);
  const [busy, setBusy] = useState(false);
  const [dlError, setDlError] = useState('');

  useEffect(() => {
    const t = setTimeout(() => { setQuery(q); setPage(1); }, 350);
    return () => clearTimeout(t);
  }, [q]);

  const { loading, error, data, reload } = useAsync(
    () => api(`/api/hr/report?${qs({ month, status, partner, manager, q: query, page, page_size: PAGE })}`),
    [month, status, partner, manager, query, page],
  );

  const exportXlsx = async (statusOverride) => {
    setBusy(true);
    setDlError('');
    try {
      await download(`/api/hr/report/export?${qs({ month, status: statusOverride === undefined ? status : statusOverride, partner, manager, q: query })}`, 'OPE_HR_Report.xlsx');
    } catch (e) {
      setDlError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const s = data && data.summary;
  const cols = [
    { key: 'employee_id', title: 'Employee', render: (r) => <><strong>{r.employee_name || '—'}</strong><div className="opr-small opr-muted">{r.employee_id}{r.fixed_amount ? ' · fixed amount' : ''}</div></> },
    { key: 'ope_limit', title: 'Limit', num: true, render: (r) => inr(r.ope_limit, '—') },
    { key: 'submitted_amount', title: 'Submitted', num: true, render: (r) => inr(r.submitted_amount) },
    { key: 'rm_approved_amount', title: 'Reporting Mgr approved', num: true, render: (r) => inr(r.rm_approved_amount) },
    { key: 'partner_approved_amount', title: 'Partner approved', num: true, render: (r) => inr(r.partner_approved_amount, '—') },
    { key: 'hr_approved_amount', title: 'HR approved', num: true, render: (r) => inr(r.hr_approved_amount) },
    { key: 'status', title: 'Status', render: (r) => <><Badge status={r.status} /><div className="opr-small opr-muted">{r.stage}</div></> },
    { key: 'submitted_at', title: 'Submitted (IST)', render: (r) => r.submitted_at || '—' },
    { key: 'remarks', title: 'Remarks', render: (r) => <span className="opr-small">{r.remarks || '—'}</span> },
    { key: 'view', title: '', render: (r) => (
      <Button variant="ghost" className="opr-btn-sm" onClick={(e) => { e.stopPropagation(); window.OPEReact.openDetail(r.employee_id, r.payroll_month); }}>
        Details
      </Button>) },
  ];

  return (
    <div className="opr-root opr-stack">
      <div>
        <h1 className="opr-page-title">HR Monthly Report</h1>
        <p className="opr-muted" style={{ margin: 0 }}>Counts use each record's current status. Full status-change history is in the audit trail.</p>
      </div>

      <Card>
        <div className="opr-row">
          <div className="opr-grow"><MonthSelect value={month} allowAll onChange={(m) => { setMonth(m); setPage(1); }} /></div>
          <label className="opr-field opr-grow"><span>Partner</span>
            <select value={partner} onChange={(e) => { setPartner(e.target.value); setManager(''); setPage(1); }}>
              <option value="">All partners</option>
              {((data && data.partners) || []).map((x) => (
                <option key={x.code} value={x.code}>{x.name} ({x.code}) · {x.records} records</option>
              ))}
            </select>
          </label>
          <label className="opr-field opr-grow"><span>Reporting Manager</span>
            <select value={manager} onChange={(e) => { setManager(e.target.value); setPage(1); }}>
              <option value="">All reporting managers</option>
              {((data && data.managers) || []).map((x) => (
                <option key={x.code} value={x.code}>{x.name} ({x.code}) · {x.records} records</option>
              ))}
            </select>
          </label>
          <label className="opr-field opr-grow"><span>Search employee</span>
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Name or ID" /></label>
          <Button variant="ghost" onClick={reload} disabled={loading}>Refresh</Button>
          <Button onClick={() => exportXlsx()} busy={busy} disabled={!data || !s || !s.total_records}>
            {status ? `Download ${FILTERS.find((f) => f[0] === status)[1]} (Excel)` : 'Download Excel'}
          </Button>
          <Button variant="ok" onClick={() => exportXlsx('hr_direct')} busy={busy}
            disabled={!data || !data.hr_direct_count}>
            Download HR direct approved (Excel){data && data.hr_direct_count ? ` · ${data.hr_direct_count}` : ''}
          </Button>
        </div>
        {dlError && <div style={{ marginTop: 10 }}><Alert onClose={() => setDlError('')}>{dlError}</Alert></div>}
      </Card>

      {error && <Alert>{error}</Alert>}
      {loading && !data && <Spinner label="Loading report…" />}

      {s && (
        <>
          <div className="opr-stats">
            <Stat label="Total records" value={s.total_records} />
            <Stat label="Approved" value={s.counts.approved} tone="ok" />
            <Stat label="Pending" value={s.counts.pending} tone="warn" />
            <Stat label="Rejected" value={s.counts.rejected} tone="bad" />
            <Stat label="Partially approved" value={s.counts.partial} tone="mid" />
            <Stat label="Submitted amount" value={inr(s.total_submitted_amount)} />
            <Stat label="HR approved amount" value={inr(s.total_hr_approved_amount)} tone="ok" />
            {s.eligible_in_upload != null && <Stat label={`Eligible (upload v${s.upload_version})`} value={s.eligible_in_upload} />}
            {s.not_submitted != null && <Stat label="Eligible, not submitted" value={s.not_submitted} />}
          </div>

          <Card title={`Records · ${s.payroll_month}`}
            actions={(
              <div className="opr-chips" role="group" aria-label="Filter by status">
                {FILTERS.map(([v, label]) => (
                  <button key={v} type="button" className="opr-chip" aria-pressed={status === v}
                    onClick={() => { setStatus(v); setPage(1); }}>{label}</button>
                ))}
              </div>
            )}>
            {loading && <Spinner />}
            {!loading && (
              <DataTable rows={data.rows} rowKey={(r) => r.employee_id} columns={cols}
                onRowClick={(r) => window.OPEReact.openDetail(r.employee_id, r.payroll_month)}
                empty={<Empty title="No records">No submissions match this month and filter.</Empty>} />
            )}
            <Pagination page={page} pageSize={PAGE} total={data.total_rows} onPage={setPage} />
          </Card>
        </>
      )}
    </div>
  );
}
