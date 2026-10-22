import React, { useEffect, useState } from 'react';
import { api, qs } from '../api.js';
import { inr } from '../format.js';
import { Alert } from './ui.jsx';

// Sits at the top of the OPE form. Follows the existing month <select> and tells
// the employee, before they fill anything, whether the month is locked, fixed or
// reopened. The server enforces all of this regardless of what is shown here.
export default function LockBanner() {
  const [month, setMonth] = useState('');
  const [state, setState] = useState(null);
  const [error, setError] = useState('');
  const [restriction, setRestriction] = useState(null);

  // restricted employees are told straight after login, before choosing any month
  useEffect(() => {
    api('/api/ope/my-restriction').then((r) => r.restricted && setRestriction(r), () => {});
  }, []);

  // lock the month picker and the whole entry table; the server refuses any save/submit anyway
  useEffect(() => {
    if (!restriction) return undefined;
    const targets = [...document.querySelectorAll('#opeSection .month-selection-card, #opeSection .entry-form-card')];
    targets.forEach((el) => {
      el.classList.add('opr-locked');
      el.setAttribute('inert', '');
      el.setAttribute('aria-disabled', 'true');
    });
    return () => targets.forEach((el) => {
      el.classList.remove('opr-locked');
      el.removeAttribute('inert');
      el.removeAttribute('aria-disabled');
    });
  }, [restriction]);

  useEffect(() => {
    const sel = document.getElementById('monthRange');
    if (!sel) return undefined;
    const on = () => setMonth(sel.value || '');
    sel.addEventListener('change', on);
    on();
    return () => sel.removeEventListener('change', on);
  }, []);

  useEffect(() => {
    if (!month) { setState(null); return undefined; }
    let live = true;
    setError('');
    api(`/api/ope/access/status?${qs({ month })}`).then(
      (s) => live && setState(s),
      (e) => live && (setState(null), setError(e.message)),
    );
    return () => { live = false; };
  }, [month]);

  // the form resets its month dropdown after a successful submit; follow it
  useEffect(() => {
    const sync = () => setMonth((document.getElementById('monthRange') || {}).value || '');
    window.addEventListener('ope:submitted', sync);
    return () => window.removeEventListener('ope:submitted', sync);
  }, []);

  if (restriction) {
    return (
      <div className="opr-root opr-banner">
        <Alert kind="warn">{restriction.message}</Alert>
      </div>
    );
  }
  if (error) return <div className="opr-root opr-banner"><Alert>{error}</Alert></div>;
  if (!state) return null;
  const items = [];
  if (state.locked) {
    items.push(<Alert key="l" kind={state.reason === 'fixed_amount' ? 'info' : 'warn'}>{state.message}</Alert>);
  } else if (state.reopen_permitted) {
    items.push(<Alert key="r" kind="success">HR has allowed you to resubmit {state.payroll_month}. You can submit once more; your earlier entries are kept.</Alert>);
  }
  if (state.policy_active && state.eligible && state.ope_limit != null && !state.locked) {
    items.push(<Alert key="p" kind="info">Your OPE limit for {state.payroll_month} is <strong>{inr(state.ope_limit)}</strong> (set by HR for this month).</Alert>);
  }
  if (!items.length) return null;
  return <div className="opr-root opr-banner opr-stack">{items}</div>;
}
