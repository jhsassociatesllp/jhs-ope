import React from 'react';
import { api, qs } from '../api.js';
import { ACTION_LABEL, inr } from '../format.js';
import { Alert, Badge, DataTable, Modal, Spinner, useAsync } from './ui.jsx';

export function Timeline({ events, source }) {
  if (!events || !events.length) return <p className="opr-muted">No history recorded yet.</p>;
  return (
    <>
      {source === 'reconstructed' && (
        <Alert kind="info">
          This is an older submission from before the detailed audit log existed, so the history below is
          rebuilt from its status record.
        </Alert>
      )}
      <ol className="opr-timeline" style={{ marginTop: 10 }}>
        {events.map((e, i) => (
          <li key={e.id || i} className={`opr-ev-${e.action}`}>
            <strong>
              {e.stage && ['approved', 'rejected', 'submitted', 'resubmitted'].includes(e.action)
                ? `${e.stage}: ${ACTION_LABEL[e.action] || e.action}`
                : ACTION_LABEL[e.action] || e.action}
            </strong>
            {e.submission_version > 1 && <span className="opr-muted"> · version {e.submission_version}</span>}
            <time dateTime={e.at_utc}>{e.at_ist || '—'}{e.actor_name || e.actor_id ? ` · by ${e.actor_name || e.actor_id}` : ''}</time>
            {(e.original_amount != null || e.stage_amount != null) && e.action !== 'reopened' && (
              <div className="opr-small">
                Submitted {inr(e.original_amount, '—')}
                {e.action === 'approved' && <> · approved at this stage <strong>{inr(e.stage_amount, '—')}</strong></>}
                {e.action === 'rejected' && <> · rejected <strong>{inr(e.rejected_amount, '—')}</strong></>}
                {e.entry_count != null && <> · {e.entry_count} entr{e.entry_count === 1 ? 'y' : 'ies'}</>}
              </div>
            )}
            {(e.prev_status || e.new_status) && e.prev_status !== e.new_status && (
              <div className="opr-small opr-muted">Status: {e.prev_status || '—'} → {e.new_status || '—'}</div>
            )}
            {e.remark && <div className="opr-small">“{e.remark}”</div>}
          </li>
        ))}
      </ol>
    </>
  );
}

function StageCard({ s }) {
  const rejected = s.status === 'rejected' || s.status === 'partial';
  return (
    <div className="opr-stage">
      <h4>
        <span>{s.stage}</span>
        <Badge status={s.status} />
      </h4>
      <div className="opr-small opr-muted">{s.approver_name ? `${s.approver_name} (${s.approver_code})` : s.approver_code}</div>
      <div>
        <div className="opr-small opr-muted">Amount approved at this stage</div>
        <div className="opr-amt">{inr(s.approved_amount)}</div>
      </div>
      {rejected && (
        <div className="opr-small">Rejected amount: <strong>{inr(s.rejected_amount)}</strong>
          {' '}({s.rejected_count} entr{s.rejected_count === 1 ? 'y' : 'ies'})</div>
      )}
      {s.approved_count > 0 && <div className="opr-small">{s.approved_count} entr{s.approved_count === 1 ? 'y' : 'ies'} approved</div>}
      {s.remark && <div className="opr-small">Remark: {s.remark}</div>}
      {s.rejection_reason && <div className="opr-small" style={{ color: 'var(--opr-bad)' }}>Rejection reason: {s.rejection_reason}</div>}
      <div className="opr-small opr-muted">{s.acted_at_ist ? `${s.acted_by || ''} · ${s.acted_at_ist}` : 'No decision yet'}</div>
    </div>
  );
}

