export default function Button({
  children,
  variant = "primary",
  size = "medium",
  type = "button",
  className = "",
  ...props
}) {
  return (
    <button
      type={type}
      className={`app-button app-button-${variant} app-button-${size} ${className}`.trim()}
      {...props}
    >
      {children}
    </button>
  );
}
