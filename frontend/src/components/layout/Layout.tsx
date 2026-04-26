import { type ReactNode } from "react";
import { NavLink } from "react-router-dom";
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
  send: (msg: ClientMessage) => boolean;
  children: ReactNode;
  /** 桌面端后端进程启动失败时的错误信息 */
  backendError?: string | null;
}

export function Layout({ isConnected, children, backendError }: LayoutProps) {
  return (
    <div className="flex h-screen bg-bg-base">
      <nav className="w-16 flex flex-col items-center py-3 gap-2 bg-bg-panel border-r border-gray-800">
        <div className="mb-1 shrink-0" title="m-agent">
          <img
            src="/logo.png"
            alt=""
            className="h-8 w-8 rounded-md object-cover ring-1 ring-gray-700"
            width={32}
            height={32}
          />
        </div>
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
        <div className="mt-auto flex flex-col items-center gap-1" title={backendError || undefined}>
          {isConnected ? (
            <Wifi size={18} className="text-green-400" />
          ) : (
            <WifiOff size={18} className="text-red-400" />
          )}
          {backendError ? (
            <span className="text-[9px] text-red-400 max-w-14 text-center leading-tight break-words">
              后端未启动
            </span>
          ) : null}
        </div>
      </nav>
      <main className="flex-1 flex flex-col overflow-hidden min-w-0">
        {backendError ? (
          <div className="shrink-0 px-3 py-2 text-xs text-red-200 bg-red-900/30 border-b border-red-800/50">
            {backendError}
          </div>
        ) : null}
        <div className="flex-1 min-h-0 overflow-hidden">{children}</div>
      </main>
    </div>
  );
}
