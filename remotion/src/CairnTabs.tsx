/**
 * Cairn Tabs — product demo (10 scenes, ~56s, 1920x1080).
 * Pure code-rendered motion graphics: real readable UI text, real badges, no AI hallucination,
 * no fake logos — meets the brief's hard constraints (无乱码/无假logo/无廉价感). Standalone
 * composition; unrelated to the matrix-loop BrandVideo pipeline.
 *
 * Timeline @30fps: S1 0-150 | S2 150-270 | S3 270-480 | S4 480-630 | S5 630-780 |
 * S6 780-930 | S7 930-1110 | S8 1110-1290 | S9 1290-1440 | S10 1440-1680.
 */
import React from "react";
import {
  AbsoluteFill, Sequence, interpolate, spring, useCurrentFrame, useVideoConfig, Easing,
} from "remotion";

export const CAIRN_FPS = 30;
export const CAIRN_DURATION = 1680; // 56s

// ---- design tokens ---------------------------------------------------------
const C = {
  desk: "#EEF1F5",
  chrome: "#FFFFFF",
  chromeBar: "#F3F5F8",
  ink: "#1E2430",
  muted: "#8A93A5",
  line: "#E4E8EE",
  green: "#2E9E6B",
  greenSoft: "#E7F6EE",
  blue: "#4F86F7",
  amber: "#F0A93B",
  purple: "#8B5CF6",
  teal: "#16B8A6",
  danger: "#E4632C",
};
const FONT =
  '"PingFang SC","Hiragino Sans GB","Inter","SF Pro Display",-apple-system,system-ui,"Segoe UI",Roboto,"Microsoft YaHei",sans-serif';

const GROUPS = [
  { name: "前端开发", color: C.blue },
  { name: "工作", color: C.amber },
  { name: "阅读稍后", color: C.purple },
  { name: "运维", color: C.teal },
];

// ---- tiny helpers ----------------------------------------------------------
const ease = (f: number, a: number, b: number, from: number, to: number) =>
  interpolate(f, [a, b], [from, to], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });

// ---- Cairn logo (stacked stones / 玛尼堆) ----------------------------------
const CairnLogo: React.FC<{ size?: number; built?: number; showWord?: boolean }> = ({
  size = 40, built = 1, showWord = false,
}) => {
  // 5 stones bottom→top; `built` 0..1 reveals them one by one
  const stones = [
    { w: 1.0, h: 0.19, y: 0.80, c: "#3E7D5C" },
    { w: 0.82, h: 0.17, y: 0.62, c: "#43976B" },
    { w: 0.66, h: 0.16, y: 0.46, c: "#2E9E6B" },
    { w: 0.5, h: 0.14, y: 0.31, c: "#59B98A" },
    { w: 0.34, h: 0.13, y: 0.18, c: "#7FCBA3" },
  ];
  return (
    <div style={{ display: "flex", alignItems: "center", gap: size * 0.4 }}>
      <svg width={size} height={size} viewBox="0 0 100 100">
        {stones.map((s, i) => {
          const on = built >= (i + 1) / stones.length - 0.001;
          return (
            <rect key={i} x={50 - (s.w * 100) / 2} y={s.y * 100} rx={s.h * 40} ry={s.h * 40}
              width={s.w * 100} height={s.h * 100} fill={s.c}
              opacity={on ? 1 : 0} transform={on ? "" : "translate(0,-6)"} />
          );
        })}
      </svg>
      {showWord && (
        <span style={{ fontFamily: FONT, fontWeight: 700, fontSize: size * 0.62, color: C.ink, letterSpacing: -0.5 }}>
          Cairn Tabs
        </span>
      )}
    </div>
  );
};

