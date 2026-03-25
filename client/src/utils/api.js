/**
 * CartPath — API Client
 *
 * Thin wrapper around fetch with:
 * - credentials: 'include' for cookie-based auth
 * - Auto-refresh on 401: retries the request after refreshing the access token
 */

let isRefreshing = false;
let refreshPromise = null;

async function refreshToken() {
  if (isRefreshing) return refreshPromise;
  isRefreshing = true;
  refreshPromise = fetch('/api/auth/refresh', {
    method: 'POST',
    credentials: 'include',
  }).then((resp) => {
    isRefreshing = false;
    return resp.ok;
  }).catch(() => {
    isRefreshing = false;
    return false;
  });
  return refreshPromise;
}

export async function apiFetch(url, options = {}) {
  const opts = {
    ...options,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  };

  let resp = await fetch(url, opts);

  // If 401, try refreshing the token and retry once
  if (resp.status === 401 && !options._retried) {
    const refreshed = await refreshToken();
    if (refreshed) {
      resp = await fetch(url, { ...opts, _retried: true });
    }
  }

  return resp;
}
