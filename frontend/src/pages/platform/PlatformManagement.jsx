import { useEffect, useRef, useState } from 'react';
import { apiRequest } from '../../services/api';

export default function PlatformManagement({section,onSelect}) {
  const blankRegistration={fullName:'',email:'',phone:'',newPassword:'',confirmPassword:'',adminPassword:'',confirmAccess:false};
  const [registrationOpen,setRegistrationOpen]=useState(false);
  const registrationDialog=useRef(null);
  const registrationTrigger=useRef(null);
  const [registration,setRegistration]=useState(blankRegistration);
  const [registrationError,setRegistrationError]=useState('');
  const [registrationNotice,setRegistrationNotice]=useState('');
  const [registering,setRegistering]=useState(false);
  const [data,setData]=useState(null), [error,setError]=useState(''), [notice,setNotice]=useState('');
  const [term,setTerm]=useState(''), [query,setQuery]=useState(''), [status,setStatus]=useState(''), [page,setPage]=useState(1);
  const [revision,setRevision]=useState(0), [loading,setLoading]=useState(true), [saving,setSaving]=useState(false);
  const [selected,setSelected]=useState(null), [password,setPassword]=useState(''), [confirmed,setConfirmed]=useState(false);
  useEffect(()=>{
    let active=true;setLoading(true);setError('');
    apiRequest(`/platform-admin/${section}/?page=${page}&q=${encodeURIComponent(query)}&status=${status}`)
      .then(r=>{if(active)setData(r);}).catch(e=>{if(active)setError(e.message);}).finally(()=>{if(active)setLoading(false);});
    return ()=>{active=false;};
  },[section,page,query,status,revision]);
  useEffect(()=>{
    if(section!=='notifications')return undefined;
    const timer=setInterval(()=>{if(!document.hidden)setRevision(v=>v+1);},30000);
    return ()=>clearInterval(timer);
  },[section]);
  useEffect(()=>{
    const dialog=registrationDialog.current;
    if(registrationOpen && dialog && !dialog.open) dialog.showModal();
    if(!registrationOpen && dialog?.open) dialog.close();
  },[registrationOpen]);
  function closeRegistration(){
    if(registering)return;
    setRegistrationOpen(false);setRegistration(blankRegistration);setRegistrationError('');
    registrationTrigger.current?.focus();
  }
  function openRegistration(){
    setRegistration(blankRegistration);setRegistrationError('');setRegistrationNotice('');setRegistrationOpen(true);
  }
  async function registerAdmin(e){
    e.preventDefault();if(registering)return;
    setRegistrationError('');setRegistrationNotice('');
    if(registration.newPassword!==registration.confirmPassword){setRegistrationError('The new passwords do not match.');return;}
    setRegistering(true);
    try{
      const r=await apiRequest('/platform-admin/administrators/register/',{method:'POST',body:JSON.stringify(registration)});
      setRegistrationNotice(r.detail);setRegistrationOpen(false);registrationTrigger.current?.focus();setRegistration(blankRegistration);setTerm('');setQuery('');setPage(1);setRevision(v=>v+1);
    }catch(e){setRegistrationError(e.message);setRegistration(v=>({...v,newPassword:'',confirmPassword:'',adminPassword:''}));}
    finally{setRegistering(false);}
  }
  async function grant(e){
    e.preventDefault();if(saving||!selected||!confirmed)return;
    setSaving(true);setError('');setNotice('');
    try {
      const r=await apiRequest('/platform-admin/administrators/',{method:'POST',body:JSON.stringify({userId:selected.id,confirmEmail:selected.email,password})});
      setNotice(r.detail);setSelected(null);setConfirmed(false);setRevision(v=>v+1);
    }catch(e){setError(e.message);}finally{setPassword('');setSaving(false);}
  }
  async function updateBug(row,next){
    if(saving||next===row.status)return;
    setSaving(true);setError('');setNotice('');
    try{await apiRequest(`/platform-admin/bugs/${row.id}/status/`,{method:'POST',body:JSON.stringify({status:next,expectedStatus:row.status})});setNotice('Bug status updated and recorded in the activity log.');setRevision(v=>v+1);}
    catch(e){setError(e.message);setRevision(v=>v+1);}finally{setSaving(false);}
  }
  return <>
    <p className="pa-note">{section==='administrators' ? 'Manage administrators and use Add Administrator to register a new account. Only authorised platform administrators can create or grant this access. No business registration is required.' : section==='bugs' ? 'Captured application errors and new support reports. Reports describe symptoms; review them before deciding the cause.' : 'System alerts and subscription updates. This view updates every 30 seconds while visible.'}</p>
    {section==='administrators' && <section aria-label="Administrator management">
      <div className="pa-section-head"><h3>Registered administrators</h3><button ref={registrationTrigger} type="button" aria-haspopup="dialog" onClick={openRegistration}>Add Administrator</button></div>
      {registrationNotice && <p className="pa-notice" role="status">{registrationNotice}</p>}
      <dialog ref={registrationDialog} className="pa-dialog" aria-labelledby="register-admin-heading" onCancel={e=>{e.preventDefault();closeRegistration();}}>
      {registrationOpen && <form className="pa-grant-form" style={{margin:0,padding:0,border:0,background:'transparent'}} onSubmit={registerAdmin}>
        <div className="pa-section-head"><h3 id="register-admin-heading">Register a new administrator</h3><button type="button" aria-label="Close administrator registration" disabled={registering} onClick={closeRegistration}>Close</button></div>
        <p>The new account will have full StockFlow platform and Django administrator access.</p>
        {registrationError && <p className="pa-error" role="alert">{registrationError}</p>}
        {[['fullName','Full name','text',150,'name'],['email','Email address','email',254,'email'],['phone','Phone number (optional)','tel',30,'tel'],['newPassword','New administrator password','password',1024,'new-password'],['confirmPassword','Confirm new administrator password','password',1024,'new-password'],['adminPassword','Your current administrator password','password',1024,'current-password']].map(([key,label,type,maxLength,autoComplete])=><label key={key}>{label}<input autoFocus={key==='fullName'} name={key} type={type} maxLength={maxLength} autoComplete={autoComplete} required={key!=='phone'} value={registration[key]} disabled={registering} onChange={e=>setRegistration(v=>({...v,[key]:e.target.value}))}/></label>)}
        <label><input type="checkbox" checked={registration.confirmAccess} disabled={registering} onChange={e=>setRegistration(v=>({...v,confirmAccess:e.target.checked}))}/>I authorise this person to manage StockFlow as a platform administrator.</label>
        <div className="pa-actions"><button type="button" disabled={registering} onClick={closeRegistration}>Cancel</button><button type="submit" disabled={registering||!registration.confirmAccess}>{registering?'Creating administrator…':'Create Administrator'}</button></div>
      </form>}
      </dialog>
      <p className="pa-note">Current administrators are listed below. Search by email or name to find an existing account and grant access.</p>
    </section>}
    {section!=='notifications' && <form className="pa-filters" onSubmit={e=>{e.preventDefault();setQuery(term.trim());setPage(1);setRevision(v=>v+1);}}>
      <label>Search<input value={term} onChange={e=>setTerm(e.target.value)} placeholder={section==='administrators'?'Account email or name':'Title, business ID or request ID'} maxLength={180}/></label>
      {section==='bugs' && <label>Status<select value={status} onChange={e=>{setStatus(e.target.value);setPage(1);}}><option value="">All statuses</option><option value="open">Open</option><option value="investigating">Investigating</option><option value="resolved">Resolved</option></select></label>}
      <button type="submit">Search</button>
    </form>}
    {notice && <p className="pa-notice" role="status">{notice}</p>}
    {error && <p className="pa-error" role="alert">{error}</p>}
    {selected && <form className="pa-grant-form" onSubmit={grant}>
      <h3>Grant platform administrator access</h3><p><strong>{selected.name || selected.email}</strong><br/>{selected.email} · Account #{selected.id}</p>
      <p>This grants control over all StockFlow businesses, users and administrator access.</p>
      <label>Your administrator password<input type="password" value={password} onChange={e=>setPassword(e.target.value)} autoComplete="current-password" required maxLength={1024}/></label>
      <label><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>I confirm this is the account that should receive full platform access.</label>
      <div className="pa-actions"><button disabled={saving||!confirmed||!password} type="submit">{saving?'Granting access…':'Confirm administrator access'}</button><button type="button" disabled={saving} onClick={()=>{setSelected(null);setPassword('');setConfirmed(false);}}>Cancel</button></div>
    </form>}
    {loading ? <p role="status">Loading…</p> : data && (section==='notifications' ? <div className="pa-records">{data.groups.map(group=><article className="pa-record" key={group.key}><h3>{group.title} <span className="pa-badge">{group.total}</span></h3>{group.items.length ? group.items.map(item=><div className="pa-note" key={item.id}><strong>{item.title}</strong><p>{item.message}</p><button onClick={()=>onSelect(item)}>View details</button></div>) : <p>No updates in this category.</p>}{group.total>group.items.length && <small>Showing {group.items.length} of {group.total}.</small>}</article>)}</div> : <>
      <p className="pa-count">{data.count} records · Page {page}</p>
      <div className="pa-records">{data.results.map(row=><article className="pa-record" key={row.id}>
        {section==='administrators' ? <><header><h3>{row.name || 'Unnamed account'}</h3><span className="pa-badge">{row.platformAdmin?'Platform administrator':'Active account'}</span></header><p>{row.email}</p><small>Account #{row.id}</small>{!row.platformAdmin && <div className="pa-actions"><button disabled={saving} onClick={()=>{setSelected(row);setPassword('');setConfirmed(false);setError('');}}>Select account</button></div>}</> : <>
          <header><h3>{row.title}</h3><span className="pa-badge">{row.status}</span></header><p>{row.source==='support'?'User support report':'Captured application error'}</p><small>{new Date(row.createdAt).toLocaleString()} · Bug #{row.id}</small>
          <details className="pa-event-details"><summary>Bug details</summary><p className="pa-bug-description">{row.description || 'No message or payload was collected for this automatic error.'}</p><p>Reporter ID: {row.reporterId || 'System'}<br/>Business ID: {row.businessId || 'Platform'}</p>{row.event && <><p>{row.event.action} · {row.event.severity}<br/>{row.event.route}<br/>{row.event.occurrences} occurrence(s)</p><button onClick={()=>onSelect({tab:'activity',query:row.event.requestId || row.event.action})}>View activity</button></>}</details>
          <label>Update status<select aria-label={`Status for bug ${row.id}`} disabled={saving} value={row.status} onChange={e=>updateBug(row,e.target.value)}><option value="open">Open</option><option value="investigating">Investigating</option><option value="resolved">Resolved</option></select></label>
        </>}
      </article>)}</div>
      {!data.results.length && <p className="pa-empty">No records match this view.</p>}
      <div className="pa-pagination"><button disabled={!data.previous||saving} onClick={()=>setPage(v=>v-1)}>Previous</button><span>Page {page}</span><button disabled={!data.next||saving} onClick={()=>setPage(v=>v+1)}>Next</button></div>
    </>)}
  </>;
}
