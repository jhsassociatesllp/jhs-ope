import React, { useRef, useState } from 'react';
import { api, qs } from '../api.js';
import { MONTHS, inr, monthLabel } from '../format.js';
import { Alert, Badge, Button, Card, ConfirmDialog, DataTable, Empty, Modal, Pagination, Spinner, useAsync } from '../components/ui.jsx';

const YEARS = (() => {
  const y = new Date().getFullYear();
  return [y - 1, y, y + 1];
})();

function ValidationResult({ v, onActivate }) {
  const ok = v.validation === 'passed';
  return (
    <div className="opr-stack">
      <Alert kind={ok ? 'success' : 'error'}>
        {ok
          ? <>Validation passed for <strong>{v.payroll_month}</strong> (version {v.version}). Nothing changes until you activate it.</>
          : <>Validation failed. Nothing was activated and the previous active data (if any) is unchanged. Fix the file and upload again.</>}
      </Alert>
      <div className="opr-kv">
        <div><span>File</span><strong>{v.filename}</strong></div>
        <div><span>Rows read</span><strong>{v.row_count}</strong></div>
        <div><span>Valid rows</span><strong>{v.valid_rows}</strong></div>
        <div><span>Fixed-amount employees</span><strong>{v.fixed_count}</strong></div>
        <div><span>Errors</span><strong>{v.error_count}</strong></div>
        <div><span>Warnings</span><strong>{v.warning_count}</strong></div>
      </div>
      {v.header_error && <Alert>{v.header_error}</Alert>}
      {v.errors.length > 0 && (
        <>
          <h4 className="opr-section-title">Errors{v.error_count > v.errors.length ? ` (first ${v.errors.length} of ${v.error_count})` : ''}</h4>
          <DataTable rowKey={(e, i) => `${e.row}-${e.message}`} rows={v.errors}
            columns={[{ key: 'row', title: 'Row' }, { key: 'emp_id', title: 'EmpID' }, { key: 'message', title: 'Problem' }]} />
        </>
      )}
      {v.warnings.length > 0 && (
        <>
          <h4 className="opr-section-title">Warnings</h4>
          <DataTable rowKey={(e) => `${e.row}-${e.message}`} rows={v.warnings}
            columns={[{ key: 'row', title: 'Row' }, { key: 'emp_id', title: 'EmpID' }, { key: 'message', title: 'Note' }]} />
        </>
      )}
      {ok && v.preview && (
        <>
          <h4 className="opr-section-title">Preview (first {v.preview.length})</h4>
          <DataTable rowKey={(r) => r.emp_id} rows={v.preview}
            columns={[{ key: 'emp_id', title: 'EmpID' }, { key: 'emp_name', title: 'Name' },
              { key: 'ope_limit', title: 'OPE limit', num: true, render: (r) => inr(r.ope_limit) },
              { key: 'fixed_amount', title: 'Fixed amount', num: true, render: (r) => inr(r.fixed_amount, '—') }]} />
        </>
      )}
      {ok && !v.is_active && <div><Button variant="ok" onClick={() => onActivate(v)}>Activate this version…</Button></div>}
    </div>
  );
}

function VersionRows({ id, onClose }) {
  const [page, setPage] = useState(1);
  const [q, setQ] = useState('');
  const [query, setQuery] = useState('');
  const { loading, error, data } = useAsync(
    () => api(`/api/admin/monthly-upload/${id}?${qs({ page, page_size: 50, q: query })}`), [id, page, query]);
  return (
    <Modal wide title="Uploaded data" onClose={onClose}
      subtitle={data ? `${data.payroll_month} · version ${data.version} · ${data.uploaded_at_ist}` : ''}>
      <div className="opr-stack">
        <form className="opr-row" onSubmit={(e) => { e.preventDefault(); setPage(1); setQuery(q); }}>
          <label className="opr-field opr-grow"><span>Search</span><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="EmpID or name" /></label>
          <Button onClick={() => { setPage(1); setQuery(q); }}>Search</Button>
        </form>
        {error && <Alert>{error}</Alert>}
        {loading && <Spinner />}
        {data && !loading && (
          <>
            {data.errors.length > 0 && (
              <Alert>This version failed validation: {data.errors.slice(0, 3).map((e) => `row ${e.row}: ${e.message}`).join('; ')}…</Alert>
            )}
            <DataTable rowKey={(r) => r.emp_id} rows={data.rows}
              empty={<Empty title="No rows">{data.validation === 'failed' ? 'Failed uploads keep no rows.' : 'No rows match.'}</Empty>}
              columns={[{ key: 'emp_id', title: 'EmpID' }, { key: 'emp_name', title: 'Name' },
                { key: 'ope_limit', title: 'OPE limit', num: true, render: (r) => inr(r.ope_limit) },
                { key: 'fixed_amount', title: 'Fixed amount', num: true, render: (r) => inr(r.fixed_amount, '—') }]} />
            <Pagination page={page} pageSize={50} total={data.total_rows} onPage={setPage} />
          </>
        )}
      </div>
    </Modal>
  );
}

