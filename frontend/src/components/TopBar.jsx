import React, { useEffect, useState } from 'react';
import { api } from '../api.js';

const IST_DATE = new Intl.DateTimeFormat('en-IN', {
  timeZone: 'Asia/Kolkata', weekday: 'short', day: '2-digit', month: 'short', year: 'numeric',
});

function roleChips(r) {
  const chips = [];
  if (r.is_admin) chips.push(['admin', 'Admin']);
  if (r.is_hr) chips.push(['hr', 'HR']);
  if (r.is_partner) chips.push(['partner', 'Partner']);
  if (r.is_manager) chips.push(['manager', 'Reporting Manager']);
  if (!chips.length) chips.push(['employee', 'Employee']);
  return chips;
}

// Slim header above the page content: where you are, today's date (IST), who is signed in.
export default function TopBar({ admin }) {
  const code = (localStorage.getItem('employee_code') || '').toUpperCase();
  const [roles, setRoles] = useState(null);
  const [name, setName] = useState(localStorage.getItem('employee_name') || '');
  const [today, setToday] = useState(IST_DATE.format(new Date()));

  useEffect(() => {
    api('/api/ope/my-roles').then(setRoles, () => {});
    const t = setInterval(() => setToday(IST_DATE.format(new Date())), 60000);
    return () => clearInterval(t);
  }, []);

  // the employee name is filled into the page by the existing script after login
  useEffect(() => {
    if (name) return undefined;
    let tries = 0;
    const t = setInterval(() => {
      const el = document.getElementById('empName');
      const v = el && el.textContent.trim();
      if (v && v !== '-') { setName(v); clearInterval(t); }
      if (++tries > 20) clearInterval(t);
    }, 600);
    return () => clearInterval(t);
  }, [name]);

  const shown = name || code;
  const hour = Number(new Intl.DateTimeFormat('en-IN', { timeZone: 'Asia/Kolkata', hour: '2-digit', hour12: false }).format(new Date())) % 24;
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';
  const first = (name || '').split(' ')[0];
  return (
    <div className="opr-topbar">
      <div>
        <h2>{first ? <>{greeting}, <em>{first}</em></> : (admin ? 'Admin Control Panel' : 'JHS OPE')}</h2>
        <p>{admin ? 'Admin Control Panel · payroll expense control dashboard' : 'JHS OPE · payroll expense (OPE) portal'}</p>
      </div>
      <div className="opr-tb-right">
        <span className="opr-chip-date">{today}</span>
        {(roles ? roleChips(roles) : []).map(([k, label]) => (
          <span key={k} className={`opr-chip-role opr-r-${k}`}>{label}</span>
        ))}
        <span className="opr-avatar">
          <b>{(shown || '?').trim().charAt(0).toUpperCase()}</b>
          <span>{shown}<small>{code}</small></span>
        </span>
      </div>
    </div>
  );
}
