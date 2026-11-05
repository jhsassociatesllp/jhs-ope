import React from 'react';
import { api } from '../api.js';
import { Alert, useAsync } from './ui.jsx';

// Dropdown of payroll months that exist in the data (HR/Admin only endpoint).
export default function MonthSelect({ value, onChange, label = 'Payroll month', allowAll = false }) {
  const { loading, error, data } = useAsync(() => api('/api/ope/months'), []);
  const months = data ? [...data.months].reverse() : [];
  React.useEffect(() => {
    if (!allowAll && !value && months.length) onChange(months[0]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);
  return (
    <label className="opr-field">
      <span>{label}</span>
      <select value={value || ''} onChange={(e) => onChange(e.target.value)} disabled={loading}>
        {loading && <option value="">Loading…</option>}
        {allowAll && !loading && <option value="">All months</option>}
        {!allowAll && !loading && !months.length && <option value="">No months yet</option>}
        {months.map((m) => <option key={m} value={m}>{m}</option>)}
      </select>
      {error && <Alert>{error}</Alert>}
    </label>
  );
}
