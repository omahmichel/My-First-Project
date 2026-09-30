// Deliberately excludes error messages, stacks, URLs, queries and form contents.
export function installPlatformErrorReporting() {
  let lastSent = 0;
  function report(kind) {
    try {
      const now = Date.now();
      if (now - lastSent < 30000) return;
      const token = window.localStorage.getItem('stockflow_access_token');
      if (!token) return;
      lastSent = now;
      const segment = window.location.pathname.split('/')[1];
      const area = ['platform-admin','app','businesses','onboarding'].includes(segment) ? segment : ['login','verify-login','register','verify-registration'].includes(segment) ? 'authentication' : 'public';
      const base = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000/api';
      void fetch(`${base.replace(/\/$/, '')}/platform-events/client-error/`, {
        method:'POST', headers:{'Content-Type':'application/json',Authorization:`Bearer ${token}`},
        body:JSON.stringify({kind,area}),
      }).catch(() => {});
    } catch { /* Error reporting must never crash the application. */ }
  }
  const onError = event => { if (event instanceof ErrorEvent) report('javascript_error'); };
  const onRejection = () => report('unhandled_rejection');
  window.addEventListener('error',onError);
  window.addEventListener('unhandledrejection',onRejection);
  return () => {window.removeEventListener('error',onError);window.removeEventListener('unhandledrejection',onRejection);};
}
