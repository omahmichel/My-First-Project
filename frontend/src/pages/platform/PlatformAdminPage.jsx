import { useEffect, useRef, useState } from 'react';
import { Link, Navigate, useParams, useNavigate } from 'react-router-dom';
import { Users, Building2, CreditCard, Activity, LayoutDashboard, ShieldCheck, Search } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { apiRequest } from '../../services/api';
import '../../styles/platform-admin.css';
import PlatformManagement from './PlatformManagement';
import PlatformAdminNotifications from './PlatformAdminNotifications';

const tabs = [['overview','Overview',LayoutDashboard],['users','Users',Users],['businesses','Businesses',Building2],['subscriptions','Subscriptions',CreditCard],['activity','Activity log',Activity],['administrators','Add Admin',ShieldCheck],['bugs','Bugs',Activity],['notifications','Notifications',Activity]];
const base = '/platform-admin/';
const date = value => value ? new Date(value).toLocaleString() : '—';
function Badge({ children, good }) { return <span className={`pa-badge ${good ? 'pa-good' : ''}`}>{children}</span>; }

export default function PlatformAdminPage() {
  const { user, isAuthenticated, isInitializing, logout } = useAuth();
  const { section = 'overview' } = useParams();
  const navigate = useNavigate();
  const tab = section;
  const setTab = next => navigate(`/platform-admin/${next}`);
  const custom = ['administrators','bugs','notifications'].includes(tab);
  const [term,setTerm] = useState('');
  const [query,setQuery] = useState('');
  const [status,setStatus] = useState('');
  const [category,setCategory] = useState('');
  const [fromDate,setFromDate] = useState('');
  const [toDate,setToDate] = useState('');
  const [page,setPage] = useState(1);
  const [data,setData] = useState(null);
  const [loadedTab,setLoadedTab] = useState(null);
  const [error,setError] = useState('');
  const [loading,setLoading] = useState(true);
  const [revision,setRevision] = useState(0);
  const [detail,setDetail] = useState(null);
  const [detailLoading,setDetailLoading] = useState(false);
  const detailSequence = useRef(0);
  const detailPanel = useRef(null);
  const [confirm,setConfirm] = useState(null);
  const [reason,setReason] = useState('');
  const [saving,setSaving] = useState(false);
  const [actionError,setActionError] = useState('');
  const [notice,setNotice] = useState('');
  const dialog = useRef(null);
  const allowed = isAuthenticated && user?.isPlatformAdmin;

  useEffect(() => {
    if (!allowed || custom) return;
    let cancelled = false;
    setLoading(true);setError('');setData(null);
    apiRequest(`${base}${tab}/?page=${page}&q=${encodeURIComponent(query)}&status=${encodeURIComponent(status)}&category=${encodeURIComponent(category)}&from=${fromDate}&to=${toDate}`)
      .then(result => { if (!cancelled) { setData(result); setLoadedTab(tab); } })
      .catch(err => { if (!cancelled) setError(err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  },[allowed,tab,page,query,status,category,fromDate,toDate,revision,custom]);
  useEffect(() => {
    if (!allowed) return undefined;
    const refreshOnFocus = () => setRevision(v => v + 1);
    window.addEventListener('focus', refreshOnFocus);
    return () => window.removeEventListener('focus', refreshOnFocus);
  }, [allowed]);
  useEffect(() => {
    if (!allowed || tab !== 'activity') return undefined;
    const timer = window.setInterval(() => { if (!document.hidden) setRevision(v => v + 1); }, 30000);
    return () => window.clearInterval(timer);
  }, [allowed, tab]);
  useEffect(() => { if (confirm && dialog.current && !dialog.current.open) dialog.current.showModal(); },[confirm]);
  useEffect(() => () => { detailSequence.current++; },[]);
  useEffect(() => { if (detail) { detailPanel.current?.scrollIntoView({block:"start"}); detailPanel.current?.focus({preventScroll:true}); } },[detail]);
  function openNotification(item) {
    switchTab(item.tab);
    setData(null);setLoading(true);setError('');setDetail(null);setDetailLoading(false);
    detailSequence.current++;setPage(1);setTerm(item.query);setQuery(item.query);setStatus('');setCategory('');setFromDate('');setToDate('');setRevision(v=>v+1);
  }
  function switchTab(next) {
    if (next === tab) return;
    setData(null);setLoading(true);setError('');
    detailSequence.current++;setDetailLoading(false);setTab(next);setPage(1);setTerm('');setQuery('');setStatus('');setCategory('');setFromDate('');setToDate('');setDetail(null);setNotice('');
  }
  async function inspect(row) {
    const seq = ++detailSequence.current;
    setDetail(null);setDetailLoading(true);setError('');
    try { const result = await apiRequest(`${base}${tab}/${row.id}/`);if (seq === detailSequence.current) setDetail(result); }
    catch(e) { if (seq === detailSequence.current) setError(e.message); }
    finally { if (seq === detailSequence.current) setDetailLoading(false); }
  }
  function ask(row) { setConfirm({kind:tab,row});setReason('');setActionError(''); }
  function closeConfirm() { if (!saving) { dialog.current?.close();setConfirm(null); } }
  async function applyStatus(event) {
    event.preventDefault();if (saving || !confirm) return;
    setSaving(true);setActionError('');
    const current = confirm.kind === 'users' ? confirm.row.active : confirm.row.status === 'active';
    try {
      await apiRequest(`${base}${confirm.kind}/${confirm.row.id}/status/`,{method:'POST',body:JSON.stringify({active:!current,expectedActive:current,reason:reason.trim()})});
      dialog.current?.close();setConfirm(null);setDetail(null);setNotice('Account status updated. The change was recorded in the activity log.');setRevision(v=>v+1);
    } catch(e) {setActionError(e.message);} finally {setSaving(false);}
  }
  if (isInitializing) return <main className="pa-root"><p role="status">Loading your account…</p></main>;
  if (!isAuthenticated) return <Navigate to="/login" replace state={{from:'/platform-admin'}} />;
  if (!allowed) return <main className="pa-root"><h1>Platform administrator access required</h1><p>Your business account does not grant access to all StockFlow accounts.</p><Link to="/businesses">Return to my businesses</Link></main>;
  if (!tabs.some(t=>t[0]===tab)) return <Navigate to="/platform-admin/overview" replace/>;
  const selected = tabs.find(t=>t[0]===tab);
  const statuses = tab === 'activity' ? ['info','warning','error','critical'] : tab === 'subscriptions' ? ['pending','successful','failed','cancelled'] : ['active','inactive'];
  const active = confirm && (confirm.kind === 'users' ? confirm.row.active : confirm.row.status === 'active');
  return <main className="pa-root pa-integrated">
    <section className="pa-hero"><div><p className="pa-eyebrow"><ShieldCheck size={16}/> PLATFORM ADMINISTRATION</p><h1>Your StockFlow control centre</h1><p>Manage people, businesses and subscription records across every industry.</p></div><Badge good>Administrator access</Badge></section>
    <div className="pa-layout">
    <section className="pa-content" aria-labelledby="pa-heading">
      <header className="pa-section-head"><div><p className="pa-eyebrow">STOCKFLOW / PLATFORM</p><h2 id="pa-heading">{selected[1]}</h2></div><PlatformAdminNotifications onSelect={openNotification}/></header>
      {notice && <p className="pa-notice" role="status">{notice}</p>}
      {tab==='subscriptions' && <p className="pa-note">Recorded subscription payments and their verification status. Historical test payments may be included; these figures do not prove live revenue or bank settlement.</p>}
      {tab==='activity' && <p className="pa-note">Application actions, record changes, validation results and detected security events. Repeated requests are grouped by minute. Collection starts when installed; earlier administrator status changes are preserved.</p>}
      {!custom && tab!=='overview' && <form className="pa-filters" onSubmit={e=>{e.preventDefault();setPage(1);setQuery(term.trim());setRevision(v=>v+1);}}><label>Search<input value={term} maxLength={180} onChange={e=>setTerm(e.target.value)} placeholder={tab==='activity'?'Event, route, request or account ID':tab==='users'?'Name, email or phone':tab==='businesses'?'Business, owner email or slug':'Business or payment reference'}/></label><label>{tab==='activity'?'Severity':'Status'}<select value={status} onChange={e=>{setStatus(e.target.value);setPage(1);}}><option value="">{tab==='activity'?'All severities':'All statuses'}</option>{statuses.map(s=><option key={s} value={s}>{s}</option>)}</select></label>{tab==='activity' && <><label>Category<select value={category} onChange={e=>{setCategory(e.target.value);setPage(1);}}><option value="">All categories</option>{['authentication','administration','business','payment','access','validation','system','security'].map(c=><option value={c} key={c}>{c}</option>)}</select></label><label>From<input type="date" value={fromDate} onChange={e=>{setFromDate(e.target.value);setPage(1);}}/></label><label>To<input type="date" value={toDate} onChange={e=>{setToDate(e.target.value);setPage(1);}}/></label></>}<button type="submit"><Search size={16}/>Search</button></form>}
      {error && <p className="pa-error" role="alert">{error}</p>}
      {custom ? <PlatformManagement key={tab} section={tab} onSelect={openNotification}/> : loading || loadedTab!==tab ? <p role="status" className="pa-empty">Loading {selected[1].toLowerCase()}…</p> : data && <>
        {tab==='overview' ? <><div className="pa-stats">{[['Registered users',data.users],['Active users',data.activeUsers],['Businesses',data.businesses],['Active businesses',data.activeBusinesses],['Current subscriptions',data.currentSubscriptions],['Current trials',data.currentTrials]].map(([label,value])=><article key={label}><p>{label}</p><strong>{value.toLocaleString()}</strong></article>)}</div><div className="pa-welcome"><h3>One view of every business</h3><p>Find an account, review its linked businesses and branches, or check subscription history. Staff roles within a business remain separate from platform administrator access.</p><button onClick={()=>switchTab('businesses')}>Browse businesses</button></div></> : <>
        <p className="pa-count">{data.count.toLocaleString()} records · Page {page} of {Math.max(1,Math.ceil(data.count/20))}</p>
        <div className="pa-records">{data.results.map(row=><article className="pa-record" key={row.id}>
          {tab==='users' && <><header><h3>{row.name || 'Unnamed account'}</h3><Badge good={row.active}>{row.active?'Active':'Suspended'}</Badge></header><p>{row.email}</p><p>{row.phone || 'No phone recorded'}</p><small>Joined {date(row.joinedAt)} · {row.administrator?'Administrator account':'Business user'}</small><div className="pa-actions"><button onClick={()=>inspect(row)}>View details</button>{!row.administrator && row.id!==user.id && <button className={row.active?'pa-danger':''} onClick={()=>ask(row)}>{row.active?'Suspend':'Reactivate'}</button>}</div></>}
          {tab==='businesses' && <><header><h3>{row.name}</h3><Badge good={row.status==='active'}>{row.status}</Badge></header><p>{row.type}</p><p>Owner: {row.owner.name || row.owner.email}</p><p>{row.owner.email}</p><small>{row.subscriptionCurrent?'Current paid subscription':row.trialCurrent?'Current free trial':'No current subscription or trial'}</small><div className="pa-actions"><button onClick={()=>inspect(row)}>View details</button><button className={row.status==='active'?'pa-danger':''} onClick={()=>ask(row)}>{row.status==='active'?'Suspend':'Reactivate'}</button></div></>}
          {tab==='subscriptions' && <><header><h3>{row.business}</h3><Badge good={row.status==='successful'}>{row.status}</Badge></header><strong>{row.currency} {Number(row.amount).toFixed(2)}</strong><p>{row.reference}</p><small>{row.durationDays} days · Created {date(row.createdAt)}<br/>Paid {date(row.paidAt)}</small></>}
          {tab==='activity' && <><header><h3>{row.summary}</h3><span className={`pa-badge pa-severity-${row.severity}`}>{row.severity}</span></header><p>{row.category} · {row.action}</p><p>{row.business}</p><small>By {row.actor}<br/>{date(row.at)}{row.occurrences>1 ? ` · ${row.occurrences} occurrences · Last ${date(row.lastSeenAt)}` : ''}</small><details className="pa-event-details"><summary>Event details</summary><dl><dt>Source</dt><dd>{row.source}</dd><dt>Request</dt><dd>{row.method} {row.route || 'No resolved route'} {row.httpStatus || ''}</dd><dt>Request ID</dt><dd>{row.requestId || '—'}</dd><dt>Peer IP</dt><dd>{row.peerIp || '—'}</dd><dt>Record</dt><dd>{row.objectType || '—'} {row.objectId}</dd>{Object.entries(row.details || {}).map(([key,value])=><div key={key}><dt>{key.replaceAll('_',' ')}</dt><dd>{Array.isArray(value)?value.join(', '):String(value)}</dd></div>)}</dl></details></>}

        </article>)}</div>
        {!data.results.length && <p className="pa-empty">No records match this view.</p>}
        <div className="pa-pagination"><button disabled={!data.previous} onClick={()=>setPage(p=>p-1)}>Previous</button><span>Page {page}</span><button disabled={!data.next} onClick={()=>setPage(p=>p+1)}>Next</button></div>
        </>}
      </>}
      {detailLoading && <p role="status">Loading account details…</p>}
      {detail && <section ref={detailPanel} tabIndex={-1} className="pa-detail" aria-label="Account details"><header><h3>{detail.name || detail.email}</h3><button onClick={()=>setDetail(null)}>Close details</button></header><dl><dt>Email</dt><dd>{detail.email || '—'}</dd><dt>Phone</dt><dd>{detail.phone || '—'}</dd><dt>Registered</dt><dd>{date(detail.joinedAt)}</dd></dl>
        {tab==='users' ? <><p>Last login: {date(detail.lastLogin)}</p><h4>Owned businesses ({detail.ownedBusinessCount})</h4>{detail.ownedBusinesses.map(b=><p key={b.id}>{b.name} · {b.status}</p>)}<h4>Business memberships ({detail.membershipCount})</h4>{detail.memberships.map((m,i)=><p key={i}>{m.business} · {m.role} · {m.active?'Active':'Inactive'}</p>)}</> : <><p>Location: {detail.location || '—'}</p><p>Owner: {detail.owner.name} · {detail.owner.email}</p><p>Subscription: {detail.subscriptionStatus}</p><p>Trial ends: {date(detail.trialEndsAt)}</p><p>Paid access ends: {date(detail.subscriptionEndsAt)}</p><h4>Branches ({detail.branchCount})</h4>{detail.branches.map(b=><p key={b.id}>{b.name} · {b.is_active?'Active':'Inactive'}</p>)}<h4>Team memberships ({detail.memberCount})</h4>{detail.members.map((m,i)=><p key={i}>{m.name || m.email} · {m.email} · {m.role} · {m.active?'Active':'Inactive'}</p>)}</>}
        <small>Each related list shows up to 100 records.</small></section>}
    </section></div>
    {confirm && <dialog ref={dialog} aria-labelledby="pa-confirm-title" className="pa-dialog" onCancel={e=>{e.preventDefault();closeConfirm();}}><form onSubmit={applyStatus}><h2 id="pa-confirm-title">{active?'Suspend':'Reactivate'} {confirm.row.name || confirm.row.email}?</h2><p>{confirm.kind==='users'?'This changes the user’s ability to sign in and use authenticated APIs.':'This changes the business’s active status. Subscription dates and existing records are retained.'}</p><label>Reason<textarea required minLength={5} maxLength={500} value={reason} onChange={e=>setReason(e.target.value)} disabled={saving}/></label>{actionError && <p role="alert">{actionError}</p>}<div className="pa-actions"><button type="button" disabled={saving} onClick={closeConfirm}>Cancel</button><button disabled={saving || reason.trim().length<5} type="submit">{saving?'Saving…':'Confirm change'}</button></div></form></dialog>}
  </main>;
}
