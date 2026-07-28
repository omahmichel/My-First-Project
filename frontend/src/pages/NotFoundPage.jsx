import { ArrowLeft } from "lucide-react";
import { Link } from "react-router-dom";

export default function NotFoundPage() {
  return (
    <main className="not-found-page">
      <span>404</span>
      <h1>This page does not exist.</h1>
      <p>The address may be incorrect or the page may have been moved.</p>
      <Link to="/"><ArrowLeft size={18} /> Return to StockFlow</Link>
    </main>
  );
}
