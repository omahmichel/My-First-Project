import { createContext, useContext, useMemo, useState } from "react";

import { loadStoredValue, saveStoredValue } from "../services/storage";

const AuthContext = createContext(null);

const DEMO_USER = {
  id: "team_owner",
  name: "Michael Triumph",
  email: "owner@stockflow.demo",
  role: "owner",
};

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => loadStoredValue("auth_user", null));
  const [pendingRegistration, setPendingRegistration] = useState(() =>
    loadStoredValue("pending_registration", null),
  );

  function login({ email, password }) {
    if (!email?.trim() || !password?.trim()) {
      throw new Error("Enter your email and password.");
    }

    if (email.trim().toLowerCase() === DEMO_USER.email && password !== "password123") {
      throw new Error("The demo password is password123.");
    }

    const nextUser =
      email.trim().toLowerCase() === DEMO_USER.email
        ? DEMO_USER
        : {
            id: `user_${Date.now()}`,
            name: email.split("@")[0],
            email: email.trim().toLowerCase(),
            role: "owner",
          };

    setUser(nextUser);
    saveStoredValue("auth_user", nextUser);
    window.localStorage.setItem("stockflow_access_token", "demo-access-token");
    return nextUser;
  }

  function register(payload) {
    if (!payload.name?.trim() || !payload.email?.trim() || !payload.password?.trim()) {
      throw new Error("Complete all required registration fields.");
    }

    if (payload.password.length < 8) {
      throw new Error("Password must contain at least 8 characters.");
    }

    const registration = {
      ...payload,
      email: payload.email.trim().toLowerCase(),
    };

    setPendingRegistration(registration);
    saveStoredValue("pending_registration", registration);
    return registration;
  }

  function completeOnboarding(business) {
    const nextUser = {
      id: `user_${Date.now()}`,
      name: pendingRegistration?.name ?? business.ownerName ?? "Business Owner",
      email: pendingRegistration?.email ?? business.email,
      role: "owner",
    };

    setUser(nextUser);
    setPendingRegistration(null);
    saveStoredValue("auth_user", nextUser);
    saveStoredValue("pending_registration", null);
    window.localStorage.setItem("stockflow_access_token", "demo-access-token");
    return nextUser;
  }

  function logout() {
    setUser(null);
    saveStoredValue("auth_user", null);
    window.localStorage.removeItem("stockflow_access_token");
  }

  const value = useMemo(
    () => ({
      user,
      pendingRegistration,
      isAuthenticated: Boolean(user),
      login,
      register,
      completeOnboarding,
      logout,
    }),
    [pendingRegistration, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider.");
  }

  return context;
}
