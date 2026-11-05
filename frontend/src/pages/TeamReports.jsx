import React, { useEffect, useState } from 'react';
import { api, download, qs } from '../api.js';
import { inr } from '../format.js';
import MonthSelect from '../components/MonthSelect.jsx';
import { Alert, Button, Card, Spinner, Stat, useAsync } from '../components/ui.jsx';

const GROUPS = [['partner', 'Partner wise'], ['manager', 'Reporting Manager wise']];
const STATUSES = [['', 'All statuses'], ['approved', 'Approved'], ['pending', 'Pending'], ['rejected', 'Rejected'], ['partial', 'Partially approved']];

export default function TeamReports() {
  const [groupBy, setGroupBy] = useState('partner');
  const [person, setPerson] = useState('');
  const [month, setMonth] = useState('');       // '' = all months
  const [status, setStatus] = useState('');
  const [busy, setBusy] = useState('');
  const [err, setErr] = useState('');
  const [note, setNote] = useState('');

  const options = useAsync(() => api(`/api/admin/team-report/options?${qs({ group_by: groupBy })}`), [groupBy]);
  useEffect(() => { setPerson(''); }, [groupBy]);
  const preview = useAsync(
    () => api(`/api/admin/team-report/preview?${qs({ group_by: groupBy, person, month, status })}`),
    [groupBy, person, month, status],
  );

  const run = async (kind) => {
    setBusy(kind); setErr(''); setNote('');
    try {
      await download(`/api/admin/team-report/${kind}?${qs({ group_by: groupBy, person, month, status })}`,
        kind === 'excel' ? 'OPE_report.xlsx' : 'OPE_tickets.zip');
      setNote(kind === 'excel' ? 'Excel report downloaded.' : 'Supporting tickets downloaded.');
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy('');
    }
  };

  const p = preview.data;
  const who = groupBy === 'partner' ? 'partner' : 'reporting manager';
  return (
    <div className="opr-root opr-stack">
      <div>
        <h1 className="opr-page-title">Team Reports</h1>
        <p className="opr-muted" style={{ margin: 0 }}>
          Download the OPE data grouped by Partner or Reporting Manager, with the supporting entry details and ticket PDFs.
        </p>
      </div>

      <Card title="1. Choose what to download">
        <div className="opr-stack">
          <div className="opr-chips" role="group" aria-label="Group by">
            {GROUPS.map(([v, label]) => (
              <button key={v} type="button" className="opr-chip" aria-pressed={groupBy === v} onClick={() => setGroupBy(v)}>{label}</button>
            ))}
          </div>
          <div className="opr-row">
            <label className="opr-field opr-grow">
              <span>{groupBy === 'partner' ? 'Partner' : 'Reporting Manager'}</span>
              <select value={person} onChange={(e) => setPerson(e.target.value)} disabled={options.loading}>
                <option value="">All {groupBy === 'partner' ? 'partners' : 'reporting managers'}</option>
                {(options.data ? options.data.people : []).map((x) => (
                  <option key={x.code} value={x.code}>{x.name} ({x.code}) · {x.employees} employees</option>
                ))}
              </select>
            </label>
            <div className="opr-grow">
              <MonthSelect value={month} onChange={setMonth} label="Payroll month" allowAll />
            </div>
            <label className="opr-field">
              <span>Status</span>
              <select value={status} onChange={(e) => setStatus(e.target.value)}>
                {STATUSES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </label>
          </div>
          {options.error && <Alert>{options.error}</Alert>}
        </div>
      </Card>

      <Card title="2. What you will get">
        {preview.loading && !p && <Spinner label="Counting…" />}
        {preview.error && <Alert>{preview.error}</Alert>}
        {p && (
          <div className="opr-stack">
            <div className="opr-stats">
              <Stat label={groupBy === 'partner' ? 'Partners' : 'Reporting Managers'} value={p.groups} />
              <Stat label="Employees" value={p.employees} tone="ok" />
              <Stat label="Employee-month records" value={p.records} tone="mid" />
              <Stat label="Expense entries" value={p.entries} tone="warn" />
              <Stat label="Ticket PDFs" value={p.tickets} tone="bad" />
              <Stat label="Submitted amount" value={inr(p.submitted_amount)} />
            </div>
            {p.records === 0 && <Alert kind="warn">No records match these filters.</Alert>}
            {p.tickets > p.ticket_limit && (
              <Alert kind="warn">
                {p.tickets} tickets match, but one ZIP holds at most {p.ticket_limit}. Pick one {who} or one month to get them all.
              </Alert>
            )}
          </div>
        )}
      </Card>

      <Card title="3. Download">
        <div className="opr-stack">
          <div className="opr-actions">
            <Button onClick={() => run('excel')} busy={busy === 'excel'} disabled={!p || p.records === 0 || !!busy}>
              Download Excel report
            </Button>
            <Button variant="ok" onClick={() => run('tickets')} busy={busy === 'tickets'} disabled={!p || p.tickets === 0 || !!busy}>
              Download supporting tickets (ZIP)
            </Button>
          </div>
          <ul className="opr-muted opr-small" style={{ margin: 0, paddingLeft: 18 }}>
            <li><strong>Excel</strong> has three sheets: <em>Summary</em> (per {who}), <em>Employee Months</em> (limit, submitted and approved amounts,
              status) and <em>Entries (supporting)</em> (every expense entry with approver, remarks and the ticket file name).</li>
            <li><strong>ZIP</strong> holds the ticket PDFs in folders <em>{groupBy === 'partner' ? 'Partner' : 'Manager'} / Employee / Month</em>.
              Each file name matches the “Ticket file (in ZIP)” column of the Excel.</li>
            <li>Times are in IST. Rejected entries are included and marked Rejected.</li>
          </ul>
          <Alert>{err}</Alert>
          <Alert kind="success" onClose={() => setNote('')}>{note}</Alert>
        </div>
      </Card>
    </div>
  );
}
