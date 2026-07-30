export default function StatCard({ icon: Icon, label, value, detail, tone = "green" }) {
  return (
    <article className="stat-card">
      <div className={`stat-card-icon stat-card-icon-${tone}`}>
        <Icon size={21} />
      </div>

      <div className="stat-card-content">
        <span>{label}</span>
        <strong>{value}</strong>
        {detail ? <small>{detail}</small> : null}
      </div>
    </article>
  );
}
