import React, { useEffect, useState } from 'react';
import { api, qs } from '../api.js';
import { inr } from '../format.js';
import MonthSelect from '../components/MonthSelect.jsx';
import { Alert, Badge, Button, Card, ConfirmDialog, DataTable, Empty, Pagination, Spinner, useAsync } from '../components/ui.jsx';

const PAGE = 15;

function Lookup({ onChanged }) {
  const [id, setId] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [emp, setEmp] = useState(null);
  const [dialog, setDialog] = useState(null);
  const [note, setNote] = useState('');

  const find = async (e) => {
    e && e.preventDefault();
    if (!id.trim()) return;
    setBusy(true);
    setErr('');
    setNote('');
    try {
      setEmp(await api(`/api/ope/access/employee/${encodeURIComponent(id.trim().toUpperCase())}`));
    } catch (ex) {
      setEmp(null);
      setErr(ex.message);
    } finally {
      setBusy(false);
    }
  };

  const act = (kind, m) => setDialog({ kind, month: m.payroll_month });
  const confirm = async (reason) => {
    const path = dialog.kind === 'grant' ? '/api/ope/access/reopen' : '/api/ope/access/revoke';
    await api(path, { method: 'POST', json: { employee_id: emp.employee_id, payroll_month: dialog.month, reason } });
    setNote(dialog.kind === 'grant'
      ? `${emp.employee_name} can now resubmit ${dialog.month} once.`
      : `Permission for ${dialog.month} was revoked.`);
    setDialog(null);
    await find();
    onChanged();
  };

  return (
    <Card title="Allow an employee to resubmit a month">
      <form className="opr-row" onSubmit={find}>
        <label className="opr-field opr-grow"><span>Employee ID</span>
          <input value={id} onChange={(e) => setId(e.target.value)} placeholder="e.g. JHS123" autoComplete="off" /></label>
        <Button busy={busy} onClick={find}>Find employee</Button>
      </form>
      <div style={{ marginTop: 12 }} className="opr-stack">
        <Alert>{err}</Alert>
        <Alert kind="success">{note}</Alert>
        {emp && (
          <>
            <div><strong>{emp.employee_name}</strong> <span className="opr-muted">({emp.employee_id})</span></div>
            <DataTable rowKey={(m) => m.payroll_month}
              empty={<Empty title="No submissions">This employee has not submitted any month, so nothing is locked.</Empty>}
              rows={emp.months}
              columns={[
                { key: 'payroll_month', title: 'Payroll month' },
                { key: 'overall_status', title: 'Status', render: (m) => <Badge status={m.overall_status} /> },
                { key: 'total_amount', title: 'Total', num: true, render: (m) => inr(m.total_amount, '—') },
                { key: 'submission_version', title: 'Version' },
                { key: 'perm', title: 'Resubmission', render: (m) => (m.reopen_permitted
                  ? <Badge status="active">Allowed once</Badge> : <span className="opr-muted">Locked</span>) },
                { key: 'act', title: '', render: (m) => (m.reopen_permitted
                  ? <Button variant="danger" className="opr-btn-sm" onClick={() => act('revoke', m)}>Revoke</Button>
                  : <Button className="opr-btn-sm" onClick={() => act('grant', m)}>Allow resubmission</Button>) },
              ]} />
          </>
        )}
      </div>
      {dialog && (
        <ConfirmDialog
          title={dialog.kind === 'grant' ? 'Allow resubmission?' : 'Revoke permission?'}
          danger={dialog.kind !== 'grant'}
          needReason
          reasonLabel={dialog.kind === 'grant' ? 'Reason for reopening (recorded in the audit trail)' : 'Reason for revoking'}
          confirmLabel={dialog.kind === 'grant' ? 'Allow once' : 'Revoke'}
          message={dialog.kind === 'grant'
            ? <>This lets <strong>{emp.employee_name}</strong> submit <strong>{dialog.month}</strong> one more time. Earlier entries and history are kept. Other months stay locked.</>
            : <>The employee will no longer be able to resubmit <strong>{dialog.month}</strong>.</>}
          onConfirm={confirm} onCancel={() => setDialog(null)} />
      )}
    </Card>
  );
}

export default function AccessControl() {
  const [month, setMonth] = useState('');
  const [status, setStatus] = useState('');
  const [q, setQ] = useState('');
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);
  useEffect(() => {
    const t = setTimeout(() => { setQuery(q); setPage(1); }, 350);
    return () => clearTimeout(t);
  }, [q]);
  const { loading, error, data, reload } = useAsync(
    () => api(`/api/ope/access/permissions?${qs({ month, status, q: query, page, page_size: PAGE })}`),
    [month, status, query, page],
  );
  return (
    <div className="opr-root opr-stack">
      <div>
        <h1 className="opr-page-title">Resubmission Access</h1>
        <p className="opr-muted" style={{ margin: 0 }}>
          An employee can submit a payroll month only once. Only HR or an Admin can allow a single employee to resubmit a single month.
        </p>
      </div>
      <Lookup onChanged={reload} />
      <Card title="Permission history">
        <div className="opr-row">
          <div className="opr-grow"><MonthSelect value={month} onChange={(m) => { setMonth(m); setPage(1); }} label="Month" /></div>
          <label className="opr-field"><span>Status</span>
            <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
              <option value="">All</option><option value="active">Active</option>
              <option value="used">Used</option><option value="revoked">Revoked</option>
            </select></label>
          <label className="opr-field opr-grow"><span>Search</span>
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Name or ID" /></label>
        </div>
        <div style={{ marginTop: 14 }}>
          {error && <Alert>{error}</Alert>}
          {loading && <Spinner />}
          {data && !loading && (
            <DataTable rowKey={(p) => p.id} rows={data.items}
              empty={<Empty title="No permissions yet">Granted resubmissions will be listed here.</Empty>}
              columns={[
                { key: 'employee_id', title: 'Employee', render: (p) => <><strong>{p.employee_name}</strong><div className="opr-small opr-muted">{p.employee_id}</div></> },
                { key: 'payroll_month', title: 'Month' },
                { key: 'status', title: 'Status', render: (p) => <Badge status={p.status} /> },
                { key: 'reason', title: 'Reason', render: (p) => <span className="opr-small">{p.reason}{p.revoke_reason ? ` · revoked: ${p.revoke_reason}` : ''}</span> },
                { key: 'granted_by', title: 'Granted by', render: (p) => <span className="opr-small">{p.granted_by}<br />{p.granted_at_ist}</span> },
                { key: 'used_at_ist', title: 'Used (IST)', render: (p) => p.used_at_ist || '—' },
              ]} />
          )}
          {data && <Pagination page={page} pageSize={PAGE} total={data.total} onPage={setPage} />}
        </div>
      </Card>
    </div>
  );
}
