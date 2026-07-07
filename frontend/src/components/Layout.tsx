import { Link, useLocation } from "react-router-dom";
import { api } from "../api/client";
import { useAsync } from "../api/hooks";
import { OpsBar } from "./OpsBar";

const NAV = [
  { to: "/", label: "总览" },
  { to: "/compare", label: "对比" },
  { to: "/content", label: "爆文库" },
];

export function Layout({ children }: { children: React.ReactNode }) {
  const { pathname } = useLocation();
  const accounts = useAsync(() => api.listAccounts(), []);

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 flex flex-wrap items-center gap-x-6 gap-y-2 border-b border-line bg-bg/80 px-6 py-3 backdrop-blur">
        <Link to="/" className="font-display text-lg font-extrabold tracking-tight">
          Matrix<span className="text-lime">Loop</span>
        </Link>
        <nav className="flex items-center gap-1">
          {NAV.map((n) => {
            const active = n.to === "/" ? pathname === "/" : pathname.startsWith(n.to);
            return (
              <Link
                key={n.to}
                to={n.to}
                className={`rounded-lg px-3 py-[6px] font-mono text-xs transition-colors ${
                  active ? "bg-lime/[.1] text-lime" : "text-muted hover:text-text"
                }`}
              >
                {n.label}
              </Link>
            );
          })}
        </nav>
        <span className="hidden font-mono text-xs text-muted lg:inline">矩阵账号 · 自我修正指挥台</span>
        <div className="flex-1" />
        <OpsBar accounts={accounts.data ?? []} onDone={() => accounts.reload()} />
      </header>
      <main className="mx-auto max-w-[1500px] px-4 py-4 md:px-[22px]">{children}</main>
    </div>
  );
}
