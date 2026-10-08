import { NavLink } from "react-router-dom";
import { BarChart3, Boxes, FileText, GitBranch, LayoutDashboard, LogOut, MessageSquareText, Network, User, X } from "lucide-react";

import { getHealth } from "../api/client";
import { useApiResource } from "../hooks/useApiResource";
import { useAuth } from "../context/AuthContext";

const primaryNavigation = [
  { label: "Overview", to: "/", icon: LayoutDashboard },
  { label: "Documents", to: "/documents", icon: FileText },
  { label: "Knowledge graph", to: "/graph", icon: Network },
  { label: "Evidence", to: "/evidence", icon: GitBranch },
  { label: "Ask documents", to: "/query", icon: MessageSquareText },
  { label: "Analytics", to: "/analytics", icon: BarChart3 },
];

export function Sidebar({ open, onClose }) {
  const health = useApiResource(getHealth);
  const { user, logout } = useAuth();
  const statusClass = health.loading ? "bg-[#d09b45]" : health.error ? "bg-[#a45d42]" : "bg-[#52705a]";
  const statusText = health.loading ? "Checking API connection…" : health.error ? "FastAPI unavailable" : "FastAPI connected";

  return (
    <aside className={`fixed inset-y-0 left-0 z-40 flex w-[254px] flex-col border-r border-[#dfe3dd] bg-[#202521] px-4 py-5 text-[#f5f6f3] transition-transform duration-200 lg:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`}>
      <div className="flex items-center justify-between px-3">
        <NavLink to="/" className="flex items-center gap-3" onClick={onClose}>
          <div className="brand-mark"><Boxes size={18} strokeWidth={2.5} /></div>
          <div>
            <p className="font-display text-lg font-semibold tracking-tight">Atlas</p>
            <p className="text-[10px] uppercase tracking-[0.18em] text-[#9ba79e]">Document intelligence</p>
          </div>
        </NavLink>
        <button className="icon-button text-[#9ba79e] hover:text-white lg:hidden" aria-label="Close navigation" onClick={onClose}>
          <X size={18} />
        </button>
      </div>

      <div className="mt-12 px-3 text-[10px] font-semibold uppercase tracking-[0.2em] text-[#7e8a81]">Workspace</div>
      <nav className="mt-3 space-y-1">
        {primaryNavigation.map(({ label, to, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            onClick={onClose}
            className={({ isActive }) => `sidebar-link ${isActive ? "sidebar-link-active" : ""}`}
            end={to === "/"}
          >
            <Icon size={18} strokeWidth={1.8} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="mt-auto rounded-lg border border-[#3c473e] bg-[#29312b] p-4">
        <div className="flex items-center justify-between mb-3">
          <span className="text-xs font-semibold text-[#d7ded8]">API connection</span>
          <span className={`status-dot ${statusClass}`} />
        </div>
        <p className="text-xs leading-5 text-[#9ba79e]">{statusText}</p>
      </div>

      <div className="mt-4 px-3">
        <button
          className="flex items-center gap-2 w-full px-3 py-2 rounded-lg text-xs font-medium text-[#9ba79e] hover:bg-[#2b342d] hover:text-[#f5f6f3] transition-colors"
          onClick={logout}
        >
          <LogOut size={14} />
          <span>Sign out</span>
        </button>
      </div>

      <div className="mt-3 px-3">
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[#29312b]">
          <div className="avatar">
            <User size={14} />
          </div>
          <div className="min-w-0">
            <p className="text-xs font-semibold text-[#d7ded8] truncate">{user?.full_name || user?.name || "Not signed in"}</p>
            <p className="text-[10px] text-[#9ba79e] truncate">{user?.email || "Not signed in"}</p>
          </div>
        </div>
      </div>

      <p className="mt-4 px-3 text-[10px] uppercase tracking-[0.16em] text-[#69756c]">v0.1.0 · Internal</p>
    </aside>
  );
}
