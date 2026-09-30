import { useEffect, useRef, useState } from 'react';
import { Bell, MoreHorizontal, ArrowUpRight, X } from 'lucide-react';
import { apiRequest } from '../../services/api';

export default function PlatformAdminNotifications({ onSelect }) {
  const [open, setOpen] = useState(false);
  const [snapshot, setSnapshot] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const wrapper = useRef(null);
  const trigger = useRef(null);
  const closeButton = useRef(null);
  function close() { setOpen(false); trigger.current?.focus(); }
  useEffect(() => {
    if (!open) return undefined;
    let active = true;
    setLoading(true); setError(''); setSnapshot(null);
    closeButton.current?.focus();
    let inFlight = false;
    const load = () => {
    if (inFlight) return;
    inFlight = true;
    apiRequest('/platform-admin/notifications/')
      .then(result => { if (active) { setSnapshot(result); setError(''); } })
      .catch(e => { if (active) setError(e.message || 'Could not load notifications.'); })
      .finally(() => { inFlight = false; if (active) setLoading(false); });
    };
    load();
    const timer = window.setInterval(() => { if (!document.hidden) load(); }, 30000);
    const outside = event => { if (!wrapper.current?.contains(event.target)) setOpen(false); };
    const escape = event => { if (event.key === 'Escape') { event.preventDefault(); close(); } };
    document.addEventListener('pointerdown', outside);
    document.addEventListener('keydown', escape);
    return () => { active = false; window.clearInterval(timer); document.removeEventListener('pointerdown', outside); document.removeEventListener('keydown', escape); };
  }, [open]);
  return <div className="pa-notifications" ref={wrapper}>
    <button ref={trigger} className="pa-menu-trigger" type="button" aria-label="Notifications and subscription updates" aria-expanded={open} aria-controls="pa-notification-panel" onClick={() => setOpen(v => !v)}><MoreHorizontal size={22}/></button>
    {open && <section id="pa-notification-panel" className="pa-notification-panel" aria-label="Notifications">
      <header><div><span className="pa-menu-kicker"><Bell size={14}/> STATUS UPDATES</span><h3>Notifications</h3></div><button ref={closeButton} type="button" className="pa-menu-close" aria-label="Close notifications" onClick={close}><X size={18}/></button></header>
      <p className="pa-menu-help">System alerts and account statuses. Updates every 30 seconds while this menu is open.</p>
      <div className="pa-notification-list" aria-live="polite">
        {loading && <p className="pa-menu-help" role="status">Loading updates…</p>}
        {error && <p className="pa-error" role="alert">{error} Close and reopen to retry.</p>}
        {!loading && snapshot?.groups?.map(group => <section className="pa-notification-group" key={group.key}><h4>{group.title}<span>{group.total}</span></h4>
          {group.items.length === 0 ? <p className="pa-menu-empty">No updates in this category.</p> : group.items.map(item => <button className="pa-notification-item" type="button" key={item.id} onClick={() => { close(); onSelect(item); }}><span><strong>{item.title}</strong><small>{item.message}{item.at ? ' · ' + new Date(item.at).toLocaleDateString() : ''}</small></span><ArrowUpRight size={16}/></button>)}
          {group.total > group.items.length && <p className="pa-menu-empty">Showing {group.items.length} of {group.total}. Browse the related section for more.</p>}
        </section>)}
      </div>
      <footer>Security warnings indicate detected checks or suspicious activity, not confirmed attacks. Business alerts cover active businesses. Pending payments may include test records and do not confirm settlement.</footer>
    </section>}
  </div>;
}
