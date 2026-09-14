import { Bell, RefreshCw, X } from "lucide-react";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Link } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { useStore } from "../../context/StoreContext";
import { apiRequest } from "../../services/api";
import { useNotificationActions, useNotificationScope } from "./NotificationRefresh";
import "./notifications.css";

export default function NotificationBell(props) {
  const { user } = useAuth();
  const scope = useNotificationScope();
  return <NotificationMenu key={`${user?.id}:${scope}`} {...props} />;
}

function NotificationMenu({ className, intelligence = false }) {
  const { business, activeBranchId } = useStore();
  const scope = useNotificationScope();
  const actions = useNotificationActions().filter(([, action]) => action.scope === scope);
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [marking, setMarking] = useState(false);
  const [error, setError] = useState("");
  const [position, setPosition] = useState({});
  const button = useRef(null);
  const panel = useRef(null);
  const mounted = useRef(true);
  const requestId = useRef(0);
  const pendingRead = useRef(false);
  const id = useId();
  const base = `/businesses/${business.id}/notifications/`;
  const query = activeBranchId ? `?branchId=${encodeURIComponent(activeBranchId)}` : "";
  const available = Boolean(business.id && business.hasSystemAccess);
  const unread = items.filter(item => !item.read).length;

  useEffect(() => { mounted.current = true; return () => { mounted.current = false; requestId.current++; }; }, []);
  const load = useCallback(async () => {
    if (!available || pendingRead.current) return;
    const sequence = ++requestId.current;
    setLoading(true);
    setError("");
    try {
      const result = await apiRequest(base + query);
      if (mounted.current && sequence === requestId.current) setItems(result.items || []);
    } catch {
      if (mounted.current && sequence === requestId.current) setError("Notifications could not load. Please try refresh again.");
    } finally {
      if (mounted.current && sequence === requestId.current) setLoading(false);
    }
  }, [base, query, available]);

  useEffect(() => {
    load();
    const onFocus = () => { if (!document.hidden && !pendingRead.current) load(); };
    window.addEventListener("focus", onFocus);
    const timer = window.setInterval(onFocus, 60000);
    return () => { window.removeEventListener("focus", onFocus); window.clearInterval(timer); };
  }, [load]);

  function close(returnFocus = false) {
    setOpen(false);
    if (returnFocus) button.current?.focus();
  }
  useEffect(() => {
    if (!open) return;
    function place() {
      const rect = button.current.getBoundingClientRect();
      const width = Math.min(380, window.innerWidth - 24);
      const top = Math.min(rect.bottom + 8, window.innerHeight - 100);
      setPosition({ width, left: Math.max(12, Math.min(rect.right - width, window.innerWidth - width - 12)), top, maxHeight: window.innerHeight - top - 12 });
    }
    place();
    panel.current?.querySelector("button")?.focus();
    function outside(event) {
      if (!panel.current?.contains(event.target) && !button.current?.contains(event.target)) close();
    }
    function key(event) { if (event.key === "Escape") { event.preventDefault(); close(true); } }
    function focus(event) {
      if (!panel.current?.contains(event.target) && !button.current?.contains(event.target)) close();
    }
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", key);
    document.addEventListener("focusin", focus);
    window.addEventListener("resize", place);
    return () => {
      document.removeEventListener("pointerdown", outside);
      document.removeEventListener("keydown", key);
      document.removeEventListener("focusin", focus);
      window.removeEventListener("resize", place);
    };
  }, [open]);

  async function markRead(ids) {
    if (!ids.length || pendingRead.current) return;
    pendingRead.current = true;
    setMarking(true); setError("");
    // Invalidate a GET already in flight so it cannot undo read indicators.
    requestId.current++; setLoading(false);
    try {
      await apiRequest(base + "read/" + query, { method: "POST", body: JSON.stringify({ ids }) });
      if (mounted.current) setItems(previous => previous.map(item => ids.includes(item.id) ? { ...item, read: true } : item));
    } catch {
      if (mounted.current) setError("Could not mark these notifications as read. Refresh and try again.");
    } finally {
      pendingRead.current = false;
      if (mounted.current) setMarking(false);
    }
  }

  return <>
    <button ref={button} type="button" className={`${className} sf-notification-bell`} aria-label={`Notifications${unread ? `, ${unread} unread` : ""}`} aria-expanded={open} aria-controls={open ? id : undefined} aria-haspopup="dialog" onClick={() => { if (!open) load(); setOpen(value => !value); }}>
      <Bell size={20} />
      {unread > 0 && <span className="sf-notification-count">{unread}</span>}
    </button>
    {open && createPortal(<section ref={panel} id={id} className={`sf-notification-panel ${intelligence ? "sf-notification-intelligence" : ""}`} style={position} role="dialog" aria-label="Notifications and refresh">
      <header><div><strong>Notifications</strong><small>Latest alerts · {unread} unread</small></div><button type="button" aria-label="Close notifications" onClick={() => close(true)}><X size={18} /></button></header>
      <div className="sf-notification-refresh">
        <button type="button" disabled={loading || marking || !available} onClick={load}><RefreshCw size={16} />{loading ? "Refreshing notifications…" : "Refresh notifications"}</button>
        {actions.map(([key, action]) => <div key={key}>{action.element}</div>)}
      </div>
      {error && <p role="alert" className="sf-notification-error">{error}</p>}
      {!available && <p>Notifications are available in an active business workspace.</p>}
      {available && !loading && !error && !items.length && <p>You’re all caught up. No notifications yet.</p>}
      {unread > 0 && <button type="button" className="sf-notification-mark" disabled={marking || loading} onClick={() => markRead(items.filter(item => !item.read).map(item => item.id))}>Mark displayed notifications as read</button>}
      <ul>{items.map(item => <li key={item.id} className={item.read ? "" : "sf-notification-unread"}>
        <strong>{item.title}</strong><p>{item.message}</p><small>{new Date(item.createdAt).toLocaleString()}</small>
        <div><Link to={item.href} onClick={() => close()}>View details</Link>{!item.read && <button type="button" disabled={marking} onClick={() => markRead([item.id])}>Mark read</button>}</div>
      </li>)}</ul>
      {items.length === 30 && <footer>Showing the latest 30 notifications.</footer>}
    </section>, document.body)}
  </>;
}
