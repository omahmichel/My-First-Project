import { ArrowDownLeft, ArrowUpRight, FileClock, Search } from "lucide-react";
import { useMemo, useState } from "react";

import Badge from "../../components/ui/Badge";
import PageHeader from "../../components/ui/PageHeader";
import { useStore } from "../../context/StoreContext";
import { formatDateTime } from "../../utils/formatters";

export default function StockMovementsPage() {
  const { stockMovements } = useStore();
  const [search, setSearch] = useState("");
  const [type, setType] = useState("all");

  const movements = useMemo(() => {
    const query = search.trim().toLowerCase();
    return stockMovements.filter((movement) => {
      const matchesQuery = !query || [movement.productName, movement.reason, movement.user]
        .some((value) => value.toLowerCase().includes(query));
      return matchesQuery && (type === "all" || movement.type === type);
    });
  }, [search, stockMovements, type]);

  return (
    <div className="page-stack">
      <PageHeader eyebrow="Inventory audit" title="Stock movements" description="Every controlled stock increase and reduction appears in this permanent history." />

      <section className="panel-card">
        <div className="table-toolbar">
          <label className="table-search"><Search size={18} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search product, reason or user..." /></label>
          <select value={type} onChange={(event) => setType(event.target.value)}><option value="all">All movement types</option><option value="sale">Sales</option><option value="stock_in">Stock received</option><option value="opening_stock">Opening stock</option><option value="adjustment">Adjustments</option><option value="damage">Damage</option><option value="return">Returns</option></select>
        </div>

        <div className="movement-list">
          {movements.map((movement) => {
            const incoming = movement.quantity > 0;
            return (
              <article key={movement.id}>
                <div className={`movement-icon ${incoming ? "movement-in" : "movement-out"}`}>{incoming ? <ArrowDownLeft size={20} /> : <ArrowUpRight size={20} />}</div>
                <div className="movement-main"><strong>{movement.productName}</strong><span>{movement.reason}</span><small><FileClock size={14} /> {formatDateTime(movement.createdAt)} · {movement.user}</small></div>
                <Badge tone={incoming ? "success" : movement.type === "sale" ? "neutral" : "warning"}>{movement.type.replace("_", " ")}</Badge>
                <div className={`movement-quantity ${incoming ? "success-text" : "danger-text"}`}>{incoming ? "+" : ""}{movement.quantity} <small>{movement.unit}(s)</small></div>
              </article>
            );
          })}
        </div>
      </section>
    </div>
  );
}
