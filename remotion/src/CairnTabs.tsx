/**
 * Cairn Tabs — product demo, faithful rebuild from the real product screenshots/recording
 * (2026-07-16). Replicates the actual side-panel UI 1:1: header + 搜索/新建/设置, "N 标签 M 任务",
 * 绑定 :3000 row, 同站归类建议 banners, 重点(star) group, colored group bars, real favicons,
 * light-green PR badges, 未分类, 已归档, footer — and the real Settings panel (自动归类/陈旧/内存/
 * AI整理·自带key/导出). Narrative only shows features the product actually has. Pure code-render:
 * every string/badge/logo is real & crisp (no AI hallucination, no invented features).
 *
 * @30fps 1920x1080. Scenes: S1 0-150 | S2 150-300 | S3 300-510 | S4 510-690 | S5 690-870 |
 * S6 870-1050 | S7 1050-1230 | S8 1230-1440 | S9 1440-1620 | S10 1620-1800  (=60s).
 */
import React from "react";
import { AbsoluteFill, Sequence, interpolate, spring, useCurrentFrame, useVideoConfig, Easing } from "remotion";

export const CAIRN_FPS = 30;
export const CAIRN_DURATION = 1800; // 60s

const C = {
  desk: "#E9ECF1", chrome: "#FFFFFF", bar: "#F1F3F6", ink: "#1F2733", muted: "#9AA3AF",
  line: "#EDF0F3", green: "#17A667", greenText: "#128A54", greenBadge: "#DCF5E6",
  greenBind: "#ECF8F1", star: "#F5B301", starBg: "#FEF7E6", red: "#E5484D", amber: "#F5A623",
  blue: "#4F86F7", mono: "#8A93A5",
};
const FONT = '"PingFang SC","Hiragino Sans GB","Inter","SF Pro Text",-apple-system,system-ui,"Microsoft YaHei",sans-serif';
const MONO = '"SF Mono","JetBrains Mono",ui-monospace,Menlo,monospace';
const ease = (f: number, a: number, b: number, from: number, to: number) =>
  interpolate(f, [a, b], [from, to], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });

// ---------------------------------------------------------------- favicons (recognizable marks)
const Favicon: React.FC<{ kind: string; size?: number }> = ({ kind, size = 22 }) => {
  const box = (bg: string, node: React.ReactNode, radius = 5) => (
    <div style={{ width: size, height: size, borderRadius: radius, background: bg, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, overflow: "hidden" }}>{node}</div>
  );
  const L = (t: string, col = "#fff", fs = size * 0.6) => <span style={{ fontFamily: FONT, fontWeight: 800, fontSize: fs, color: col }}>{t}</span>;
  switch (kind) {
    case "github": return box("#1B1F24", (
      <svg width={size * 0.72} height={size * 0.72} viewBox="0 0 16 16" fill="#fff"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38v-1.34c-2.23.48-2.7-1.07-2.7-1.07-.36-.93-.89-1.18-.89-1.18-.73-.5.06-.49.06-.49.8.06 1.23.83 1.23.83.72 1.23 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.83-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82a7.6 7.6 0 0 1 4 0c1.53-1.03 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.52.56.83 1.28.83 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48v2.2c0 .21.15.46.55.38A8 8 0 0 0 16 8c0-4.42-3.58-8-8-8Z" /></svg>
    ));
    case "react": return box("#15191E", (
      <svg width={size * 0.82} height={size * 0.82} viewBox="0 0 24 24" fill="none" stroke="#61DAFB" strokeWidth="1"><circle cx="12" cy="12" r="2" fill="#61DAFB" stroke="none" /><g><ellipse cx="12" cy="12" rx="10" ry="4" /><ellipse cx="12" cy="12" rx="10" ry="4" transform="rotate(60 12 12)" /><ellipse cx="12" cy="12" rx="10" ry="4" transform="rotate(120 12 12)" /></g></svg>
    ));
    case "so": return box("#F48024", <svg width={size * 0.7} height={size * 0.7} viewBox="0 0 24 24" fill="#fff"><path d="M17 21v-6h2v8H3v-8h2v6h12Z" /><path d="M6.5 15.5l.4-2 8 1.7-.4 2-8-1.7Zm.9-4.2l.8-1.9 7.4 3.2-.8 1.8-7.4-3.1Zm1.8-4l1.2-1.6 6.1 4.6-1.2 1.6-6.1-4.6ZM14 3l4.8 6.4-1.6 1.2L12.4 4.2 14 3Z" /></svg>);
    case "mdn": return box("#000", <span style={{ fontFamily: FONT, fontWeight: 900, fontSize: size * 0.52, color: "#fff" }}>M</span>);
    case "hn": return box("#FF6600", L("Y", "#fff", size * 0.62));
    case "bitbucket": return box("#2684FF", <span style={{ color: "#fff", fontWeight: 800, fontSize: size * 0.6 }}>{"{ }".slice(0, 1)}</span>);
    case "vscode": return box("#0A66C2", L("V", "#fff", size * 0.58));
    case "localhost": return box("#D6409F", L("L"));
    case "qa": return box("#15191E", <span style={{ color: C.green, fontSize: size * 0.6 }}>✦</span>);
    case "elevate": return box("linear-gradient(135deg,#5B8DEF,#C86DD7)", <span style={{ color: "#fff", fontSize: size * 0.5, fontWeight: 800 }}>◔</span>, size / 2);
    case "claude": return box("#D97757", L("C"));
    default: return box("#C7CDD8", null);
  }
};

