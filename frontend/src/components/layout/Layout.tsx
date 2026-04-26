import { NavLink, type ReactNode } from "react-router-dom";
import type { ClientMessage } from "@/types";
import { cn } from "@/lib/cn";
import {
  MessageSquare,
  Users,
  FolderOpen,
  Settings,
  History,
  Wifi,
  WifiOff,
} from "lucide-react";

const NAV_ITEMS = [
  { to: "/", icon: MessageSquare, label: "对话" },
  { to: "/agents", icon: Users, label: "Agent" },
  { to: "/workspace", icon: FolderOpen, label: "工作区" },
  { to: "/config", icon: Settings, label: "配置" },
  { to: "/history", icon: History, label: "历史" },
];

interface LayoutProps {
  isConnected: boolean;
  send: (msg: ClientMessage) => void;
  children: ReactNode;
}

export function Layout({ isConnected, children }: LayoutProps) {
  return (
    <div className="flex h-screen bg-bg-base">
      <nav className="w-16 flex flex-col items-center py-4 gap-2 bg-bg-panel border-r border-gray-800">
        {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              cn(
                "flex flex-col items-center gap-0.5 w-12 py-2 rounded-lg text-xs transition-colors",
                isActive
                  ? "bg-accent/20 text-accent"
                  : "text-gray-500 hover:text-gray-300 hover:bg-gray-800"
              )
            }
          >
            <Icon size={20} />
            <span>{label}</span>
          </NavLink>
        ))}
        <div className="mt-auto">
          {isConnected ? (
            <Wifi size={18} className="text-green-400" />
          ) : (
            <WifiOff size={18} className="text-red-400" />
          )}
        </div>
      </nav>
      <main className="flex-1 overflow-hidden">{children}</main>
    </div>
  );
}
