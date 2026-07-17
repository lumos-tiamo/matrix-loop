import { Link, useLocation } from "react-router-dom";
import { api } from "../api/client";
import { useAsync } from "../api/hooks";
import { OpsBar } from "./OpsBar";

const NAV = [
  { to: "/", label: "飞轮", ic: "🌀" },
  { to: "/overview", label: "总览", ic: "📊" },
  { to: "/video", label: "视频", ic: "🎬" },
  { to: "/schedule", label: "排期", ic: "📅" },
  { to: "/carousels", label: "图文", ic: "🖼" },
  { to: "/flow", label: "导流", ic: "🔀" },
  { to: "/content", label: "爆文库", ic: "🔥" },
  { to: "/compare", label: "对比", ic: "⚖" },
];

export function Layout({ children }: { children: React.ReactNode }) {
  const { pathname } = useLocation();
  const accounts = useAsync(() => api.listAccounts(), []);

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 flex flex-wrap items-center gap-x-4 gap-y-2 px-6 py-3.5">
        <Link to="/" className="navpill flex items-center gap-2.5 px-4 py-2 leading-none">
          <span className="grid h-8 w-8 place-items-center rounded-full bg-gradient-to-br from-lime to-cyan text-[15px]">◆</span>
          <span className="font-display text-base font-extrabold tracking-tight">Matrix<span className="text-lime">Loop</span></span>
        </Link>
        <nav className="navpill mx-auto flex items-center gap-1 px-2 py-1.5">
          {NAV.map((n) => {
            const active = n.to === "/" ? pathname === "/" : (pathname === n.to || pathname.startsWith(n.to + "/"));
            return (
              <Link key={n.to} to={n.to}
                className={`flex items-center gap-1.5 rounded-full px-3.5 py-[7px] text-xs transition-all ${
                  active ? "bg-blue1/[.16] text-lime shadow-[0_0_0_1px_rgba(47,123,255,.5),0_0_18px_rgba(47,123,255,.25)]" : "text-muted hover:bg-white/[.05] hover:text-text"
                }`}>
                <span className="text-[13px]">{n.ic}</span><span className="hidden sm:inline">{n.label}</span>
              </Link>
            );
          })}
        </nav>
        <OpsBar accounts={accounts.data ?? []} onDone={() => accounts.reload()} />
      </header>
      <main className="mx-auto max-w-[1500px] px-4 py-4 md:px-[22px]">{children}</main>
    </div>
  );
}