// ---------------------------------------------------------------- small parts
const PRBadge: React.FC<{ t: string }> = ({ t }) => (
  <span style={{ display: "inline-flex", alignItems: "center", gap: 4, background: C.greenBadge, color: C.greenText,
    fontFamily: FONT, fontWeight: 700, fontSize: 13, padding: "3px 8px", borderRadius: 7, flexShrink: 0 }}>
    <svg width="11" height="11" viewBox="0 0 16 16" fill={C.greenText}><path d="M5 3a2 2 0 1 0-2.83 1.82v6.36a2 2 0 1 0 1.66 0V8.6c.5.26 1.07.4 1.67.4H9a2 2 0 0 0 2-2V4.82a2 2 0 1 0-1.66 0V7a.5.5 0 0 1-.5.5H5.5c-.6 0-1.17.14-1.67.4V4.82C4.42 4.5 5 3.8 5 3Z" /></svg>{t}
  </span>
);
const Star: React.FC<{ on?: boolean }> = ({ on = true }) => (
  <span style={{ color: on ? C.star : "#D4D9E0", fontSize: 17, flexShrink: 0 }}>★</span>
);

type Item = { fav: string; title: string; pr?: string; star?: boolean; port?: string };
const TabRow: React.FC<{ it: Item; dim?: number; highlight?: number }> = ({ it, dim = 1, highlight = 0 }) => (
  <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "7px 8px", borderRadius: 8, opacity: dim,
    background: highlight ? `rgba(23,166,103,${0.10 * highlight})` : "transparent" }}>
    <Favicon kind={it.fav} />
    <span style={{ fontFamily: FONT, fontSize: 15.5, color: C.ink, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", flex: 1 }}>{it.title}</span>
    {it.pr && <PRBadge t={it.pr} />}
    {it.port && <span style={{ fontFamily: MONO, fontSize: 13, color: C.mono, flexShrink: 0 }}>{it.port}</span>}
    {it.star && <Star />}
  </div>
);

const GroupHeader: React.FC<{ name: string; color?: string; count: number; star?: boolean; actions?: boolean; open?: boolean }> = ({ name, color, count, star, actions, open = true }) => (
  <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 4px" }}>
    {color && <div style={{ width: 4, height: 20, borderRadius: 3, background: color }} />}
    {star && <span style={{ color: C.star, fontSize: 16 }}>★</span>}
    <span style={{ color: C.muted, fontSize: 13, width: 10 }}>{open ? "⌄" : "›"}</span>
    <span style={{ fontFamily: FONT, fontWeight: 700, fontSize: 17, color: C.ink }}>{name}</span>
    {actions && <span style={{ marginLeft: 10, fontFamily: FONT, fontSize: 13, color: C.muted }}>改名 导出 归档 删</span>}
    <span style={{ marginLeft: "auto", fontFamily: FONT, fontSize: 14, color: C.muted }}>{count}</span>
  </div>
);

const Banner: React.FC<{ site: string; n: number; op?: number; clicked?: boolean }> = ({ site, n, op = 1, clicked }) => (
  <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "9px 10px", background: C.greenBind, borderRadius: 9, marginBottom: 6, opacity: op }}>
    <span style={{ fontFamily: FONT, fontSize: 14.5, color: C.ink }}>同站 <b>{site}</b> · {n} 个</span>
    <span style={{ marginLeft: "auto", fontFamily: FONT, fontSize: 14, fontWeight: 700, color: clicked ? "#fff" : C.greenText, background: clicked ? C.green : "transparent", padding: "3px 12px", borderRadius: 7 }}>归类</span>
    <span style={{ fontFamily: FONT, fontSize: 14, color: C.muted }}>忽略</span>
  </div>
);

