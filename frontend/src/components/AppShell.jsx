import { useState } from "react";
import { Outlet, useNavigate } from "react-router-dom";
import { Menu, Search, LogOut, User } from "lucide-react";

import { Sidebar } from "./Sidebar";
import { useAuth } from "../context/AuthContext";

export function AppShell() {
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { user, logout } = useAuth();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div className="min-h-screen bg-[#f5f6f3] text-[#202521]">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      {sidebarOpen && (
        <button
          className="fixed inset-0 z-30 bg-[#202521]/30 lg:hidden"
          aria-label="Close navigation"
          onClick={() => setSidebarOpen(false)}
        />
      )}
      <div className="lg:pl-[254px]">
        <header className="sticky top-0 z-20 flex h-[72px] items-center justify-between border-b border-[#dfe3dd] bg-[#f5f6f3]/95 px-5 backdrop-blur md:px-8">
          <div className="flex items-center gap-3">
            <button
              className="icon-button lg:hidden"
              aria-label="Open navigation"
              onClick={() => setSidebarOpen(true)}
            >
              <Menu size={20} />
            </button>
            <div className="hidden h-9 w-px bg-[#dfe3dd] lg:block" />
            <p className="text-sm text-[#69716a]">Workspace / <span className="text-[#202521]">Document Intelligence</span></p>
          </div>
          <div className="flex items-center gap-2 md:gap-4">
            <button className="icon-button" aria-label="Search">
              <Search size={18} />
            </button>
            <div className="hidden h-7 w-px bg-[#dfe3dd] md:block" />
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-2 px-2 py-1 rounded-lg bg-[#29312b] md:hidden">
                <div className="avatar">
                  <User size={12} />
                </div>
                <span className="text-xs font-medium text-[#d7ded8]">{user?.name || "Admin"}</span>
              </div>
              <button
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium text-[#52705a] hover:bg-[#e8ebe7] transition-colors md:flex"
                onClick={handleLogout}
              >
                <LogOut size={14} />
                <span className="hidden sm:inline">Sign out</span>
              </button>
            </div>
          </div>
        </header>
        <main className="mx-auto max-w-[1480px] px-5 py-7 md:px-8 md:py-10">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