function History({ refreshKey, onActivate }) {
  const [month, setMonth] = useState(null);
  const [rowsOf, setRowsOf] = useState(null);
  const months = useAsync(() => api('/api/admin/monthly-upload/months'), [refreshKey]);
  const versions = useAsync(
    () => (month ? api(`/api/admin/monthly-upload/versions?${qs({ month })}`) : Promise.resolve(null)), [month, refreshKey]);
  return (
    <Card title="Month-wise upload history">
      {months.error && <Alert>{months.error}</Alert>}
      {months.loading && <Spinner />}
      {months.data && (
        <DataTable rowKey={(m) => m.payroll_month} rows={months.data.months}
          onRowClick={(m) => setMonth(m.payroll_month)}
          empty={<Empty title="No uploads yet">Upload the first monthly file above.</Empty>}
          columns={[
            { key: 'payroll_month', title: 'Payroll month', render: (m) => <strong>{m.payroll_month}</strong> },
            { key: 'active', title: 'Active version', render: (m) => (m.active ? <Badge status="active">{`v${m.active.version}`}</Badge> : <Badge status="pending">None active</Badge>) },
            { key: 'rows', title: 'Employees', num: true, render: (m) => m.active?.valid_rows ?? '—' },
            { key: 'versions', title: 'Versions', num: true },
            { key: 'go', title: '', render: (m) => <Button variant="ghost" className="opr-btn-sm" onClick={() => setMonth(m.payroll_month)}>Open</Button> },
          ]} />
      )}
      {month && (
        <Modal wide title={month} subtitle="All uploaded versions (newest first). The active version decides eligibility, limits and fixed amounts."
          onClose={() => setMonth(null)}>
          {versions.loading && <Spinner />}
          {versions.error && <Alert>{versions.error}</Alert>}
          {versions.data && (
            <DataTable rowKey={(v) => v.id} rows={versions.data.versions}
              columns={[
                { key: 'version', title: 'Version', render: (v) => <>v{v.version} {v.is_active && <Badge status="active">Active</Badge>}</> },
                { key: 'uploaded_at_ist', title: 'Uploaded (IST)' },
                { key: 'uploaded_by', title: 'By' },
                { key: 'filename', title: 'File' },
                { key: 'row_count', title: 'Rows', num: true },
                { key: 'fixed_count', title: 'Fixed', num: true },
                { key: 'validation', title: 'Validation', render: (v) => <Badge status={v.validation === 'passed' ? 'approved' : 'rejected'}>{v.validation === 'passed' ? 'Passed' : `Failed (${v.error_count || 1})`}</Badge> },
                { key: 'act', title: '', render: (v) => (
                  <div className="opr-actions">
                    <Button variant="ghost" className="opr-btn-sm" onClick={() => setRowsOf(v.id)}>View</Button>
                    {v.validation === 'passed' && !v.is_active && (
                      <Button variant="ok" className="opr-btn-sm"
                        onClick={() => onActivate({ ...v, expected: (versions.data.versions.find((x) => x.is_active) || {}).id || '' })}>
                        Activate
                      </Button>)}
                  </div>) },
              ]} />
          )}
        </Modal>
      )}
      {rowsOf && <VersionRows id={rowsOf} onClose={() => setRowsOf(null)} />}
    </Card>
  );
}

