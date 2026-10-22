import React, { useState } from 'react';
import { api } from '../api.js';
import { MONTHS, monthLabel } from '../format.js';
import { Alert, Badge, Button, Card, ConfirmDialog, DataTable, Empty, Modal, Spinner, useAsync } from '../components/ui.jsx';

const thisYear = new Date().getFullYear();
const YEARS = [thisYear - 1, thisYear, thisYear + 1, thisYear + 2];

const pad = (n) => String(n).padStart(2, '0');
function defaultDates(m, y) {
  const m2 = (m % 12) + 1;
  const y2 = m === 12 ? y + 1 : y;
  return [`${y}-${pad(m)}-21`, `${y2}-${pad(m2)}-20`];
}

function DateField({ label, value, onChange, hint }) {
  return (
    <label className="opr-field">
      <span>{label}</span>
      <input type="date" value={value || ''} onChange={(e) => onChange(e.target.value)} />
      {hint && <small className="opr-muted">{hint}</small>}
    </label>
  );
}

function EditDialog({ month, onClose, onSaved }) {
  const [f, setF] = useState({
    start: month.start, end: month.end,
    submit_deadline: month.submit_deadline || '', approve_deadline: month.approve_deadline || '',
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const set = (k) => (v) => setF((s) => ({ ...s, [k]: v }));
  const save = async () => {
    setBusy(true);
    setErr('');
    try {
      await api(`/api/admin/payroll-months/${month.key}`, {
        method: 'PUT',
        json: {
          start: f.start, end: f.end,
          submit_deadline: f.submit_deadline || null, approve_deadline: f.approve_deadline || null,
          clear_submit_deadline: !f.submit_deadline, clear_approve_deadline: !f.approve_deadline,
        },
      });
      onSaved(`${month.display} updated.`);
    } catch (e) {
      setErr(e.message);
      setBusy(false);
    }
  };
  return (
    <Modal title={`Edit ${month.display}`} onClose={onClose}
      footer={(<><Button variant="ghost" onClick={onClose} disabled={busy}>Cancel</Button>
        <Button onClick={save} busy={busy}>Save</Button></>)}>
      <div className="opr-stack">
        <div className="opr-row">
          <div className="opr-grow"><DateField label="Period starts" value={f.start} onChange={set('start')} /></div>
          <div className="opr-grow"><DateField label="Period ends" value={f.end} onChange={set('end')} /></div>
        </div>
        <DateField label="Employees should submit by (optional)" value={f.submit_deadline} onChange={set('submit_deadline')}
          hint="Leave empty to use the standard 7 days after the period ends." />
        <DateField label="Approvers should finish by (optional)" value={f.approve_deadline} onChange={set('approve_deadline')}
          hint="Leave empty to use the standard 5 days after the submit-by date." />
        <Alert>{err}</Alert>
      </div>
    </Modal>
  );
}

export default function PayrollMonths() {
  const { loading, error, data, reload } = useAsync(() => api('/api/admin/payroll-months'), []);
  const now = new Date();
  const [sm, setSm] = useState(now.getMonth() + 1);
  const [sy, setSy] = useState(now.getFullYear());
  const [dates, setDates] = useState(null);       // null = use the standard 21st-20th
  const [sub, setSub] = useState('');
  const [appr, setAppr] = useState('');
  const [visible, setVisible] = useState(true);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [note, setNote] = useState('');
  const [toggle, setToggle] = useState(null);
  const [edit, setEdit] = useState(null);

  const [dStart, dEnd] = dates || defaultDates(sm, sy);

  const add = async () => {
    setBusy(true); setErr(''); setNote('');
    try {
      const out = await api('/api/admin/payroll-months', {
        method: 'POST',
        json: {
          start_month: sm, start_year: sy, start: dStart, end: dEnd,
          submit_deadline: sub || null, approve_deadline: appr || null, visible,
        },
      });
      setNote(`${out.display} added and ${out.visible ? 'shown to employees' : 'kept hidden'}.`);
      setDates(null); setSub(''); setAppr('');
      reload();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  const doToggle = async () => {
    await api(`/api/admin/payroll-months/${toggle.key}`, { method: 'PUT', json: { visible: !toggle.visible } });
    setNote(`${toggle.display} is now ${toggle.visible ? 'hidden from' : 'shown to'} employees.`);
    setToggle(null);
    reload();
  };

  return (
    <div className="opr-root opr-stack">
      <div>
        <h1 className="opr-page-title">Payroll Months</h1>
        <p className="opr-muted" style={{ margin: 0 }}>
          Choose which payroll months employees see in the OPE “Month Range” list. Hidden months stay in history and
          reports, but employees can no longer start a new submission for them.
        </p>
      </div>

      <Card title="Add a payroll month">
        <div className="opr-stack">
          <div className="opr-row">
            <label className="opr-field"><span>Starting month</span>
              <select value={sm} onChange={(e) => { setSm(Number(e.target.value)); setDates(null); }}>
                {MONTHS.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
              </select></label>
            <label className="opr-field"><span>Year</span>
              <select value={sy} onChange={(e) => { setSy(Number(e.target.value)); setDates(null); }}>
                {YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
              </select></label>
            <div className="opr-grow"><DateField label="Period starts" value={dStart} onChange={(v) => setDates([v, dEnd])} /></div>
            <div className="opr-grow"><DateField label="Period ends" value={dEnd} onChange={(v) => setDates([dStart, v])} /></div>
          </div>
          <div className="opr-row">
            <div className="opr-grow"><DateField label="Submit-by date (optional)" value={sub} onChange={setSub} /></div>
            <div className="opr-grow"><DateField label="Approve-by date (optional)" value={appr} onChange={setAppr} /></div>
          </div>
          <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <input type="checkbox" checked={visible} onChange={(e) => setVisible(e.target.checked)} />
            Show to employees now
          </label>
          <div className="opr-muted">Will be added as: <strong>{monthLabel(sm, sy)}</strong> ({dStart} to {dEnd})</div>
          <div><Button onClick={add} busy={busy}>Add month</Button></div>
          <Alert>{err}</Alert>
          <Alert kind="success" onClose={() => setNote('')}>{note}</Alert>
        </div>
      </Card>

      <Card title="Months" actions={<Button variant="ghost" onClick={reload} disabled={loading}>Refresh</Button>}>
        {error && <Alert>{error}</Alert>}
        {loading && !data && <Spinner />}
        {data && (
          <DataTable rowKey={(m) => m.key} rows={data.months}
            empty={<Empty title="No months yet">Add the first payroll month above.</Empty>}
            columns={[
              { key: 'display', title: 'Payroll month', render: (m) => <strong>{m.display}</strong> },
              { key: 'start', title: 'Period', render: (m) => `${m.start} → ${m.end}` },
              { key: 'submit_deadline', title: 'Submit by', render: (m) => m.submit_deadline || 'Standard' },
              { key: 'approve_deadline', title: 'Approve by', render: (m) => m.approve_deadline || 'Standard' },
              { key: 'visible', title: 'Employees see it', render: (m) => (m.visible
                ? <Badge status="approved">Shown</Badge> : <Badge status="not_reached">Hidden</Badge>) },
              { key: 'act', title: '', render: (m) => (
                <div className="opr-actions">
                  <Button variant="ghost" className="opr-btn-sm" onClick={() => setEdit(m)}>Edit</Button>
                  <Button variant={m.visible ? 'danger' : 'ok'} className="opr-btn-sm" onClick={() => setToggle(m)}>
                    {m.visible ? 'Hide' : 'Show'}
                  </Button>
                </div>) },
            ]} />
        )}
      </Card>

      {toggle && (
        <ConfirmDialog
          title={toggle.visible ? 'Hide this month?' : 'Show this month?'}
          danger={toggle.visible}
          confirmLabel={toggle.visible ? 'Hide' : 'Show'}
          message={toggle.visible
            ? <>Employees will no longer see <strong>{toggle.display}</strong> in the month list and cannot start a new submission for it. Existing data, approvals and reports are not affected.</>
            : <>Employees will see <strong>{toggle.display}</strong> in the month list and can submit for it.</>}
          onConfirm={doToggle} onCancel={() => setToggle(null)} />
      )}
      {edit && <EditDialog month={edit} onClose={() => setEdit(null)}
        onSaved={(msg) => { setEdit(null); setNote(msg); reload(); }} />}
    </div>
  );
}
