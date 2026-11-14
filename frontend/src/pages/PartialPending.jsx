import React, { useEffect, useState } from 'react';
import { api, qs } from '../api.js';
import { inr } from '../format.js';
import { Alert, Button, Card, ConfirmDialog, DataTable, Empty, Modal, Spinner, Stat, useAsync } from '../components/ui.jsx';

const st = (x) => (x ? x.status : '—');

export default function PartialPending() {
  const [q, setQ] = useState('');
  const [query, setQuery] = useState('');
  const [sel, setSel] = useState(null);
  const [appr, setAppr] = useState(null);
  const [rej, setRej] = useState(null);
  const [done, setDone] = useState('');
  useEffect(() => { const t = setTimeout(() => setQuery(q), 350); return () => clearTimeout(t); }, [q]);
  const { loading, error, data, reload } = useAsync(() => api(`/api/ope/hr/partial-pending?${qs({ q: query })}`), [query]);

  // keep the list current without a manual browser refresh
  useEffect(() => {
    const id = setInterval(reload, 30000);
    const on = () => reload();
    window.addEventListener('ope:submitted', on);
    return () => { clearInterval(id); window.removeEventListener('ope:submitted', on); };
  }, [reload]);

  const cols = [
    { key: 'employee', title: 'Employee', render: (r) => <><strong>{r.employee_name || '—'}</strong><div className="opr-small opr-muted">{r.employee_id}</div></> },
    { key: 'designation', title: 'Designation', render: (r) => r.designation || '—' },
    { key: 'department', title: 'Department', render: (r) => r.department || '—' },
    { key: 'rm', title: 'Reporting Manager', render: (r) => r.reporting_manager || '—' },
    { key: 'amt', title: 'Amount', num: true, render: (r) => inr(r.submitted_amount) },
    { key: 'date', title: 'Submitted (IST)', render: (r) => r.submission_date || '—' },
    { key: 'rms', title: 'Reporting Mgr', render: (r) => st(r.rm_status) },
    { key: 'ps', title: 'Partner', render: (r) => st(r.partner_status) },
    { key: 'hrs', title: 'HR', render: (r) => st(r.hr_status) },
    { key: 'stage', title: 'Current stage', render: (r) => r.current_stage },
    { key: 'v', title: '', render: (r) => <><Button variant="ghost" className="opr-btn-sm" onClick={(e) => { e.stopPropagation(); setSel(r); }}>View</Button>{' '}
      <Button className="opr-btn-sm" onClick={(e) => { e.stopPropagation(); setAppr(r); }}>Approve</Button>{' '}
      <Button variant="danger" className="opr-btn-sm" onClick={(e) => { e.stopPropagation(); setRej(r); }}>Reject</Button></> },
  ];

  return (
    <div className="opr-root opr-stack">
      <div>
        <h1 className="opr-page-title">Partial Pending</h1>
        <p className="opr-muted" style={{ margin: 0 }}>Submitted, but still waiting on a Reporting Manager or Partner. HR can approve directly from here; Reporting Manager / Partner approvals will then only update the status.</p>
      </div>
      <Card>
        <div className="opr-row">
          <label className="opr-field opr-grow"><span>Search employee</span>
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Name or ID" /></label>
          <Button variant="ghost" onClick={reload} disabled={loading}>Refresh</Button>
        </div>
      </Card>
      {done && <Alert kind="success" onClose={() => setDone('')}>{done}</Alert>}
      {error && <Alert>{error}</Alert>}
      {loading && !data && <Spinner />}
      {data && (
        <>
          <div className="opr-stats"><Stat label="Awaiting RM / Partner" value={data.total_count} tone="warn" /></div>
          <Card>
            <DataTable rows={data.rows} rowKey={(r) => `${r.employee_id}|${r.payroll_month}`} columns={cols}
              onRowClick={(r) => setSel(r)}
              empty={<Empty title="Nothing partially pending">Every submission is either with HR or already decided.</Empty>} />
          </Card>
        </>
      )}
      {appr && (
        <ConfirmDialog title="Approve as HR" confirmLabel="Approve" needReason reasonLabel="Remark (min 3 characters)"
          message={`Approve ${appr.employee_name} (${appr.employee_id}) for ${appr.payroll_month} directly, before Reporting Manager / Partner approval? They can still approve later; the record will not return to HR Pending.`}
          onCancel={() => setAppr(null)}
          onConfirm={async (remark) => {
            await api('/api/ope/hr/partial-pending/approve', { method: 'POST', json: { employee_id: appr.employee_id, payroll_month: appr.payroll_month, remark } });
            setDone(`${appr.employee_name}: approved by HR.`);
            setAppr(null); setSel(null); reload();
          }} />
      )}
      {rej && (
        <ConfirmDialog title="Reject as HR" confirmLabel="Reject" danger needReason reasonLabel="Rejection reason (min 3 characters)"
          message={`Reject ${rej.employee_name} (${rej.employee_id}) for ${rej.payroll_month}? It moves to HR Rejected and the Reporting Manager / Partner can no longer approve it.`}
          onCancel={() => setRej(null)}
          onConfirm={async (reason) => {
            await api('/api/ope/hr/partial-pending/reject', { method: 'POST', json: { employee_id: rej.employee_id, month_range: rej.payroll_month, reason } });
            setDone(`${rej.employee_name}: rejected by HR.`);
            setRej(null); setSel(null); reload();
          }} />
      )}
      {sel && (
        <Modal title={`${sel.employee_name} · ${sel.payroll_month}`} subtitle={sel.current_stage} onClose={() => setSel(null)} wide
          footer={<Button variant="ghost" onClick={() => setSel(null)}>Close</Button>}>
          <table className="opr-table"><thead><tr><th>Level</th><th>Status</th><th>Approver</th><th>Date</th><th>Remark</th></tr></thead>
            <tbody>{sel.history.map((h) => (
              <tr key={h.level}><td>{h.level_name}</td><td>{h.status}</td><td>{h.approver || '—'}</td><td>{h.date || '—'}</td><td>{h.remark || '—'}</td></tr>))}
            </tbody></table>
          <Button variant="ghost" className="opr-btn-sm" onClick={() => window.OPEReact.openDetail(sel.employee_id, sel.payroll_month)}>Open full details</Button>
        </Modal>
      )}
    </div>
  );
}