// ---------------------------------------------------------------- the side panel shell
const Panel: React.FC<{ children: React.ReactNode; tabs?: string; tasks?: string; search?: string; scroll?: number }> = ({
  children, tabs = "15", tasks = "3", search = "搜索标签...", scroll = 0,
}) => (
  <div style={{ position: "absolute", top: 0, right: 0, bottom: 0, width: 620, background: C.chrome, boxShadow: "-24px 0 60px rgba(30,40,60,0.10)", display: "flex", flexDirection: "column", overflow: "hidden" }}>
    {/* header */}
    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "18px 20px 12px" }}>
      <CairnMark size={22} />
      <span style={{ fontFamily: FONT, fontWeight: 700, fontSize: 21, color: C.ink }}>Cairn Tabs</span>
      <span style={{ marginLeft: "auto", color: C.muted, fontSize: 18 }}>⇲</span>
      <span style={{ color: C.muted, fontSize: 20 }}>✕</span>
    </div>
    {/* search row */}
    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "0 20px 12px" }}>
      <div style={{ flex: 1, display: "flex", alignItems: "center", gap: 8, background: "#F4F6F8", borderRadius: 10, padding: "9px 12px" }}>
        <span style={{ color: C.muted, fontSize: 15 }}>🔍</span>
        <span style={{ fontFamily: FONT, fontSize: 15, color: search === "搜索标签..." ? C.muted : C.ink }}>{search}</span>
        <span style={{ marginLeft: "auto", fontFamily: FONT, fontSize: 13, color: C.muted }}>⌘⇧K</span>
      </div>
      <span style={{ fontFamily: FONT, fontSize: 15, fontWeight: 600, color: C.greenText }}>+ 新建</span>
      <span style={{ color: C.muted, fontSize: 16 }}>⌃</span>
      <span style={{ color: C.muted, fontSize: 17 }}>⚙</span>
    </div>
    {/* meta */}
    <div style={{ padding: "10px 20px", borderTop: `1px solid ${C.line}`, borderBottom: `1px solid ${C.line}` }}>
      <span style={{ fontFamily: FONT, fontSize: 15, color: C.muted }}>{tabs} 标签{"   "}{tasks} 任务</span>
    </div>
    {/* body (scrollable) */}
    <div style={{ flex: 1, padding: "10px 16px", transform: `translateY(${-scroll}px)` }}>{children}</div>
  </div>
);

const CairnMark: React.FC<{ size?: number; built?: number }> = ({ size = 22, built = 1 }) => {
  const stones = [
    { w: 1.0, y: 0.78, c: "#3E7D5C" }, { w: 0.8, y: 0.6, c: "#1B9E63" },
    { w: 0.62, y: 0.43, c: "#2FB077" }, { w: 0.46, y: 0.27, c: "#57C495" }, { w: 0.32, y: 0.13, c: "#86D6B2" },
  ];
  return (
    <svg width={size} height={size} viewBox="0 0 100 100">
      {stones.map((s, i) => (built >= (i + 1) / stones.length - 0.001) && (
        <rect key={i} x={50 - s.w * 42} y={s.y * 100} rx={9} width={s.w * 84} height={14} fill={s.c} />
      ))}
    </svg>
  );
};

// ---------------------------------------------------------------- browser chrome context (behind panel)
// loose (pre-grouping) individual tabs
const CHROME_TABS: [string, string][] = [
  ["react/re", "react"], ["Convert", "github"], ["Convert", "github"], ["microso", "vscode"],
  ["404 — B", "bitbucket"], ["Quick S", "react"], ["JavaSc", "mdn"], ["java - W", "so"],
  ["iterator", "so"], ["How to", "so"], ["localho", "localhost"], ["Hacker", "hn"],
  ["QA Pl", "qa"], ["Elevate", "elevate"], ["claude", "claude"],
];
// native Chrome tab-groups shown AFTER grouping (mirrors the real screenshot)
const TAB_GROUPS: { name: string; color: string; favs: string[] }[] = [
  { name: "React Dev", color: "#4F86F7", favs: ["react", "github", "github", "github"] },
  { name: "JS & Python", color: "#F5A623", favs: ["so", "mdn", "so", "so"] },
  { name: "本地开发", color: "#16B8A6", favs: ["localhost"] },
  { name: "Hacker News", color: "#2E9E6B", favs: ["hn"] },
  { name: "QA Platform", color: "#E5484D", favs: ["qa", "elevate"] },
  { name: "查看代码提交", color: "#5A6472", favs: ["bitbucket"] },
  { name: "claude.ai", color: "#8B5CF6", favs: ["claude"] },
];

// one native tab-group pill: colored label + its tabs on a colored underline; `p` (0..1) drives entrance
const TabGroupPill: React.FC<{ g: { name: string; color: string; favs: string[] }; p: number }> = ({ g, p }) => (
  <div style={{ display: "flex", alignItems: "flex-end", gap: 2, opacity: p }}>
    <div style={{ display: "flex", alignItems: "center", gap: 4, background: g.color, color: "#fff", fontFamily: FONT,
      fontWeight: 700, fontSize: 12, height: 26, padding: "0 9px", borderRadius: "8px 8px 0 0",
      transform: `scaleX(${interpolate(p, [0, 1], [0.4, 1])})`, transformOrigin: "left", whiteSpace: "nowrap" }}>
      {g.name}
    </div>
    <div style={{ display: "flex", alignItems: "flex-end", gap: 2, borderBottom: `3px solid ${g.color}`, background: `${g.color}14`, borderRadius: "6px 6px 0 0", padding: "0 3px", overflow: "hidden", width: `${interpolate(p, [0.2, 1], [0, g.favs.length * 26 + 6], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })}px` }}>
      {g.favs.map((fav, i) => (
        <div key={i} style={{ width: 24, height: 30, display: "flex", alignItems: "center", justifyContent: "center", background: i === 0 ? "#fff" : "transparent", borderRadius: "6px 6px 0 0" }}>
          <Favicon kind={fav} size={15} />
        </div>
      ))}
    </div>
  </div>
);

