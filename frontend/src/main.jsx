import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';
import { api } from './api.js';
import AccessControl from './pages/AccessControl.jsx';
import HrReport from './pages/HrReport.jsx';
import MonthlyUploads from './pages/MonthlyUploads.jsx';
import PayrollMonths from './pages/PayrollMonths.jsx';
import LockBanner from './components/LockBanner.jsx';
import TopBar from './components/TopBar.jsx';
import SubmissionDetail from './components/SubmissionDetail.jsx';

// Modal host: the existing (non-React) pages call OPEReact.openDetail(emp, month).
function DetailHost() {
  const [req, setReq] = useState(null);
  useEffect(() => {
    const on = (e) => setReq(e.detail);
    window.addEventListener('ope:open-detail', on);
    return () => window.removeEventListener('ope:open-detail', on);
  }, []);
  if (!req) return null;
  return <SubmissionDetail employeeId={req.employeeId} month={req.month} onClose={() => setReq(null)} />;
}

const PAGES = {
  'hr-report': HrReport,
  'access-control': AccessControl,
  'monthly-uploads': MonthlyUploads,
  'payroll-months': PayrollMonths,
  'lock-banner': LockBanner,
};

function mount(selector) {
  document.querySelectorAll(selector).forEach((el) => {
    if (el.dataset.opeMounted) return;
    const Page = PAGES[el.dataset.opeReact];
    if (!Page) return;
    el.dataset.opeMounted = '1';
    createRoot(el).render(<Page />);
  });
}

// ---- integration with the existing sidebar layout ----------------------------
function showSection(nav, sectionId) {
  document.querySelectorAll('.nav-item').forEach((i) => i.classList.remove('active'));
  nav.classList.add('active');
  document.querySelectorAll('.content-section').forEach((s) => {
    s.classList.remove('active');
    s.style.display = 'none';
  });
  const sec = document.getElementById(sectionId);
  if (sec) {
    sec.classList.add('active');
    sec.style.display = 'block';
  }
  const sidebar = document.querySelector('.sidebar');
  if (sidebar) sidebar.classList.remove('mobile-active');
}

async function setupPortal() {
  const navReports = document.getElementById('navReports');
  const navAccess = document.getElementById('navAccess');
  if (!navReports && !navAccess) return;
  try {
    const roles = await api('/api/ope/my-roles');
    if (!(roles.is_hr || roles.is_admin)) return;
    [[navReports, 'reportsSection'], [navAccess, 'accessSection']].forEach(([nav, sec]) => {
      if (!nav) return;
      nav.style.display = 'flex';
      nav.addEventListener('click', (e) => { e.preventDefault(); showSection(nav, sec); });
    });
    mount('[data-ope-role="hr"]');
  } catch (_) {
    /* roles unavailable: new HR/Admin screens simply stay hidden */
  }
}

function boot() {
  const host = document.createElement('div');
  host.className = 'opr-root';
  document.body.appendChild(host);
  createRoot(host).render(<DetailHost />);

  const main = document.querySelector('.main-content');
  if (main && localStorage.getItem('access_token')) {
    const bar = document.createElement('div');
    main.insertBefore(bar, main.firstChild);
    createRoot(bar).render(<TopBar admin={/admin\.html/i.test(window.location.pathname)} />);
  }

  window.OPEReact = {
    openDetail(employeeId, month) {
      window.dispatchEvent(new CustomEvent('ope:open-detail', { detail: { employeeId, month } }));
    },
    notifySubmitted() {
      window.dispatchEvent(new Event('ope:submitted'));
    },
  };

  // screens everyone may see (employee banner) and the admin console tabs;
  // HR-only portal sections carry data-ope-role="hr" and mount after the role check
  mount('[data-ope-react]:not([data-ope-role])');
  setupPortal();
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
else boot();
