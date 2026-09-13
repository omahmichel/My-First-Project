import "../../styles/welcome-actions.css";

export default function PageHeader({ eyebrow, title, description, actions }) {
  return (
    <>
      <div className="page-header">
        <div>
          {eyebrow ? <span className="page-eyebrow">{eyebrow}</span> : null}
          <h1>{title}</h1>
          {description ? <p>{description}</p> : null}
        </div>
      </div>
      {actions ? <div className="page-header-actions sf-welcome-actions">{actions}</div> : null}
    </>
  );
}