export function DetailBody({ d }) {
  const sd = d.status;
  const lock = d.lock || {};
  const openPdf = (id) => {
    if (typeof window.fetchAndOpenPdf === 'function') window.fetchAndOpenPdf(id);
  };
  const cols = [
    { key: 'date', title: 'Date' },
    { key: 'client', title: 'Client' },
    { key: 'project', title: 'Project', render: (e) => `${e.project_id || '-'} · ${e.project_name || '-'}` },
    { key: 'route', title: 'From → To', render: (e) => `${e.location_from || '-'} → ${e.location_to || '-'}` },
    { key: 'travel_mode', title: 'Mode' },
    { key: 'original_amount', title: 'Submitted', num: true,
      render: (e) => <>{inr(e.original_amount)}{!e.original_amount_known && <span className="opr-muted opr-small" title="Original value was not recorded for this older entry"> *</span>}</> },
    { key: 'amount', title: 'Current', num: true,
      render: (e) => <strong style={e.amount !== e.original_amount ? { color: 'var(--opr-warn)' } : undefined}>{inr(e.amount)}</strong> },
    { key: 'status', title: 'Status', render: (e) => (
      <>
        <Badge status={e.status === 'saved' ? 'pending' : e.status} />
      </>) },
    { key: 'ticket_pdf', title: 'Ticket', render: (e) => (e.ticket_pdf
      ? <button type="button" className="opr-link" onClick={() => openPdf(e.ticket_pdf)}>View</button> : '—') },
  ];
  return (
    <div className="opr-stack">
      <div className="opr-kv">
        <div><span>Payroll month</span><strong>{d.payroll_month}</strong></div>
        <div><span>Current status</span><strong><Badge status={sd.overall_status} /></strong></div>
        <div><span>OPE limit for this month</span><strong>{d.limit.amount != null ? inr(d.limit.amount) : '—'}</strong></div>
        <div><span>Submission version</span><strong>{sd.submission_version}</strong></div>
        <div><span>Submitted at</span><strong>{sd.submitted_at_ist || '—'}</strong></div>
      </div>

      {sd.is_fixed_amount && (
        <Alert kind="info">This is a fixed monthly OPE amount set by HR. It is sent straight to HR for approval.</Alert>
      )}
      {lock.reason === 'already_submitted' && (
        <Alert kind="warn">{lock.message}</Alert>
      )}
      {lock.reopen_permitted && (
        <Alert kind="success">HR has allowed this employee to resubmit this month. The permission can be used once.</Alert>
      )}

      <div className="opr-stats">
        <div className="opr-stat"><span>Original amount submitted by employee</span><strong>{inr(d.amounts.original_submitted)}</strong></div>
        <div className="opr-stat opr-tone-mid"><span>Current total (after any edits)</span><strong>{inr(d.amounts.current_total, '—')}</strong></div>
      </div>
      {d.amounts.edit_history.length > 0 && (
        <Alert kind="info">
          The month total was adjusted by a reviewer (see “Total amount edits”). Individual entry amounts below are unchanged;
          the stage amounts and the current total use the adjusted total.
        </Alert>
      )}
      {d.amounts.original_estimated && (
        <p className="opr-small opr-muted">* The original value was not stored for some older entries, so their current amount is shown as the submitted amount.</p>
      )}

      <h3 className="opr-section-title">Approval stages</h3>
      <div className="opr-stages">{d.amounts.stages.map((s) => <StageCard key={s.level} s={s} />)}</div>

      {d.amounts.edit_history.length > 0 && (
        <>
          <h3 className="opr-section-title">Total amount edits</h3>
          <DataTable rowKey={(r) => r.edited_date}
            columns={[
              { key: 'edited_date_ist', title: 'When (IST)' },
              { key: 'edited_by_role', title: 'By', render: (r) => `${r.edited_by_name || r.edited_by} (${r.edited_by_role})` },
              { key: 'old_total', title: 'From', num: true, render: (r) => inr(r.old_total) },
              { key: 'new_total', title: 'To', num: true, render: (r) => inr(r.new_total) },
            ]}
            rows={d.amounts.edit_history} />
        </>
      )}

      <h3 className="opr-section-title">Expense entries ({d.entries.length})</h3>
      <DataTable rowKey={(r) => r.id} columns={cols} rows={d.entries} />

      <h3 className="opr-section-title">History (Indian Standard Time)</h3>
      <Timeline events={d.timeline} source={d.timeline_source} />
    </div>
  );
}

export default function SubmissionDetail({ employeeId, month, onClose }) {
  const { loading, error, data } = useAsync(
    () => api(`/api/ope/submission/${encodeURIComponent(employeeId)}/detail?${qs({ month })}`),
    [employeeId, month],
  );
  return (
    <Modal wide title="Submission details" subtitle={`${employeeId} · ${month}`} onClose={onClose}>
      {loading && <Spinner />}
      {error && <Alert>{error}</Alert>}
      {data && <DetailBody d={data} />}
    </Modal>
  );
}