const BrowserBg: React.FC<{ panelW?: number; grouped?: number; url?: string }> = ({ panelW = 620, grouped = 1, url }) => (
  <AbsoluteFill style={{ background: C.desk }}>
    {/* tab bar — morphs from loose tabs (grouped=0) to native colored tab-groups (grouped=1) */}
    <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 44, background: C.bar, display: "flex", alignItems: "flex-end", padding: "0 12px", gap: 4 }}>
      <div style={{ display: "flex", gap: 8, alignSelf: "center", marginRight: 10 }}>
        {["#FF5F57", "#FEBC2E", "#28C840"].map((c) => <div key={c} style={{ width: 12, height: 12, borderRadius: 6, background: c }} />)}
      </div>
      {/* loose tabs fade out as grouping happens */}
      {grouped < 0.6 && (
        <div style={{ display: "flex", gap: 3, alignItems: "flex-end", opacity: interpolate(grouped, [0, 0.5], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }), position: grouped > 0 ? "absolute" : "relative", left: grouped > 0 ? 76 : undefined, bottom: grouped > 0 ? 0 : undefined }}>
          {CHROME_TABS.map(([t, fav], i) => (
            <div key={i} style={{ width: 84, height: 32, background: i === 8 ? "#fff" : "transparent", borderRadius: "8px 8px 0 0", display: "flex", alignItems: "center", gap: 5, padding: "0 8px", opacity: i === 8 ? 1 : 0.7 }}>
              <Favicon kind={fav} size={13} />
              <span style={{ fontFamily: FONT, fontSize: 12, color: C.ink, whiteSpace: "nowrap", overflow: "hidden" }}>{t}</span>
            </div>
          ))}
        </div>
      )}
      {/* grouped pills appear, staggered */}
      {grouped > 0 && (
        <div style={{ display: "flex", gap: 8, alignItems: "flex-end" }}>
          {TAB_GROUPS.map((g, i) => (
            <TabGroupPill key={g.name} g={g} p={interpolate(grouped, [i * 0.05, i * 0.05 + 0.45], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })} />
          ))}
        </div>
      )}
      <span style={{ marginLeft: "auto", color: C.muted, fontSize: 18, alignSelf: "center" }}>＋</span>
    </div>
    {/* url bar */}
    <div style={{ position: "absolute", top: 44, left: 0, right: 0, height: 40, background: "#fff", borderBottom: `1px solid ${C.line}`, display: "flex", alignItems: "center", gap: 12, padding: "0 16px" }}>
      <span style={{ color: C.muted, fontSize: 15 }}>‹ › ⟳</span>
      <div style={{ flex: 1, background: "#F1F3F6", borderRadius: 14, padding: "6px 14px", fontFamily: FONT, fontSize: 13, color: "#5A6472", maxWidth: 1000 }}>{url || "stackoverflow.com/questions/231767/what-does-the-yield-keyword-do-in-python"}</div>
      <span style={{ fontFamily: FONT, fontSize: 12, color: "#fff", background: "#7A828F", padding: "3px 8px", borderRadius: 6 }}>H 工作</span>
      <span style={{ fontFamily: FONT, fontSize: 12, color: "#fff", background: C.green, padding: "4px 10px", borderRadius: 7 }}>重新启动即可更新</span>
    </div>
    {/* faint page area on the left of the docked panel */}
    <div style={{ position: "absolute", top: 84, left: 0, bottom: 0, right: panelW, background: "#FBFCFD" }}>
      <div style={{ padding: 40, opacity: 0.5 }}>
        <div style={{ fontFamily: FONT, fontSize: 26, fontWeight: 700, color: "#C0C7D0" }}>Stack Overflow</div>
        {[92, 78, 85, 60, 88, 70, 82].map((w, i) => <div key={i} style={{ height: 12, width: `${w * 0.7}%`, background: "#EAEDF1", borderRadius: 6, margin: "18px 0" }} />)}
      </div>
    </div>
  </AbsoluteFill>
);

// caption
const Caption: React.FC<{ text: string; sub?: string; len: number }> = ({ text, sub, len }) => {
  const f = useCurrentFrame();
  const op = interpolate(f, [4, 14, len - 12, len - 2], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <div style={{ position: "absolute", left: 0, right: 620, bottom: 66, display: "flex", justifyContent: "center", opacity: op }}>
      <div style={{ textAlign: "center", transform: `translateY(${ease(f, 4, 16, 20, 0)}px)` }}>
        <div style={{ display: "inline-block", background: "rgba(22,28,38,0.88)", color: "#fff", fontFamily: FONT, fontWeight: 600, fontSize: 38, padding: "15px 28px", borderRadius: 15, boxShadow: "0 12px 34px rgba(0,0,0,0.22)" }}>{text}</div>
        {sub && <div style={{ marginTop: 10, color: "#6B7480", fontFamily: FONT, fontSize: 24, fontWeight: 500 }}>{sub}</div>}
      </div>
    </div>
  );
};