// ---- caption bar -----------------------------------------------------------
const Caption: React.FC<{ text: string; sub?: string; localLen: number }> = ({ text, sub, localLen }) => {
  const f = useCurrentFrame();
  const op = interpolate(f, [4, 14, localLen - 12, localLen - 2], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const y = ease(f, 4, 16, 24, 0);
  return (
    <div style={{ position: "absolute", left: 0, right: 0, bottom: 70, display: "flex", justifyContent: "center", opacity: op }}>
      <div style={{ transform: `translateY(${y}px)`, textAlign: "center" }}>
        <div style={{ display: "inline-block", background: "rgba(20,26,38,0.86)", color: "#fff", fontFamily: FONT,
          fontWeight: 600, fontSize: 40, padding: "16px 30px", borderRadius: 16, backdropFilter: "blur(4px)",
          boxShadow: "0 10px 34px rgba(0,0,0,0.22)" }}>
          {text}
        </div>
        {sub && <div style={{ marginTop: 12, color: C.muted, fontFamily: FONT, fontSize: 26, fontWeight: 500 }}>{sub}</div>}
      </div>
    </div>
  );
};

// ---- cursor ----------------------------------------------------------------
const Cursor: React.FC<{ x: number; y: number; clickAt?: number }> = ({ x, y, clickAt }) => {
  const f = useCurrentFrame();
  const ring = clickAt != null && f >= clickAt && f < clickAt + 18;
  const r = ring ? interpolate(f, [clickAt!, clickAt! + 18], [4, 34]) : 0;
  const ro = ring ? interpolate(f, [clickAt!, clickAt! + 18], [0.5, 0]) : 0;
  return (
    <div style={{ position: "absolute", left: x, top: y, zIndex: 50 }}>
      {ring && <div style={{ position: "absolute", left: -r, top: -r, width: r * 2, height: r * 2, borderRadius: r,
        border: `3px solid ${C.green}`, opacity: ro }} />}
      <svg width="30" height="30" viewBox="0 0 24 24" style={{ filter: "drop-shadow(0 2px 3px rgba(0,0,0,.3))" }}>
        <path d="M3 2 L3 20 L8 15 L11 22 L14 21 L11 14 L18 14 Z" fill="#fff" stroke="#1E2430" strokeWidth="1.4" strokeLinejoin="round" />
      </svg>
    </div>
  );
};

// ---- browser frame + tab bar ----------------------------------------------
const TabPill: React.FC<{ title: string; color?: string; w?: number; dim?: number; badge?: string; state?: "dup" | "keep" }> = ({
  title, color, w = 150, dim = 1, badge, state,
}) => (
  <div style={{ width: w, height: 34, display: "flex", alignItems: "center", gap: 7, padding: "0 10px",
    background: dim < 1 ? "#EDEFF3" : "#fff", borderRadius: "9px 9px 0 0", border: `1px solid ${C.line}`,
    borderBottom: "none", opacity: dim, position: "relative", overflow: "hidden" }}>
    <div style={{ width: 12, height: 12, borderRadius: 3, background: color || "#C7CDD8", flexShrink: 0 }} />
    <span style={{ fontFamily: FONT, fontSize: 15, color: C.ink, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{title}</span>
    {badge && <span style={{ marginLeft: "auto", fontFamily: FONT, fontSize: 12, fontWeight: 700, color: "#fff",
      background: color || C.green, padding: "2px 6px", borderRadius: 6, flexShrink: 0 }}>{badge}</span>}
    {state && <span style={{ marginLeft: "auto", fontFamily: FONT, fontSize: 12, fontWeight: 700,
      color: state === "dup" ? C.danger : C.green, background: state === "dup" ? "#FBEAE2" : C.greenSoft,
      padding: "2px 7px", borderRadius: 6, flexShrink: 0 }}>{state === "dup" ? "重复" : "重复·留"}</span>}
    {color && dim === 1 && <div style={{ position: "absolute", left: 0, bottom: 0, height: 3, width: "100%", background: color }} />}
  </div>
);

const BrowserFrame: React.FC<{ tabs: React.ReactNode; children?: React.ReactNode; push?: number }> = ({ tabs, children, push = 0 }) => (
  <div style={{ position: "absolute", inset: 0, background: C.desk, transform: `scale(${1 + push})`, transformOrigin: "50% 42%" }}>
    <div style={{ position: "absolute", left: 90, right: 90, top: 70, bottom: 70, background: C.chrome, borderRadius: 18,
      boxShadow: "0 40px 90px rgba(30,40,60,0.18)", overflow: "hidden" }}>
      {/* traffic lights + tab bar */}
      <div style={{ height: 52, background: C.chromeBar, display: "flex", alignItems: "flex-end", padding: "0 16px", gap: 8, borderBottom: `1px solid ${C.line}` }}>
        <div style={{ display: "flex", gap: 8, alignSelf: "center", marginBottom: 2, marginRight: 8 }}>
          {["#FF5F57", "#FEBC2E", "#28C840"].map((c) => <div key={c} style={{ width: 13, height: 13, borderRadius: 7, background: c }} />)}
        </div>
        <div style={{ display: "flex", gap: 4, alignItems: "flex-end", flexWrap: "nowrap", overflow: "hidden" }}>{tabs}</div>
      </div>
      <div style={{ position: "absolute", top: 52, left: 0, right: 0, bottom: 0 }}>{children}</div>
    </div>
  </div>
);

// ---- sidebar group card ----------------------------------------------------
const GroupCard: React.FC<{ name: string; color: string; items: { t: string; badge?: string }[]; reveal?: number }> = ({
  name, color, items, reveal = 1,
}) => (
  <div style={{ background: "#fff", border: `1px solid ${C.line}`, borderRadius: 14, padding: "12px 12px 8px", marginBottom: 12,
    boxShadow: "0 2px 10px rgba(30,40,60,0.05)" }}>
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
      <div style={{ width: 4, height: 18, borderRadius: 3, background: color }} />
      <span style={{ fontFamily: FONT, fontWeight: 700, fontSize: 19, color: C.ink }}>{name}</span>
      <span style={{ marginLeft: "auto", fontFamily: FONT, fontSize: 14, color: C.muted }}>{items.length}</span>
    </div>
    {items.slice(0, Math.ceil(items.length * reveal)).map((it, i) => (
      <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 6px", borderRadius: 8 }}>
        <div style={{ width: 8, height: 8, borderRadius: 2, background: color }} />
        <span style={{ fontFamily: FONT, fontSize: 15, color: C.ink, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{it.t}</span>
        {it.badge && <span style={{ marginLeft: "auto", fontFamily: FONT, fontSize: 12, fontWeight: 700, color: "#fff", background: color, padding: "1px 6px", borderRadius: 5 }}>{it.badge}</span>}
      </div>
    ))}
  </div>
);

const Sidebar: React.FC<{ x: number; children: React.ReactNode; header?: React.ReactNode }> = ({ x, children, header }) => (
  <div style={{ position: "absolute", top: 70, right: 90, bottom: 70, width: 470, background: "#F7F9FB",
    borderRadius: "0 18px 18px 0", boxShadow: "-20px 0 50px rgba(30,40,60,0.10)", transform: `translateX(${x}px)`,
    padding: 22, overflow: "hidden" }}>
    <div style={{ display: "flex", alignItems: "center", marginBottom: 18 }}>
      <CairnLogo size={30} showWord />
      {header}
    </div>
    {children}
  </div>
);

// messy tab titles for the opening chaos
const MESSY = ["无标题", "Re: 会议纪要", "如何优雅地…", "Untitled", "订单 #4821", "文档-最终版2", "AWS 控制台",
  "YouTube", "npm err", "Figma", "Slack", "机票", "知乎", "Notion", "PR review", "报销", "天气", "Docs"];

// =====================================================================================
// Scenes
// =====================================================================================

// S1 — pain hook: 40+ messy tabs, slight push-in
const S1: React.FC = () => {
  const f = useCurrentFrame();
  const push = ease(f, 0, 150, 0.0, 0.06);
  const tabs = Array.from({ length: 16 }).map((_, i) => (
    <TabPill key={i} title={MESSY[i % MESSY.length]} w={i === 0 ? 120 : 92} />
  ));
  return (
    <AbsoluteFill style={{ background: C.desk }}>
      <BrowserFrame push={push} tabs={<>{tabs}<div style={{ fontFamily: FONT, color: C.muted, fontSize: 13, alignSelf: "center", padding: "0 8px" }}>+24</div></>}>
        <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div style={{ width: 900, height: 520, background: "#FAFBFC", borderRadius: 12, border: `1px solid ${C.line}` }} />
        </div>
        {/* subtle "counter" of overflow */}
        <div style={{ position: "absolute", top: 14, right: 22, fontFamily: FONT, color: C.danger, fontSize: 18, fontWeight: 700, opacity: ease(f, 30, 60, 0, 1) }}>标签 42 · 已溢出</div>
      </BrowserFrame>
      <Caption text="标签又爆了?" localLen={150} />
    </AbsoluteFill>
  );
};

// S2 — sidebar slides in, chaos absorbed into groups
const S2: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const sx = spring({ frame: f, fps, config: { damping: 200 }, durationInFrames: 26 });
  const x = interpolate(sx, [0, 1], [500, 0]);
  const absorb = ease(f, 26, 90, 0, 1);
  const tabsLeft = 16 - Math.floor(absorb * 12);
  const tabs = Array.from({ length: Math.max(4, tabsLeft) }).map((_, i) => <TabPill key={i} title={MESSY[i % MESSY.length]} w={92} />);
  return (
    <AbsoluteFill style={{ background: C.desk }}>
      <BrowserFrame tabs={tabs}>
        <div style={{ position: "absolute", inset: 0, background: "#FAFBFC" }} />
      </BrowserFrame>
      <Sidebar x={x}>
        {GROUPS.slice(0, 3).map((g, gi) => (
          <div key={g.name} style={{ opacity: ease(f, 30 + gi * 10, 55 + gi * 10, 0, 1), transform: `translateY(${ease(f, 30 + gi * 10, 55 + gi * 10, 16, 0)}px)` }}>
            <GroupCard name={g.name} color={g.color}
              items={[{ t: MESSY[gi * 3] }, { t: MESSY[gi * 3 + 1] }, { t: MESSY[gi * 3 + 2] }]} reveal={absorb} />
          </div>
        ))}
      </Sidebar>
      <Caption text="Cairn Tabs · 为标签立个路标" localLen={120} />
    </AbsoluteFill>
  );
};

// S3 — open 3 dev tabs, each auto-joins「前端开发」
const S3: React.FC = () => {
  const f = useCurrentFrame();
  const sites = [
    { t: "facebook/react", color: C.blue },
    { t: "React 官方文档", color: C.blue },
    { t: "MDN Web Docs", color: C.blue },
  ];
  const opened = Math.min(3, Math.floor(f / 55) + (f > 10 ? 1 : 0));
  const baseTabs = [<TabPill key="x" title="工作台" w={110} color={C.amber} />];
  for (let i = 0; i < opened; i++) baseTabs.push(<TabPill key={i} title={sites[i].t} w={150} color={C.blue} />);
  return (
    <AbsoluteFill style={{ background: C.desk }}>
      <BrowserFrame tabs={baseTabs}>
        <div style={{ position: "absolute", inset: 0, background: "#FAFBFC" }} />
      </BrowserFrame>
      <Sidebar x={0}>
        <GroupCard name="前端开发" color={C.blue}
          items={sites.slice(0, opened).map((s) => ({ t: s.t }))} />
        <div style={{ fontFamily: FONT, fontSize: 15, color: C.green, fontWeight: 600, marginTop: 6, opacity: opened > 0 ? interpolate(f % 55, [0, 10, 40], [0, 1, 0.4], { extrapolateRight: "clamp" }) : 0 }}>
          ✓ 已自动归入「前端开发」
        </div>
      </Sidebar>
      <Caption text="新标签,自动归到对的任务" localLen={210} />
    </AbsoluteFill>
  );
};

// S4 — same-site suggestion banner for 4 stackoverflow tabs, click 归类
const S4: React.FC = () => {
  const f = useCurrentFrame();
  const grouped = f > 105;
  const tabs = [<TabPill key="d" title="前端开发·组" w={130} color={C.blue} />];
  for (let i = 0; i < 4; i++) tabs.push(<TabPill key={i} title="Stack Overflow" w={110} color={grouped ? C.teal : undefined} dim={grouped ? 1 : 1} />);
  return (
    <AbsoluteFill style={{ background: C.desk }}>
      <BrowserFrame tabs={tabs}>
        <div style={{ position: "absolute", inset: 0, background: "#FAFBFC" }} />
        {/* suggestion banner */}
        <div style={{ position: "absolute", top: 20, left: "50%", transform: `translateX(-50%) translateY(${ease(f, 20, 34, -20, 0)}px)`,
          opacity: grouped ? ease(f, 108, 120, 1, 0) : ease(f, 20, 34, 0, 1),
          background: "#fff", border: `1px solid ${C.line}`, borderRadius: 12, padding: "12px 16px",
          boxShadow: "0 12px 34px rgba(30,40,60,0.16)", display: "flex", alignItems: "center", gap: 16 }}>
          <span style={{ fontFamily: FONT, fontSize: 17, color: C.ink }}>同站 <b>stackoverflow.com</b> · 4 个</span>
          <span style={{ fontFamily: FONT, fontSize: 16, fontWeight: 700, color: "#fff", background: C.green, padding: "7px 16px", borderRadius: 9 }}>归类</span>
          <span style={{ fontFamily: FONT, fontSize: 16, color: C.muted }}>忽略</span>
        </div>
      </BrowserFrame>
      <Sidebar x={0}>
        <GroupCard name="前端开发" color={C.blue} items={[{ t: "facebook/react" }, { t: "React 官方文档" }, { t: "MDN Web Docs" }]} />
        {grouped && <div style={{ opacity: ease(f, 108, 122, 0, 1) }}>
          <GroupCard name="Stack Overflow" color={C.teal} items={[{ t: "类型报错怎么修" }, { t: "async 陷阱" }, { t: "CORS 配置" }, { t: "正则匹配" }]} />
        </div>}
      </Sidebar>
      {/* cursor moving to 归类 then click at f=100 */}
      <Cursor x={interpolate(f, [40, 96], [1150, 995], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })}
        y={interpolate(f, [40, 96], [560, 150], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })} clickAt={100} />
      <Caption text="成组要你点头,绝不自作主张" localLen={150} />
    </AbsoluteFill>
  );
};

// S5 — dev badges: PR, PR, localhost project name
const S5: React.FC = () => {
  const f = useCurrentFrame();
  const rows = [
    { t: "GitHub · fix: auth redirect", badge: "PR #123", color: C.blue },
    { t: "Bitbucket · release 2.1", badge: "PR #1022", color: C.blue },
    { t: "localhost:3000", badge: "auth-service", color: C.teal },
  ];
  return (
    <AbsoluteFill style={{ background: C.desk }}>
      <BrowserFrame tabs={[<TabPill key="a" title="GitHub" w={110} color={C.blue} badge="PR #123" />, <TabPill key="b" title="Bitbucket" w={120} color={C.blue} badge="PR #1022" />, <TabPill key="c" title="localhost:3000" w={140} color={C.teal} />]}>
        <div style={{ position: "absolute", inset: 0, background: "#FAFBFC" }} />
      </BrowserFrame>
      <Sidebar x={0}>
        <div style={{ background: "#fff", border: `1px solid ${C.line}`, borderRadius: 14, padding: 12 }}>
          {rows.map((r, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, padding: "12px 8px", borderBottom: i < 2 ? `1px solid ${C.line}` : "none",
              opacity: ease(f, 15 + i * 22, 40 + i * 22, 0, 1), transform: `translateX(${ease(f, 15 + i * 22, 40 + i * 22, 18, 0)}px)` }}>
              <div style={{ width: 10, height: 10, borderRadius: 3, background: r.color }} />
              <span style={{ fontFamily: FONT, fontSize: 16, color: C.ink, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{r.t}</span>
              <span style={{ marginLeft: "auto", fontFamily: FONT, fontSize: 14, fontWeight: 700, color: "#fff", background: r.color, padding: "3px 10px", borderRadius: 7, flexShrink: 0 }}>{r.badge}</span>
            </div>
          ))}
        </div>
      </Sidebar>
      <Caption text="PR / Issue / 本地端口,一眼认得" localLen={150} />
    </AbsoluteFill>
  );
};

// S6 — dedup merge
const S6: React.FC = () => {
  const f = useCurrentFrame();
  const merged = f > 95;
  return (
    <AbsoluteFill style={{ background: C.desk }}>
      <BrowserFrame tabs={[<TabPill key="a" title="设计规范.md" w={130} />, <TabPill key="b" title="设计规范.md" w={130} state={merged ? undefined : "keep"} />, ...(merged ? [] : [<TabPill key="c" title="设计规范.md" w={130} state="dup" dim={0.55} />])]}>
        <div style={{ position: "absolute", inset: 0, background: "#FAFBFC" }} />
      </BrowserFrame>
      <Sidebar x={0} header={
        <span style={{ marginLeft: "auto", fontFamily: FONT, fontSize: 15, fontWeight: 700, color: "#fff",
          background: merged ? C.muted : C.danger, padding: "7px 12px", borderRadius: 9, opacity: merged ? ease(f, 96, 110, 1, 0.4) : 1 }}>
          {merged ? "已合并" : "1 重复 · 合并"}
        </span>} >
        <div style={{ fontFamily: FONT, fontSize: 16, color: C.muted, fontWeight: 700, margin: "4px 4px 10px" }}>未分类</div>
        <div style={{ background: "#fff", border: `1px solid ${C.line}`, borderRadius: 12, padding: 8 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, padding: 10 }}>
            <div style={{ width: 8, height: 8, borderRadius: 2, background: C.green }} />
            <span style={{ fontFamily: FONT, fontSize: 15, color: C.ink }}>设计规范.md</span>
            <span style={{ marginLeft: "auto", fontFamily: FONT, fontSize: 12, fontWeight: 700, color: C.green, background: C.greenSoft, padding: "2px 7px", borderRadius: 6 }}>重复·留</span>
          </div>
          {!merged && <div style={{ display: "flex", alignItems: "center", gap: 8, padding: 10, opacity: ease(f, 96, 108, 1, 0) }}>
            <div style={{ width: 8, height: 8, borderRadius: 2, background: C.danger }} />
            <span style={{ fontFamily: FONT, fontSize: 15, color: C.muted, textDecoration: "line-through" }}>设计规范.md</span>
            <span style={{ marginLeft: "auto", fontFamily: FONT, fontSize: 12, fontWeight: 700, color: C.danger, background: "#FBEAE2", padding: "2px 7px", borderRadius: 6 }}>重复</span>
          </div>}
        </div>
      </Sidebar>
      <Cursor x={interpolate(f, [30, 80], [1200, 1330], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })}
        y={interpolate(f, [30, 80], [400, 118], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })} clickAt={88} />
      <Caption text="重复标签,一键合并" localLen={150} />
    </AbsoluteFill>
  );
};

