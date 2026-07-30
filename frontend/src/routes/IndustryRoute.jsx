import { Navigate, Outlet } from "react-router-dom";

import { useStore } from "../context/StoreContext";

export default function IndustryRoute({ allowedBusinessTypes }) {
  const { business } = useStore();

  if (!allowedBusinessTypes.includes(business.type)) {
    return <Navigate to="/app/dashboard" replace />;
  }

  return <Outlet />;
}