const Cursor: React.FC<{ x: number; y: number; clickAt?: number }> = ({ x, y, clickAt }) => {
  const f = useCurrentFrame();
  const ring = clickAt != null && f >= clickAt && f < clickAt + 16;
  const r = ring ? interpolate(f, [clickAt!, clickAt! + 16], [4, 30]) : 0;
  const ro = ring ? interpolate(f, [clickAt!, clickAt! + 16], [0.5, 0]) : 0;
  return (
    <div style={{ position: "absolute", left: x, top: y, zIndex: 60 }}>
      {ring && <div style={{ position: "absolute", left: -r, top: -r, width: r * 2, height: r * 2, borderRadius: r, border: `3px solid ${C.green}`, opacity: ro }} />}
      <svg width="28" height="28" viewBox="0 0 24 24" style={{ filter: "drop-shadow(0 2px 3px rgba(0,0,0,.3))" }}><path d="M3 2 L3 20 L8 15 L11 22 L14 21 L11 14 L18 14 Z" fill="#fff" stroke="#1E2430" strokeWidth="1.4" strokeLinejoin="round" /></svg>
    </div>
  );
};

// item pools reflecting the real product
const IT = {
  qa: { fav: "qa", title: "QA Platform · Agent 评测", star: true } as Item,
  elevate: { fav: "elevate", title: "ElevateSphere AIG", star: true } as Item,
  soContains: { fav: "so", title: "How to check whether a string contains a …" } as Item,
  mdn: { fav: "mdn", title: "JavaScript | MDN" } as Item,
  soDetect: { fav: "so", title: "javascript - How to detect Safari, Chrome, …" } as Item,
  soJava: { fav: "so", title: "java - Why is conditional processing of a s…" } as Item,
  soYield: { fav: "so", title: 'iterator - What does the "yield" keyword d…' } as Item,
  reactStart: { fav: "react", title: "Quick Start – React" } as Item,
  reactRepo: { fav: "github", title: "react/react: The library for web and native …" } as Item,
  pr1: { fav: "github", title: "Convert ReactFreshMultipl…", pr: "PR #28000" } as Item,
  pr2: { fav: "github", title: "Convert describeCompone…", pr: "PR #28001" } as Item,
  vscode: { fav: "vscode", title: "microsoft/vscode: Visual Studio Code" } as Item,
  bitbucket: { fav: "bitbucket", title: "404 — Bitbucket", pr: "PR #1" } as Item,
  localhost: { fav: "localhost", title: "localhost", port: ":3000" } as Item,
  hn: { fav: "hn", title: "Hacker News" } as Item,
};

// ===================================================================================== scenes
// S1 — chaos: everything in 未分类, banners waiting
const S1: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill>
      <BrowserBg grouped={0} />
      <Panel tabs="17" tasks="0">
        <Banner site="stackoverflow.com" n={4} />
        <Banner site="github.com" n={4} />
        <GroupHeader name="未分类" count={13} />
        {[IT.qa, IT.reactRepo, IT.pr1, IT.pr2, IT.vscode, IT.bitbucket, IT.reactStart, IT.mdn, IT.soJava, IT.soYield, IT.soContains, IT.localhost, IT.hn]
          .map((it, i) => <TabRow key={i} it={{ ...it, star: false }} />)}
      </Panel>
      <div style={{ position: "absolute", top: 96, right: 40, fontFamily: FONT, color: C.red, fontSize: 17, fontWeight: 700, opacity: ease(f, 26, 50, 0, 1) }}>标签 42 · 已溢出</div>
      <Caption text="标签又爆了?" len={150} />
    </AbsoluteFill>
  );
};

// S2 — identity: the panel, cairn mark
const S2: React.FC = () => {
  const f = useCurrentFrame();
  const pop = spring({ frame: f, fps: 30, config: { damping: 200 }, durationInFrames: 20 });
  return (
    <AbsoluteFill>
      <BrowserBg grouped={0} />
      <Panel tabs="17" tasks="3">
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: 420, gap: 20, transform: `scale(${interpolate(pop, [0, 1], [0.9, 1])})`, opacity: ease(f, 4, 18, 0, 1) }}>
          <CairnMark size={92} />
          <span style={{ fontFamily: FONT, fontWeight: 800, fontSize: 40, color: C.ink }}>Cairn Tabs</span>
          <span style={{ fontFamily: FONT, fontSize: 20, color: C.muted }}>为标签立个路标</span>
        </div>
      </Panel>
      <Caption text="Cairn Tabs · 为标签立个路标" len={150} />
    </AbsoluteFill>
  );
};

