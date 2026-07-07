import { Link } from "react-router-dom";

export function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen">
      <header className="border-b border-line px-6 py-3 flex items-center gap-6">
        <Link to="/" className="font-display font-extrabold tracking-tight text-lg">
          Matrix<span className="text-accent">Loop</span>
        </Link>
        <span className="font-mono text-xs text-muted">矩阵账号 · 自我修正指挥台</span>
      </header>
      <main className="px-6 py-6 max-w-[1400px] mx-auto">{children}</main>
    </div>
  );
}
