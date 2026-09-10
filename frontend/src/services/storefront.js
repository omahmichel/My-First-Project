const BASE = (import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000/api').replace(/\/$/, '');

export async function publicShopRequest(slug, suffix = '', options = {}) {
  const response = await fetch(BASE + '/shops/' + encodeURIComponent(slug) + '/' + suffix, {
    ...options,
    credentials: 'omit',
    cache: 'no-store',
    headers: { Accept: 'application/json', ...(options.body ? { 'Content-Type': 'application/json' } : {}) },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const value = data.detail || Object.values(data)[0];
    const error = new Error(typeof value === 'string' ? value : Array.isArray(value) ? value.join(' ') : 'The shop request could not be completed.');
    error.status = response.status;
    throw error;
  }
  return data;
}

export const shopMoney = value => new Intl.NumberFormat('en-GH', { style: 'currency', currency: 'GHS' }).format(Number(value));