// S3 — auto-group: dev tabs settle into React Dev / JS & Python
const S3: React.FC = () => {
  const f = useCurrentFrame();
  const rev = ease(f, 20, 140, 0, 1);
  const reactItems = [IT.reactStart, IT.reactRepo, IT.pr1, IT.pr2];
  const jsItems = [IT.soContains, IT.mdn, IT.soDetect, IT.soJava, IT.soYield];
  return (
    <AbsoluteFill>
      <BrowserBg grouped={ease(f, 24, 140, 0, 1)} />
      <Panel tabs="17" tasks="3">
        <GroupHeader name="React Dev" color={C.blue} count={4} />
        {reactItems.slice(0, Math.ceil(reactItems.length * rev)).map((it, i) => (
          <div key={i} style={{ transform: `translateX(${ease(f, 20 + i * 12, 44 + i * 12, 26, 0)}px)`, opacity: ease(f, 20 + i * 12, 44 + i * 12, 0, 1) }}><TabRow it={it} highlight={interpolate((f - (20 + i * 12)) % 200, [0, 14, 34], [0, 1, 0], { extrapolateRight: "clamp" })} /></div>
        ))}
        <div style={{ height: 8 }} />
        <GroupHeader name="JS & Python" color={C.amber} count={5} />
        {jsItems.slice(0, Math.ceil(jsItems.length * rev)).map((it, i) => (
          <div key={i} style={{ transform: `translateX(${ease(f, 60 + i * 12, 84 + i * 12, 26, 0)}px)`, opacity: ease(f, 60 + i * 12, 84 + i * 12, 0, 1) }}><TabRow it={it} /></div>
        ))}
      </Panel>
      <Caption text="新标签,自动归到对的任务" len={210} />
    </AbsoluteFill>
  );
};

// S4 — same-site suggestion → click 归类
const S4: React.FC = () => {
  const f = useCurrentFrame();
  const clicked = f > 96;
  const grouped = f > 110;
  return (
    <AbsoluteFill>
      <BrowserBg />
      <Panel tabs="17" tasks={grouped ? "4" : "3"}>
        {!grouped ? <Banner site="stackoverflow.com" n={4} clicked={clicked} /> : (
          <div style={{ opacity: ease(f, 110, 124, 0, 1) }}>
            <GroupHeader name="JS & Python" color={C.amber} count={5} />
            {[IT.soContains, IT.mdn, IT.soDetect, IT.soJava, IT.soYield].map((it, i) => <TabRow key={i} it={it} />)}
          </div>
        )}
        {!grouped && <>
          <GroupHeader name="未分类" count={9} />
          {[IT.soContains, IT.soDetect, IT.soJava, IT.soYield].map((it, i) => <TabRow key={i} it={it} dim={0.9} />)}
        </>}
      </Panel>
      <Cursor x={interpolate(f, [30, 92], [1600, 1831], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })} y={interpolate(f, [30, 92], [540, 188], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })} clickAt={96} />
      <Caption text="成组要你点头,绝不自作主张" len={180} />
    </AbsoluteFill>
  );
};

// S5 — dev badges
const S5: React.FC = () => {
  const f = useCurrentFrame();
  const rows = [IT.pr1, IT.pr2, IT.bitbucket, IT.localhost, IT.qa];
  return (
    <AbsoluteFill>
      <BrowserBg />
      <Panel tabs="17" tasks="4">
        <GroupHeader name="React Dev" color={C.blue} count={4} actions />
        {rows.map((it, i) => (
          <div key={i} style={{ opacity: ease(f, 14 + i * 16, 38 + i * 16, 0, 1), transform: `translateX(${ease(f, 14 + i * 16, 38 + i * 16, 16, 0)}px)` }}><TabRow it={it} highlight={it.pr || it.port ? interpolate((f - (14 + i * 16)), [10, 24, 44], [0, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) : 0} /></div>
        ))}
      </Panel>
      <Caption text="PR / Issue / 本地端口,一眼认得" len={180} />
    </AbsoluteFill>
  );
};

// S6 — 重点 starring (real feature, replaces invented dedup)
const S6: React.FC = () => {
  const f = useCurrentFrame();
  const pinned = f > 80;
  return (
    <AbsoluteFill>
      <BrowserBg />
      <Panel tabs="15" tasks="3">
        <div style={{ background: C.starBg, borderRadius: 12, padding: "8px 8px 4px", marginBottom: 10, opacity: pinned ? ease(f, 80, 96, 0, 1) : 0, transform: `translateY(${pinned ? ease(f, 80, 96, -10, 0) : -10}px)` }}>
          <GroupHeader name="重点" count={2} star />
          <TabRow it={IT.qa} />
          <TabRow it={IT.elevate} />
        </div>
        <GroupHeader name="QA Platform" color={C.red} count={2} />
        <TabRow it={{ ...IT.qa, star: f > 50 }} highlight={interpolate(f, [40, 54, 74], [0, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })} />
        <TabRow it={{ ...IT.elevate, star: f > 66 }} highlight={interpolate(f, [56, 70, 90], [0, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })} />
      </Panel>
      <Cursor x={interpolate(f, [20, 46], [1400, 1882], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })} y={interpolate(f, [20, 46], [480, 356], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })} clickAt={50} />
      <Caption text="重点标签,一键置顶" len={180} />
    </AbsoluteFill>
  );
};

