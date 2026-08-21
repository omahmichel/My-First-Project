import { Outlet, useNavigate } from "react-router-dom";

import AccessBlockedModal from "../components/ui/AccessBlockedModal";
import { useStore } from "../context/StoreContext";

export default function RoleRoute({ allowedRoles, areaLabel }) {
  const { business } = useStore();
  const navigate = useNavigate();
  const role = business?.currentUserRole;

  // Django remains the security authority. This route guard mirrors the
  // established business-role rules so restricted staff receive a clear
  // warning before a protected page is rendered.
  if (business?.id && role && !allowedRoles.includes(role)) {
    return (
      <AccessBlockedModal
        open
        variant="role"
        role={role}
        areaLabel={areaLabel}
        businessName={business.name}
        onClose={() => navigate("/app/dashboard", { replace: true })}
      />
    );
  }

  return <Outlet />;
}
