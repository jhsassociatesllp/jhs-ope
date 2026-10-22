// Thin fetch wrapper. The JWT is the one the existing portal already stores after
// login; every authorisation decision is still made by the FastAPI backend.
export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

function detailOf(data, fallback) {
  const d = data && data.detail;
  if (typeof d === 'string') return d;
  if (Array.isArray(d)) return d.map((x) => x.msg || JSON.stringify(x)).join('; ');
  return fallback;
}

async function request(path, { method = 'GET', json, form, signal } = {}) {
  const headers = {};
  const token = localStorage.getItem('access_token');
  if (token) headers.Authorization = `Bearer ${token}`;
  let body;
  if (json !== undefined) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(json);
  } else if (form) {
    body = form;
  }
  let res;
  try {
    res = await fetch(path, { method, headers, body, signal });
  } catch (e) {
    if (e.name === 'AbortError') throw e;
    throw new ApiError('Network error. Please check your connection and try again.', 0);
  }
  if (res.status === 401) {
    window.location.href = 'login.html';
    throw new ApiError('Your session has expired. Please log in again.', 401);
  }
  return res;
}

export async function api(path, opts = {}) {
  const res = await request(path, opts);
  let data = null;
  try {
    data = await res.json();
  } catch (_) {
    /* empty body */
  }
  if (!res.ok) throw new ApiError(detailOf(data, `Request failed (${res.status})`), res.status);
  return data;
}

export async function download(path, fallbackName) {
  const res = await request(path);
  if (!res.ok) {
    let data = null;
    try {
      data = await res.json();
    } catch (_) {
      /* not json */
    }
    throw new ApiError(detailOf(data, `Download failed (${res.status})`), res.status);
  }
  const cd = res.headers.get('Content-Disposition') || '';
  const m = /filename="?([^";]+)"?/i.exec(cd);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = m ? m[1] : fallbackName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export const qs = (obj) => {
  const p = new URLSearchParams();
  Object.entries(obj).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') p.append(k, v);
  });
  return p.toString();
};
