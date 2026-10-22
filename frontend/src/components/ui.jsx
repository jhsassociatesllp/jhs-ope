import React, { useEffect, useRef, useState } from 'react';
import { STATUS } from '../format.js';

export function Badge({ status, children }) {
  const s = STATUS[status] || { label: status, tone: 'muted' };
  return <span className={`opr-badge opr-tone-${s.tone}`}>{children || s.label}</span>;
}

export function Spinner({ label = 'Loading…' }) {
  return (
    <div className="opr-center" role="status" aria-live="polite">
      <span className="opr-spin" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}

export function Alert({ kind = 'error', children, onClose }) {
  if (!children) return null;
  return (
    <div className={`opr-alert opr-alert-${kind}`} role={kind === 'error' ? 'alert' : 'status'}>
      <div>{children}</div>
      {onClose && (
        <button type="button" className="opr-x" onClick={onClose} aria-label="Dismiss">×</button>
      )}
    </div>
  );
}

export function Empty({ title = 'Nothing to show', children }) {
  return (
    <div className="opr-empty">
      <strong>{title}</strong>
      {children && <p>{children}</p>}
    </div>
  );
}

export function Button({ variant = 'primary', busy, disabled, children, className = '', ...rest }) {
  return (
    <button
      type="button"
      className={`opr-btn opr-btn-${variant} ${className}`}
      disabled={disabled || busy}
      aria-busy={busy ? 'true' : undefined}
      {...rest}
    >
      {busy && <span className="opr-spin opr-spin-sm" aria-hidden="true" />}
      {children}
    </button>
  );
}

export function Card({ title, actions, children, className = '' }) {
  return (
    <section className={`opr-card ${className}`}>
      {(title || actions) && (
        <header className="opr-card-head">
          {title && <h3>{title}</h3>}
          {actions && <div className="opr-actions">{actions}</div>}
        </header>
      )}
      <div className="opr-card-body">{children}</div>
    </section>
  );
}

export function Stat({ label, value, tone }) {
  return (
    <div className={`opr-stat ${tone ? `opr-tone-${tone}` : ''}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export function Modal({ title, subtitle, onClose, children, wide, footer }) {
  const ref = useRef(null);
  useEffect(() => {
    const prev = document.activeElement;
    const onKey = (e) => e.key === 'Escape' && onClose();
    document.addEventListener('keydown', onKey);
    ref.current && ref.current.focus();
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = overflow;
      prev && prev.focus && prev.focus();
    };
  }, [onClose]);
  return (
    <div className="opr-overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={`opr-modal ${wide ? 'opr-modal-wide' : ''}`} role="dialog" aria-modal="true"
        aria-label={title} tabIndex={-1} ref={ref}>
        <header className="opr-modal-head">
          <div>
            <h2>{title}</h2>
            {subtitle && <p>{subtitle}</p>}
          </div>
          <button type="button" className="opr-x" onClick={onClose} aria-label="Close">×</button>
        </header>
        <div className="opr-modal-body">{children}</div>
        {footer && <footer className="opr-modal-foot">{footer}</footer>}
      </div>
    </div>
  );
}

// Confirmation for high-impact actions; optionally collects a mandatory reason.
export function ConfirmDialog({ title, message, confirmLabel = 'Confirm', danger, needReason,
  reasonLabel = 'Reason', onConfirm, onCancel }) {
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const go = async () => {
    if (needReason && reason.trim().length < 3) {
      setErr('Please enter a reason (at least 3 characters).');
      return;
    }
    setBusy(true);
    setErr('');
    try {
      await onConfirm(reason.trim());
    } catch (e) {
      setErr(e.message || 'Something went wrong');
      setBusy(false);
    }
  };
  return (
    <Modal title={title} onClose={busy ? () => {} : onCancel}
      footer={(
        <>
          <Button variant="ghost" onClick={onCancel} disabled={busy}>Cancel</Button>
          <Button variant={danger ? 'danger' : 'primary'} onClick={go} busy={busy}>{confirmLabel}</Button>
        </>
      )}>
      <div className="opr-stack">
        <div>{message}</div>
        {needReason && (
          <label className="opr-field">
            <span>{reasonLabel}</span>
            <textarea rows={3} maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)} />
          </label>
        )}
        <Alert>{err}</Alert>
      </div>
    </Modal>
  );
}

export function Pagination({ page, pageSize, total, onPage }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (total <= pageSize) return null;
  return (
    <nav className="opr-pager" aria-label="Pagination">
      <Button variant="ghost" disabled={page <= 1} onClick={() => onPage(page - 1)}>‹ Prev</Button>
      <span>Page {page} of {pages} · {total} records</span>
      <Button variant="ghost" disabled={page >= pages} onClick={() => onPage(page + 1)}>Next ›</Button>
    </nav>
  );
}

// Table that turns into stacked cards on phones (cells carry data-label).
export function DataTable({ columns, rows, rowKey, onRowClick, empty }) {
  if (!rows.length) return empty || <Empty />;
  return (
    <div className="opr-table-wrap">
      <table className="opr-table">
        <thead>
          <tr>{columns.map((c) => <th key={c.key} className={c.num ? 'opr-num' : ''}>{c.title}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={rowKey(r)} onClick={onRowClick ? () => onRowClick(r) : undefined}
              className={onRowClick ? 'opr-click' : ''}>
              {columns.map((c) => (
                <td key={c.key} data-label={c.title} className={c.num ? 'opr-num' : ''}>
                  {c.render ? c.render(r) : r[c.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Month dropdown fed by the months that exist in the data.
export function useAsync(fn, deps) {
  const [state, setState] = useState({ loading: true, error: '', data: null });
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let live = true;
    setState((s) => ({ ...s, loading: true, error: '' }));
    fn().then(
      (data) => live && setState({ loading: false, error: '', data }),
      (e) => live && e.name !== 'AbortError' && setState({ loading: false, error: e.message, data: null }),
    );
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);
  return { ...state, reload: () => setTick((t) => t + 1) };
}
