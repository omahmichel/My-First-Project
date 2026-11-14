export default function Badge({ children, tone = "neutral" }) {
  return <span data-stock-alert={typeof children === "string" && /^low[\s-]*stock$/i.test(children.trim()) ? "low" : undefined} className={`status-badge status-badge-${tone}`}>{children}</span>;
}