// S7 — global search ⌘⇧K
const S7: React.FC = () => {
  const f = useCurrentFrame();
  const open = f > 10;
  const query = "react".slice(0, Math.max(0, Math.floor((f - 24) / 6)));
  const hits = ["facebook/react", "React 官方文档", "React Router 文档", "react-query"].filter((h) => h.toLowerCase().includes(query.toLowerCase()) || query === "");
  return (
    <AbsoluteFill style={{ background: C.desk }}>
      <BrowserFrame tabs={[<TabPill key="a" title="前端开发·组" w={130} color={C.blue} />, <TabPill key="b" title="工作·组" w={110} color={C.amber} />, <TabPill key="c" title="运维·组" w={100} color={C.teal} />]}>
        <div style={{ position: "absolute", inset: 0, background: "rgba(20,26,38,0.28)", opacity: open ? ease(f, 10, 22, 0, 1) : 0 }} />
      </BrowserFrame>
      {open && (
        <div style={{ position: "absolute", top: 300, left: "50%", transform: `translateX(-50%) scale(${interpolate(spring({ frame: f - 10, fps: 30, config: { damping: 200 }, durationInFrames: 16 }), [0, 1], [0.94, 1])})`,
          width: 760, background: "#fff", borderRadius: 18, boxShadow: "0 40px 90px rgba(0,0,0,0.3)", overflow: "hidden", opacity: ease(f, 10, 20, 0, 1) }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "20px 24px", borderBottom: `1px solid ${C.line}` }}>
            <span style={{ fontSize: 24 }}>🔍</span>
            <span style={{ fontFamily: FONT, fontSize: 26, color: C.ink }}>{query}<span style={{ opacity: f % 20 < 10 ? 1 : 0, color: C.green }}>|</span></span>
            <span style={{ marginLeft: "auto", fontFamily: FONT, fontSize: 15, color: C.muted, border: `1px solid ${C.line}`, padding: "4px 10px", borderRadius: 7 }}>⌘⇧K</span>
          </div>
          {hits.map((h, i) => (
            <div key={h} style={{ display: "flex", alignItems: "center", gap: 12, padding: "14px 24px", background: i === 0 ? C.greenSoft : "#fff" }}>
              <div style={{ width: 10, height: 10, borderRadius: 3, background: C.blue }} />
              <span style={{ fontFamily: FONT, fontSize: 19, color: C.ink }}>{h}</span>
              {i === 0 && <span style={{ marginLeft: "auto", fontFamily: FONT, fontSize: 14, color: C.green, fontWeight: 700 }}>↵ 跳转</span>}
            </div>
          ))}
        </div>
      )}
      <Caption text="⌘⇧K,秒搜所有标签" localLen={180} />
    </AbsoluteFill>
  );
};

