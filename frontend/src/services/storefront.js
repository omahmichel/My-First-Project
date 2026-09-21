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

// Resolve StockFlow media against the same API used by the public catalogue.
// External photo/CDN URLs are left untouched.
export function resolveShopMediaUrl(value, apiBase = BASE, pageUrl = window.location.href) {
  if (!value) return '';
  try {
    const page = new URL(pageUrl);
    const api = new URL(apiBase.replace(/\/$/, '') + '/', page);
    const media = new URL(value, page);
    const route = media.pathname.match(/^\/api\/(product-(?:photos|videos)\/[0-9a-f-]{36}\/[0-9a-f-]{36}\/)$/i);
    const knownHost = [api.hostname, page.hostname, 'localhost', '127.0.0.1', '[::1]'].includes(media.hostname);
    if (route && knownHost && ['http:', 'https:'].includes(media.protocol)) {
      return new URL(route[1] + media.search, api).href;
    }
  } catch { /* Keep existing external URLs unchanged. */ }
  return value;
}
