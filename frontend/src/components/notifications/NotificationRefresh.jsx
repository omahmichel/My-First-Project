import { createContext, useCallback, useContext, useEffect, useId, useMemo, useState } from "react";
import { useLocation } from "react-router-dom";
import { useStore } from "../../context/StoreContext";

const RegisterContext = createContext(null);
const ActionsContext = createContext([]);

export function NotificationActionsProvider({ children }) {
  const [actions, setActions] = useState({});
  const register = useCallback((id, action) => {
    setActions(previous => {
      const next = { ...previous };
      if (action) next[id] = action;
      else delete next[id];
      return next;
    });
  }, []);
  const values = useMemo(() => Object.entries(actions), [actions]);
  return <RegisterContext.Provider value={register}>
    <ActionsContext.Provider value={values}>{children}</ActionsContext.Provider>
  </RegisterContext.Provider>;
}

export function useNotificationActions() { return useContext(ActionsContext); }

export function useNotificationScope() {
  const { business, activeBranchId } = useStore();
  const { pathname } = useLocation();
  return `${business.id || ""}:${activeBranchId || ""}:${pathname}`;
}

// Register the original control, preserving its callback and disabled/loading state.
export default function NotificationRefresh({ children }) {
  const register = useContext(RegisterContext);
  const id = useId();
  const scope = useNotificationScope();
  useEffect(() => {
    if (register) register(id, { element: children, scope });
  }, [register, id, children, scope]);
  useEffect(() => () => { if (register) register(id, null); }, [register, id]);
  return register ? null : children;
}