// S8 — AI organize
const S8: React.FC = () => {
  const f = useCurrentFrame();
  const phase = f < 55 ? "analyze" : f < 130 ? "preview" : "done";
  return (
    <AbsoluteFill style={{ background: C.desk }}>
      <BrowserFrame tabs={[<TabPill key="a" title="未分类 · 9" w={120} />]}>
        <div style={{ position: "absolute", inset: 0, background: "#FAFBFC" }} />
      </BrowserFrame>
      <Sidebar x={0} header={
        <span style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 6, fontFamily: FONT, fontSize: 15, fontWeight: 700,
          color: C.purple, background: "#F1ECFE", padding: "7px 12px", borderRadius: 9 }}>✦ AI 整理</span>}>
        {phase === "analyze" && (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: 300, gap: 16 }}>
            <div style={{ width: 46, height: 46, borderRadius: 23, border: `4px solid ${C.line}`, borderTopColor: C.purple, transform: `rotate(${f * 12}deg)` }} />
            <span style={{ fontFamily: FONT, fontSize: 17, color: C.muted }}>正在分析 9 个未分类标签…</span>
          </div>
        )}
        {phase !== "analyze" && (
          <div style={{ opacity: ease(f, 55, 68, 0, 1) }}>
            <div style={{ fontFamily: FONT, fontSize: 14, color: C.muted, margin: "0 4px 10px" }}>建议方案 · 预览</div>
            {[{ n: "前端开发", c: C.blue, tag: "新建", k: 3 }, { n: "工作", c: C.amber, tag: "并入已有", k: 3 }, { n: "阅读稍后", c: C.purple, tag: "新建", k: 3 }].map((g, i) => (
              <div key={g.n} style={{ display: "flex", alignItems: "center", gap: 10, background: "#fff", border: `1px solid ${C.line}`, borderRadius: 12, padding: 12, marginBottom: 10 }}>
                <div style={{ width: 4, height: 20, borderRadius: 3, background: g.c }} />
                <span style={{ fontFamily: FONT, fontWeight: 700, fontSize: 17, color: C.ink }}>{g.n}</span>
                <span style={{ fontFamily: FONT, fontSize: 13, color: C.muted }}>· {g.k} 个</span>
                <span style={{ marginLeft: "auto", fontFamily: FONT, fontSize: 12, fontWeight: 700, color: g.tag === "新建" ? C.green : C.amber, background: g.tag === "新建" ? C.greenSoft : "#FDF3E3", padding: "2px 8px", borderRadius: 6 }}>{g.tag}</span>
              </div>
            ))}
            <div style={{ display: "flex", gap: 10, marginTop: 4 }}>
              <span style={{ fontFamily: FONT, fontSize: 16, fontWeight: 700, color: "#fff", background: phase === "done" ? C.muted : C.purple, padding: "9px 18px", borderRadius: 9 }}>{phase === "done" ? "已应用 ✓" : "应用"}</span>
              <span style={{ fontFamily: FONT, fontSize: 16, color: C.muted, padding: "9px 12px" }}>取消</span>
            </div>
          </div>
        )}
      </Sidebar>
      {phase === "preview" && <Cursor x={interpolate(f, [70, 120], [1180, 1010], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })} y={interpolate(f, [70, 120], [560, 560], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })} clickAt={124} />}
      <Caption text="用你的 API key,AI 帮你整理" sub="数据只在本地" localLen={180} />
    </AbsoluteFill>
  );
};

