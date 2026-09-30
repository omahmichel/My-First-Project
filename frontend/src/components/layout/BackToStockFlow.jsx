import { ArrowLeft } from 'lucide-react';
import { Link } from 'react-router-dom';

// Public callers must check shop membership before rendering this control.
export default function BackToStockFlow({ onClick }) {
  return <Link className="sf-shop-back-link" to="/app/dashboard" onClick={onClick}>
    <ArrowLeft size={17} aria-hidden="true" />Back to StockFlow
  </Link>;
}
