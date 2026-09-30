import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import { installPlatformErrorReporting } from "./services/platformErrorReporting";

import App from "./App";
import { AuthProvider } from "./context/AuthContext";
import { StoreProvider } from "./context/StoreContext";
import "./styles/global.css";
import "./styles/design-system.css";
import "./styles/premium-data-table.css";
import "./styles/stockflow-inventory-system.css";
import "./styles/tailwind.css";

const removeErrorReporting = installPlatformErrorReporting();
if (import.meta.hot) import.meta.hot.dispose(removeErrorReporting);

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <StoreProvider>
          <App />
        </StoreProvider>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