export default function MonthlyUploads() {
  const now = new Date();
  const [sm, setSm] = useState(now.getMonth() + 1);
  const [sy, setSy] = useState(now.getFullYear());
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [result, setResult] = useState(null);
  const [confirm, setConfirm] = useState(null);
  const [done, setDone] = useState('');
  const [tick, setTick] = useState(0);
  const input = useRef(null);

  const upload = async () => {
    if (!file) { setErr('Choose an .xlsx or .csv file first.'); return; }
    setBusy(true); setErr(''); setDone(''); setResult(null);
    try {
      const form = new FormData();
      form.append('file', file);
      form.append('start_month', String(sm));
      form.append('start_year', String(sy));
      setResult(await api('/api/admin/monthly-upload', { method: 'POST', form }));
      setTick((t) => t + 1);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  const doActivate = async () => {
    const out = await api(`/api/admin/monthly-upload/${confirm.id}/activate`, {
      method: 'POST', json: { confirm: true, expected_active_id: confirm.expected ?? '' } });
    setDone(`Version ${out.version} of ${out.payroll_month} is now active. ${out.fixed_submissions_created} fixed-amount record(s) sent to HR`
      + (out.fixed_skipped.length ? `; ${out.fixed_skipped.length} skipped (${out.fixed_skipped[0].emp_id}: ${out.fixed_skipped[0].reason}${out.fixed_skipped.length > 1 ? ', …' : ''}).` : '.'));
    setConfirm(null); setResult(null); setFile(null);
    if (input.current) input.current.value = '';
    setTick((t) => t + 1);
  };

  // activating from the preview needs the id of whatever is currently active
  const startActivate = async (v) => {
    if (v.expected !== undefined) { setConfirm(v); return; }
    try {
      const list = await api(`/api/admin/monthly-upload/versions?${qs({ month: v.payroll_month })}`);
      setConfirm({ ...v, expected: (list.versions.find((x) => x.is_active) || {}).id || '' });
    } catch (e) { setErr(e.message); }
  };

  return (
    <div className="opr-root opr-stack">
      <div>
        <h1 className="opr-page-title">Monthly Eligibility &amp; Limits</h1>
        <p className="opr-muted" style={{ margin: 0 }}>
          Upload each payroll month's employee list. The active version decides who may submit, their OPE limit and any fixed
          amount for that month only. Earlier months are never changed.
        </p>
      </div>

      <Card title="Upload a month">
        <div className="opr-stack">
          <Alert kind="info">
            Columns: <strong>EmpID</strong> (required), <strong>Emp Name</strong>, <strong>OPE LIMIT</strong> (required),
            <strong> Fixed OPE Amount</strong> (optional - employees with a value cannot fill the form; their fixed amount goes straight to HR).
            Accepted: .xlsx or .csv, max 5 MB.
          </Alert>
          <div className="opr-row">
            <label className="opr-field"><span>Starting month</span>
              <select value={sm} onChange={(e) => setSm(Number(e.target.value))}>
                {MONTHS.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
              </select></label>
            <label className="opr-field"><span>Year</span>
              <select value={sy} onChange={(e) => setSy(Number(e.target.value))}>
                {YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
              </select></label>
            <label className="opr-field opr-grow"><span>File</span>
              <input ref={input} type="file" accept=".xlsx,.csv" onChange={(e) => setFile(e.target.files[0] || null)} /></label>
          </div>
          <div className="opr-muted">Applies to payroll month: <strong>{monthLabel(sm, sy)}</strong></div>
          <div><Button onClick={upload} busy={busy} disabled={!file}>Validate &amp; upload</Button></div>
          <Alert>{err}</Alert>
          <Alert kind="success" onClose={() => setDone('')}>{done}</Alert>
          {result && <ValidationResult v={result} onActivate={startActivate} />}
        </div>
      </Card>

      <History refreshKey={tick} onActivate={startActivate} />

      {confirm && (
        <ConfirmDialog title="Activate this version?" confirmLabel="Activate" onConfirm={doActivate} onCancel={() => setConfirm(null)}
          message={<>
            <p>Version <strong>{confirm.version}</strong> of <strong>{confirm.payroll_month}</strong> ({confirm.valid_rows} employees,
              {' '}{confirm.fixed_count} fixed-amount) will replace the currently active version for this month.</p>
            <p>Employees not in the file will no longer be able to submit for this month. Fixed-amount employees are sent to HR now.
              The previous version stays in history.</p>
          </>} />
      )}
    </div>
  );
}