// S9 — archive + dark mode
const S9: React.FC = () => {
  const f = useCurrentFrame();
  const archived = f > 60;
  const dark = f > 100;
  const bg = dark ? "#151922" : C.desk;
  const panel = dark ? "#1E2430" : "#F7F9FB";
  const ink = dark ? "#EAECEF" : C.ink;
  return (
    <AbsoluteFill style={{ background: bg }}>
      <BrowserFrame tabs={[<TabPill key="a" title="工作台" w={110} color={C.amber} />, ...(archived ? [] : [<TabPill key="b" title="前端开发·组" w={130} color={C.blue} dim={archived ? 0.3 : 1} />])]}>
        <div style={{ position: "absolute", inset: 0, background: dark ? "#10141C" : "#FAFBFC" }} />
      </BrowserFrame>
      <div style={{ position: "absolute", top: 70, right: 90, bottom: 70, width: 470, background: panel, borderRadius: "0 18px 18px 0",
        boxShadow: "-20px 0 50px rgba(30,40,60,0.10)", padding: 22 }}>
        <div style={{ display: "flex", alignItems: "center", marginBottom: 18 }}>
          <CairnLogo size={30} showWord />
          <span style={{ marginLeft: "auto", fontFamily: FONT, fontSize: 18 }}>{dark ? "🌙" : "☀️"}</span>
        </div>
        {!archived ? (
          <div style={{ background: dark ? "#252C3A" : "#fff", border: `1px solid ${dark ? "#2E3646" : C.line}`, borderRadius: 14, padding: 14, transform: `translateX(${ease(f, 40, 60, 0, 500)}px)`, opacity: ease(f, 48, 60, 1, 0) }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <div style={{ width: 4, height: 18, borderRadius: 3, background: C.blue }} />
              <span style={{ fontFamily: FONT, fontWeight: 700, fontSize: 19, color: ink }}>前端开发</span>
              <span style={{ marginLeft: "auto", fontFamily: FONT, fontSize: 14, fontWeight: 700, color: C.green, background: C.greenSoft, padding: "4px 10px", borderRadius: 8 }}>归档</span>
            </div>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: 260, gap: 14, opacity: ease(f, 62, 74, 0, 1) }}>
            <CairnLogo size={54} />
            <span style={{ fontFamily: FONT, fontSize: 17, color: dark ? "#9AA3B2" : C.muted }}>清爽多了 ✓</span>
          </div>
        )}
      </div>
      {archived && <div style={{ position: "absolute", bottom: 130, left: "50%", transform: "translateX(-50%)", background: "rgba(20,26,38,0.9)", color: "#fff", fontFamily: FONT, fontSize: 20, padding: "12px 22px", borderRadius: 12, opacity: ease(f, 62, 74, 0, 1) }}>已归档 · 随时恢复</div>}
      <Cursor x={interpolate(f, [20, 54], [1180, 1300], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })} y={interpolate(f, [20, 54], [400, 118], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })} clickAt={56} />
      <Caption text="整个任务一键归档,随时恢复" localLen={150} />
    </AbsoluteFill>
  );
};

