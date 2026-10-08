import { useEffect, useRef, useState } from 'react';
import { MessageSquare, ShieldCheck } from 'lucide-react';
import { apiRequest } from '../../services/api';
import '../../styles/owner-sms.css';

const TYPES = [
  ['restock', 'Restocking', 'A text for each product restocked.'],
  ['adjustment', 'Stock adjustments', 'Manual corrections, damage and returns.'],
  ['low_stock', 'Low stock', 'When physical stock crosses the branch threshold.'],
  ['sale', 'Confirmed sales', 'One text per sale, including credit sales.'],
  ['security', 'Security alerts', 'Blocked business access and repeated failed sign-ins.'],
];
const STATES = { pending: 'Queued', sending: 'Submitting', sent: 'Accepted by SMS provider', unknown: 'Delivery unconfirmed', cancelled: 'Cancelled' };

export default function OwnerSmsPanel({ businessId }) {
  const [config, setConfig] = useState(null);
  const [phone, setPhone] = useState('');
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [recent, setRecent] = useState([]);
  const [retry, setRetry] = useState(0);
  const alive = useRef(true);
  const path = `/businesses/${businessId}/owner-sms/`;
  useEffect(() => {
    alive.current = true;
    const controller = new AbortController();
    setError('');
    apiRequest(path, { signal: controller.signal }).then(data => {
      if (!alive.current) return;
      setConfig(data); setPhone(data.phone || ''); setRecent(data.recent || []);
    }).catch(err => {
      if (alive.current && err.name !== 'AbortError') setError('Unable to load your SMS settings. Please try again.');
    });
    return () => { alive.current = false; controller.abort(); };
  }, [path, retry]);

  async function action(suffix, method, body, success) {
    if (busy) return;
    setBusy(true); setError(''); setNotice('');
    try {
      const data = await apiRequest(path + suffix, { method, body: JSON.stringify(body) });
      if (!alive.current) return;
      setConfig(data); setNotice(success);
      if (suffix === 'verify-code/') { setCode(''); setPhone(data.phone); }
    } catch (err) {
      if (alive.current) setError([400, 429].includes(err.status) ? err.message : 'Unable to complete this request. Please try again later.');
    } finally { if (alive.current) setBusy(false); }
  }

  return <section className='panel-card settings-section owner-sms-panel' id='owner-sms' aria-labelledby='owner-sms-title'>
    <header className='panel-heading'><MessageSquare size={24} aria-hidden='true' /><div><h2 id='owner-sms-title'>Owner SMS alerts</h2><p>Receive updates from every branch on your phone.</p></div></header>
    {error && <p role='alert' className='owner-sms-error'>{error}</p>}
    {notice && <p role='status' className='owner-sms-notice'>{notice}</p>}
    {!config ? <><p>SMS settings are loading or unavailable.</p><button type='button' onClick={() => setRetry(n => n + 1)}>Retry</button></> : <>
      {!config.smsAvailable && <p role='status'>SMS is temporarily unavailable. Your saved preferences are unchanged.</p>}
      <div className='owner-sms-verification'>
        {config.verified && <p><ShieldCheck size={18} aria-hidden='true' /> Verified number: <strong>{config.phone}</strong></p>}
        <label htmlFor='owner-sms-phone'>Your notification phone number</label>
        <div className='owner-sms-controls'><input id='owner-sms-phone' type='tel' autoComplete='tel' value={phone} maxLength={30} placeholder='024 123 4567' disabled={busy} onChange={e => setPhone(e.target.value)} /><button type='button' disabled={busy || !phone.trim() || !config.smsAvailable} onClick={() => action('request-code/', 'POST', { phone }, 'Verification SMS queued. Allow a few minutes for it to arrive. The code expires in 10 minutes.')}>Send verification code</button></div>
        {config.pendingPhone && <div className='owner-sms-code'><label htmlFor='owner-sms-code'>Code sent to {config.pendingPhone}</label><div className='owner-sms-controls'><input id='owner-sms-code' inputMode='numeric' autoComplete='one-time-code' maxLength={6} value={code} onChange={e => setCode(e.target.value.replace(/\D/g, ''))} /><button type='button' disabled={busy || code.length !== 6} onClick={() => action('verify-code/', 'POST', { code }, 'Phone verified. Choose your alerts and save to enable SMS.')}>Verify number</button></div></div>}
      </div>
      <fieldset disabled={busy} className='owner-sms-options'><legend>Choose your alerts</legend>
        <label className='owner-sms-option'><input type='checkbox' checked={config.enabled} disabled={!config.verified} onChange={e => setConfig({ ...config, enabled: e.target.checked })} /><span><strong>Enable owner SMS alerts</strong><small>Only future events after activation are sent.</small></span></label>
        {TYPES.map(([key, label, hint]) => <label key={key} className='owner-sms-option'><input type='checkbox' checked={config.eventTypes.includes(key)} onChange={e => setConfig({ ...config, eventTypes: e.target.checked ? [...config.eventTypes, key] : config.eventTypes.filter(t => t !== key) })} /><span><strong>{label}</strong><small>{hint}</small></span></label>)}
      </fieldset>
      <p className='settings-note'>SMS uses your platform's messaging credits. Sales can generate many messages. Security alerts are limited to one per business per hour. Low-stock alerts repeat only after stock recovers and falls again.</p>
      <button type='button' disabled={busy || (config.enabled && !config.verified)} onClick={() => action('', 'PATCH', { enabled: config.enabled, eventTypes: config.eventTypes }, 'SMS preferences saved.')}>{busy ? 'Please wait...' : 'Save SMS preferences'}</button>
      <details className='owner-sms-history'><summary>Recent SMS activity</summary><p>Provider acceptance does not confirm delivery to your phone.</p><button type='button' disabled={busy} onClick={() => setRetry(n => n + 1)}>Refresh activity</button>
        {recent.length === 0 ? <p>No owner alert messages yet.</p> : <ul>{recent.map(row => <li key={row.id}><strong>{STATES[row.status] || 'Pending review'}</strong><time dateTime={row.created_at}>{new Date(row.created_at).toLocaleString()}</time><p>{row.message || 'Message no longer available.'}</p></li>)}</ul>}
      </details>
    </>}
  </section>;
}
