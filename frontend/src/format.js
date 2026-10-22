const inrFmt = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', minimumFractionDigits: 2 });

// null/undefined means "no decision yet" - never show it as an approved zero.
export function inr(value, empty = 'Not reviewed yet') {
  if (value === null || value === undefined || value === '') return empty;
  const n = Number(value);
  return Number.isFinite(n) ? inrFmt.format(n) : empty;
}

export const STATUS = {
  approved: { label: 'Approved', tone: 'ok' },
  pending: { label: 'Pending', tone: 'warn' },
  rejected: { label: 'Rejected', tone: 'bad' },
  partial: { label: 'Partially approved', tone: 'mid' },
  not_reached: { label: 'Not reached', tone: 'muted' },
  active: { label: 'Active', tone: 'ok' },
  used: { label: 'Used', tone: 'muted' },
  revoked: { label: 'Revoked', tone: 'bad' },
};

export const ACTION_LABEL = {
  submitted: 'Submitted',
  resubmitted: 'Resubmitted',
  approved: 'Approved',
  rejected: 'Rejected',
  reopened: 'Resubmission allowed (reopened)',
  reopen_revoked: 'Reopen permission revoked',
  amount_edited: 'Amount edited',
  entry_updated: 'Entry edited',
  entry_deleted: 'Entry deleted',
  fixed_amount_assigned: 'Fixed amount assigned',
  upload_activated: 'Monthly upload activated',
  report_exported: 'Report exported',
};

export const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July',
  'August', 'September', 'October', 'November', 'December'];

export function monthLabel(startMonth, startYear) {
  const m2 = startMonth % 12;
  const y2 = startMonth === 12 ? startYear + 1 : startYear;
  return `${MONTHS[startMonth - 1]} ${startYear} - ${MONTHS[m2]} ${y2}`;
}