// S10 — resolution: calm, cairn builds into logo
const S10: React.FC = () => {
  const f = useCurrentFrame();
  const built = ease(f, 20, 110, 0, 1);
  const wordOp = ease(f, 110, 130, 0, 1);
  const tagOp = ease(f, 150, 180, 0, 1);
  const settle = ease(f, 0, 40, 0.5, 1);
  return (
    <AbsoluteFill style={{ background: `linear-gradient(180deg, #F7FBF9 0%, ${C.greenSoft} 100%)` }}>
      {/* faint settled groups behind */}
      <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", opacity: 0.12 * settle }}>
        <div style={{ display: "flex", gap: 20 }}>
          {GROUPS.map((g) => <div key={g.name} style={{ width: 150, height: 200, borderRadius: 16, borderTop: `6px solid ${g.color}`, background: "#fff" }} />)}
        </div>
      </div>
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 26 }}>
        <div style={{ transform: "scale(1.6)" }}><CairnLogo size={130} built={built} /></div>
        <div style={{ opacity: wordOp }}>
          <span style={{ fontFamily: FONT, fontWeight: 800, fontSize: 78, color: C.ink, letterSpacing: -1 }}>Cairn Tabs</span>
        </div>
        <div style={{ opacity: tagOp, display: "flex", gap: 18, alignItems: "center" }}>
          {["本地优先", "无账号", "开源"].map((t, i) => (
            <React.Fragment key={t}>
              {i > 0 && <span style={{ color: C.green, fontSize: 20 }}>·</span>}
              <span style={{ fontFamily: FONT, fontSize: 30, color: C.green, fontWeight: 600 }}>{t}</span>
            </React.Fragment>
          ))}
        </div>
      </div>
    </AbsoluteFill>
  );
};

// =====================================================================================
export const CairnTabs: React.FC = () => (
  <AbsoluteFill style={{ background: C.desk }}>
    <Sequence from={0} durationInFrames={150}><S1 /></Sequence>
    <Sequence from={150} durationInFrames={120}><S2 /></Sequence>
    <Sequence from={270} durationInFrames={210}><S3 /></Sequence>
    <Sequence from={480} durationInFrames={150}><S4 /></Sequence>
    <Sequence from={630} durationInFrames={150}><S5 /></Sequence>
    <Sequence from={780} durationInFrames={150}><S6 /></Sequence>
    <Sequence from={930} durationInFrames={180}><S7 /></Sequence>
    <Sequence from={1110} durationInFrames={180}><S8 /></Sequence>
    <Sequence from={1290} durationInFrames={150}><S9 /></Sequence>
    <Sequence from={1440} durationInFrames={240}><S10 /></Sequence>
  </AbsoluteFill>
);
