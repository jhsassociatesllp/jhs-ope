import React, { useState } from 'react';
import { api, download, qs } from '../api.js';
import { inr } from '../format.js';
import MonthSelect from '../components/MonthSelect.jsx';
import { Alert, Button, Card, Spinner, Stat, useAsync } from '../components/ui.jsx';

const GROUPS = [['partner', 'Partner wise'], ['manager', 'Reporting Manager wise']];
const STATUSES = [['', 'All statuses'], ['approved', 'Approved'], ['pending', 'Pending'], ['rejected', 'Rejected'], ['partial', 'Partially approved']];

export default function TeamReports() {
  const [groupBy, setGroupBy] = useState('partner');
  const [partner, setPartner] = useState('');
  const [manager, setManager] = useState('');
  const [month, setMonth] = useState('');       // '' = all months
  const [status, setStatus] = useState('');
  const [busy, setBusy] = useState('');
  const [err, setErr] = useState('');
  const [note, setNote] = useState('');

  // the Reporting Manager list follows the chosen Partner
  const options = useAsync(() => api(`/api/admin/team-report/options?${qs({ group_by: groupBy, partner })}`), [groupBy, partner]);
  const pickPartner = (v) => { setPartner(v); setManager(''); };
  const filters = { group_by: groupBy, partner, manager, month, status };
  const preview = useAsync(
    () => api(`/api/admin/team-report/preview?${qs(filters)}`),
    [groupBy, partner, manager, month, status],
  );

  const run = async (kind) => {
    setBusy(kind); setErr(''); setNote('');
    try {
      const months = (preview.data && preview.data.ticket_months) || [];
      const parts = months.reduce((n, m) => n + m.parts, 0);
      if (kind === 'tickets' && !month && parts > 1) {
        // All months: download month by month (and part by part for very big months)
        let done = 0;
        for (const m of months) {
          for (let part = 1; part <= m.parts; part++) {
            done += 1;
            setNote(`Downloading ZIP ${done} of ${parts} (${m.month})…`);
            await download(`/api/admin/team-report/tickets?${qs({ ...filters, month: m.month, part })}`,
              `OPE_tickets_${m.month}${part > 1 ? `_part${part}` : ''}.zip`);
            await new Promise((r) => setTimeout(r, 600));
          }
        }
        setNote(`${parts} month-wise ZIP files downloaded (${p.tickets} tickets).`);
        return;
      }
      await download(`/api/admin/team-report/${kind}?${qs(filters)}`,
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
              <span>Partner</span>
              <select value={partner} onChange={(e) => pickPartner(e.target.value)}>
                <option value="">All partners</option>
                {(options.data ? options.data.partners : []).map((x) => (
                  <option key={x.code} value={x.code}>{x.name} ({x.code}) · {x.employees} employees</option>
                ))}
              </select>
            </label>
            <label className="opr-field opr-grow">
              <span>Reporting Manager</span>
              <select value={manager} onChange={(e) => setManager(e.target.value)}>
                <option value="">{partner ? 'All reporting managers under this partner' : 'All reporting managers'}</option>
                {(options.data ? options.data.managers : []).map((x) => (
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
            {!month && p.ticket_months && p.ticket_months.reduce((n, m) => n + m.parts, 0) > 1 && (
              <Alert kind="warn">
                {p.tickets} tickets across {p.ticket_months.length} months: they will download as separate month-wise ZIP files
                (max {p.ticket_limit} tickets per ZIP). Allow multiple downloads if the browser asks.
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
