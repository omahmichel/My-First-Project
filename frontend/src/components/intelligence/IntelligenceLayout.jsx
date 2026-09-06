import { useState } from "react";
import { Outlet } from "react-router-dom";

import IntelligenceSidebar from "./IntelligenceSidebar";
import IntelligenceTopbar from "./IntelligenceTopbar";

import "../../styles/intelligence-workspace.css";


export default function IntelligenceLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="intelligence-workspace">
      <IntelligenceSidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      <div className="intelligence-workspace-main">
        <IntelligenceTopbar
          onOpenSidebar={() => setSidebarOpen(true)}
        />
        <main className="intelligence-workspace-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