// S7 — search
const S7: React.FC = () => {
  const f = useCurrentFrame();
  const q = "react".slice(0, Math.max(0, Math.floor((f - 16) / 6)));
  const all = [IT.reactStart, IT.reactRepo, IT.pr1, IT.pr2, IT.mdn, IT.soJava, IT.hn];
  const hits = q ? all.filter((it) => it.title.toLowerCase().includes(q) || it.title.includes("React")) : all;
  return (
    <AbsoluteFill>
      <BrowserBg />
      <Panel tabs="15" tasks="3" search={q ? q : "搜索标签..."}>
        {(q ? hits : all).map((it, i) => <div key={i} style={{ opacity: ease(f, 0, 8, 1, 1) }}><TabRow it={it} highlight={q && i === 0 ? 1 : 0} /></div>)}
      </Panel>
      <Cursor x={1480} y={78} clickAt={10} />
      <Caption text="⌘⇧K,秒搜所有标签" len={180} />
    </AbsoluteFill>
  );
};

// S8 — Settings / AI 整理 (faithful to screenshot #3)
const Toggle: React.FC<{ on: boolean }> = ({ on }) => (
  <div style={{ width: 44, height: 26, borderRadius: 13, background: on ? C.green : "#D4D9E0", display: "flex", alignItems: "center", padding: 3, justifyContent: on ? "flex-end" : "flex-start" }}>
    <div style={{ width: 20, height: 20, borderRadius: 10, background: "#fff" }} />
  </div>
);
const SettingCard: React.FC<{ title: React.ReactNode; desc: string; right: React.ReactNode }> = ({ title, desc, right }) => (
  <div style={{ background: "#F7F9FB", borderRadius: 12, padding: 16, marginBottom: 12, display: "flex", alignItems: "flex-start", gap: 12 }}>
    <div style={{ flex: 1 }}>
      <div style={{ fontFamily: FONT, fontWeight: 700, fontSize: 17, color: C.ink }}>{title}</div>
      <div style={{ fontFamily: FONT, fontSize: 13.5, color: C.muted, marginTop: 6, lineHeight: 1.5 }}>{desc}</div>
    </div>
    <div style={{ flexShrink: 0, paddingTop: 2 }}>{right}</div>
  </div>
);
const Stepper: React.FC<{ n: number }> = ({ n }) => (
  <div style={{ display: "flex", alignItems: "center", gap: 6, fontFamily: FONT }}>
    <span style={{ width: 30, height: 30, borderRadius: 8, border: `1px solid ${C.line}`, display: "flex", alignItems: "center", justifyContent: "center", color: C.muted }}>−</span>
    <span style={{ fontSize: 17, color: C.ink, width: 20, textAlign: "center" }}>{n}</span>
    <span style={{ width: 30, height: 30, borderRadius: 8, border: `1px solid ${C.line}`, display: "flex", alignItems: "center", justifyContent: "center", color: C.muted }}>+</span>
  </div>
);
const S8: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill>
      <BrowserBg />
      <Panel tabs="15" tasks="3">
        <div style={{ display: "flex", alignItems: "center", marginBottom: 14, opacity: ease(f, 2, 12, 0, 1) }}>
          <span style={{ fontFamily: FONT, fontWeight: 700, fontSize: 20, color: C.ink }}>⚙ 设置</span>
          <span style={{ marginLeft: "auto", fontFamily: FONT, fontSize: 16, color: C.greenText, fontWeight: 600 }}>完成</span>
        </div>
        <div style={{ opacity: ease(f, 10, 22, 0, 1) }}>
          <div style={{ fontFamily: FONT, fontSize: 13, color: C.muted, margin: "4px 4px 8px" }}>自动归类</div>
          <SettingCard title="自动归类" desc="把相关新标签自动归入任务,并在标签栏建立对应分组。" right={<Toggle on />} />
          <SettingCard title="同站归类建议" desc="未分类里同一网站的标签达到这个数,就建议归成一个任务。" right={<Stepper n={4} />} />
          <div style={{ fontFamily: FONT, fontSize: 13, color: C.muted, margin: "10px 4px 8px" }}>AI 整理</div>
          <div style={{ background: "#F7F9FB", borderRadius: 12, padding: 16, opacity: ease(f, 40, 60, 0, 1) }}>
            <div style={{ fontFamily: FONT, fontSize: 13.5, color: C.muted, lineHeight: 1.5 }}>自带 API key,用你的 key 直连你选的服务商。只把标签标题、域名、任务名发出去,<b style={{ color: C.greenText }}>绝不发完整网址或页面内容</b>。</div>
            <div style={{ display: "flex", gap: 10, margin: "12px 0" }}>
              {["Anthropic", "OpenAI", "自定义中转站"].map((t, i) => <span key={t} style={{ fontFamily: FONT, fontSize: 14, fontWeight: 600, color: i === 0 ? C.greenText : C.muted, background: i === 0 ? C.greenBadge : "transparent", padding: "6px 12px", borderRadius: 8 }}>{t}</span>)}
            </div>
            <div style={{ background: "#fff", border: `1px solid ${C.line}`, borderRadius: 9, padding: "10px 12px", fontFamily: FONT, fontSize: 14, color: C.muted, marginBottom: 10 }}>Anthropic API key</div>
            <span style={{ fontFamily: FONT, fontSize: 15, fontWeight: 700, color: "#fff", background: C.green, padding: "9px 18px", borderRadius: 9 }}>保存并启用</span>
          </div>
        </div>
      </Panel>
      <Caption text="AI 用你的 key" sub="标题域名任务名才发出去 · 数据只在本地" len={210} />
    </AbsoluteFill>
  );
};

