import { useEffect, useRef } from 'react';
import { LogIn, Building2, ShieldCheck } from 'lucide-react';
import { Link } from 'react-router-dom';

export default function LandingLoginChoice({ navigationOpen = false, onOpen }) {
  const ref = useRef(null);
  useEffect(() => { if (navigationOpen && ref.current) ref.current.open = false; }, [navigationOpen]);
  useEffect(() => {
    const close = event => {
      if (event.type === 'keydown' && event.key !== 'Escape') return;
      if (event.type === 'pointerdown' && ref.current?.contains(event.target)) return;
      if (ref.current) ref.current.open = false;
    };
    document.addEventListener('pointerdown', close);
    document.addEventListener('keydown', close);
    return () => { document.removeEventListener('pointerdown', close); document.removeEventListener('keydown', close); };
  }, []);
  return <details className="sf-landing-login-choice" ref={ref} onToggle={(event) => { if (event.currentTarget.open) onOpen?.(); }}>
    <summary className="sf-landing-nav-icon" aria-label="Log in" title="Log in"><LogIn size={22} strokeWidth={2.2} aria-hidden="true" /></summary>
    <div className="sf-landing-login-options">
      <Link to="/login" onClick={() => { ref.current.open = false; }}><span className="sf-login-option-icon"><Building2 size={22} strokeWidth={2.1} aria-hidden="true" /></span><span>Business owner login</span></Link>
      <Link to="/admin-login" onClick={() => { ref.current.open = false; }}><span className="sf-login-option-icon"><ShieldCheck size={22} strokeWidth={2.1} aria-hidden="true" /></span><span>StockFlow admin login</span></Link>
    </div>
  </details>;
}
