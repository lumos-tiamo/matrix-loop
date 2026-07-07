import { Link } from "react-router-dom";

export function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 flex items-center gap-6 border-b border-line bg-bg/80 px-6 py-3 backdrop-blur">
        <Link to="/" className="font-display text-lg font-extrabold tracking-tight">
          Matrix<span className="text-lime">Loop</span>
        </Link>
        <span className="font-mono text-xs text-muted">矩阵账号 · 自我修正指挥台</span>
      </header>
      <main className="mx-auto max-w-[1500px] px-4 py-4 md:px-[22px]">{children}</main>
    </div>
  );
}