// S9 — archive
const S9: React.FC = () => {
  const f = useCurrentFrame();
  const archived = f > 66;
  return (
    <AbsoluteFill>
      <BrowserBg />
      <Panel tabs={archived ? "11" : "15"} tasks={archived ? "2" : "3"}>
        {!archived ? (
          <div style={{ transform: `translateX(${ease(f, 48, 66, 0, 640)}px)`, opacity: ease(f, 54, 66, 1, 0) }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 4px" }}>
              <div style={{ width: 4, height: 20, borderRadius: 3, background: C.blue }} />
              <span style={{ fontFamily: FONT, fontWeight: 700, fontSize: 17, color: C.ink }}>React Dev</span>
              <span style={{ marginLeft: "auto", fontFamily: FONT, fontSize: 13, color: C.muted }}>改名 导出 <b style={{ color: C.greenText }}>归档</b> 删</span>
            </div>
            {[IT.reactStart, IT.reactRepo, IT.pr1, IT.pr2].map((it, i) => <TabRow key={i} it={it} />)}
          </div>
        ) : (
          <>
            <div style={{ fontFamily: FONT, fontSize: 14, color: C.muted, margin: "6px 4px 10px", opacity: ease(f, 66, 78, 0, 1) }}>已归档</div>
            {[{ t: "React Dev", s: "react.dev · github.com ×4", n: 4 }, { t: "查看代码提交", s: "bitbucket.org ×1", n: 1 }, { t: "github", s: "github.com ×4", n: 4 }].map((g, i) => (
              <div key={i} style={{ padding: "10px 6px", opacity: ease(f, 68 + i * 8, 82 + i * 8, 0, 1) }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ color: C.muted, fontSize: 13 }}>›</span>
                  <span style={{ fontFamily: FONT, fontWeight: 600, fontSize: 16, color: C.ink }}>{g.t}</span>
                  <span style={{ marginLeft: "auto", fontFamily: FONT, fontSize: 14, color: C.muted }}>{g.n}</span>
                </div>
                <div style={{ fontFamily: MONO, fontSize: 12.5, color: C.mono, marginLeft: 22, marginTop: 3 }}>{g.s}</div>
              </div>
            ))}
          </>
        )}
      </Panel>
      {archived && <div style={{ position: "absolute", bottom: 120, left: "50%", transform: "translateX(-50%)", marginRight: 310, background: "rgba(22,28,38,0.9)", color: "#fff", fontFamily: FONT, fontSize: 20, padding: "12px 22px", borderRadius: 12, opacity: ease(f, 66, 80, 0, 1) }}>已归档 · 随时恢复</div>}
      <Cursor x={interpolate(f, [12, 40], [1450, 1818], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })} y={interpolate(f, [12, 40], [360, 185], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })} clickAt={44} />
      <Caption text="整组一键归档,随时恢复" len={180} />
    </AbsoluteFill>
  );
};

// S10 — outro
const S10: React.FC = () => {
  const f = useCurrentFrame();
  const built = ease(f, 16, 100, 0, 1);
  return (
    <AbsoluteFill style={{ background: "linear-gradient(180deg,#F6FBF8 0%,#E7F6EE 100%)" }}>
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 28 }}>
        <div style={{ transform: "scale(1.7)" }}><CairnMark size={120} built={built} /></div>
        <span style={{ fontFamily: FONT, fontWeight: 800, fontSize: 82, color: C.ink, opacity: ease(f, 100, 120, 0, 1) }}>Cairn Tabs</span>
        <div style={{ display: "flex", gap: 16, alignItems: "center", opacity: ease(f, 130, 158, 0, 1) }}>
          {["本地优先", "无账号", "开源"].map((t, i) => (
            <React.Fragment key={t}>{i > 0 && <span style={{ color: C.green }}>·</span>}
              <span style={{ fontFamily: FONT, fontSize: 30, color: C.greenText, fontWeight: 600 }}>{t}</span></React.Fragment>
          ))}
        </div>
      </div>
    </AbsoluteFill>
  );
};

export const CairnTabs: React.FC = () => (
  <AbsoluteFill style={{ background: C.desk }}>
    <Sequence from={0} durationInFrames={150}><S1 /></Sequence>
    <Sequence from={150} durationInFrames={150}><S2 /></Sequence>
    <Sequence from={300} durationInFrames={210}><S3 /></Sequence>
    <Sequence from={510} durationInFrames={180}><S4 /></Sequence>
    <Sequence from={690} durationInFrames={180}><S5 /></Sequence>
    <Sequence from={870} durationInFrames={180}><S6 /></Sequence>
    <Sequence from={1050} durationInFrames={180}><S7 /></Sequence>
    <Sequence from={1230} durationInFrames={210}><S8 /></Sequence>
    <Sequence from={1440} durationInFrames={180}><S9 /></Sequence>
    <Sequence from={1620} durationInFrames={180}><S10 /></Sequence>
  </AbsoluteFill>
);
