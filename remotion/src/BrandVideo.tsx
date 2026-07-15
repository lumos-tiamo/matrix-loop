import React from "react";
import {
  AbsoluteFill, Audio, Img, OffthreadVideo, staticFile,
  useCurrentFrame, useVideoConfig, interpolate, spring,
} from "remotion";

export type Caption = { text: string; start: number; end: number };

export type BrandVideoProps = {
  width: number;
  height: number;
  fps: number;
  durationInSeconds: number;
  /** background media served from remotion/public (relative path), or "none" for a brand gradient */
  background: { kind: "video" | "image" | "none"; src: string };
  /** TTS voiceover served from remotion/public (relative path), or null */
  audioSrc: string | null;
  captions: Caption[];
  brand: { name: string; color: string; accent: string; handle: string };
  title: string | null;
};

export const DEFAULT_PROPS: BrandVideoProps = {
  width: 1080,
  height: 1920,
  fps: 30,
  durationInSeconds: 8,
  background: { kind: "none", src: "" },
  audioSrc: null,
  captions: [
    { text: "matrix-loop × Remotion", start: 0, end: 3 },
    { text: "brand template preview", start: 3, end: 8 },
  ],
  brand: { name: "Airdrop Edge", color: "#8B5CFF", accent: "#C6FF3A", handle: "@AirdropEdge" },
  title: null,
};

const Background: React.FC<{ background: BrandVideoProps["background"]; brand: BrandVideoProps["brand"]; totalFrames: number }>
  = ({ background, brand, totalFrames }) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  if (background.kind === "video") {
    return <OffthreadVideo src={staticFile(background.src)} muted playbackRate={1}
      style={{ width, height, objectFit: "cover" }} />;
  }
  if (background.kind === "image") {
    const zoom = interpolate(frame, [0, totalFrames], [1, 1.09], { extrapolateRight: "clamp" });
    return <Img src={staticFile(background.src)} style={{ width, height, objectFit: "cover", transform: `scale(${zoom})` }} />;
  }
  return <AbsoluteFill style={{ background: `radial-gradient(120% 80% at 50% 0%, ${brand.color} 0%, #0A0D12 60%)` }} />;
};

const CaptionBlock: React.FC<{ text: string; accent: string; fps: number; startFrame: number }>
  = ({ text, accent, fps, startFrame }) => {
  const frame = useCurrentFrame();
  const local = frame - startFrame;
  const pop = spring({ frame: local, fps, config: { damping: 200 } });
  const y = interpolate(pop, [0, 1], [30, 0]);
  return (
    <div style={{
      position: "absolute", left: 60, right: 60, bottom: 260, textAlign: "center",
      transform: `translateY(${y}px)`, opacity: pop,
    }}>
      <span style={{
        display: "inline",
        fontFamily: "Inter, -apple-system, 'PingFang SC', sans-serif",
        fontWeight: 800, fontSize: 62, lineHeight: 1.2, color: "#fff",
        textShadow: "0 3px 22px rgba(0,0,0,.75)",
        boxDecorationBreak: "clone", WebkitBoxDecorationBreak: "clone",
        background: "linear-gradient(180deg, transparent 62%, " + accent + "44 62%)",
      }}>{text}</span>
    </div>
  );
};

export const BrandVideo: React.FC<BrandVideoProps> = ({ background, audioSrc, captions, brand, title, durationInSeconds }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const totalFrames = Math.round(durationInSeconds * fps);
  const active = captions.find((c) => t >= c.start && t < c.end);
  const titleIn = interpolate(frame, [0, 12], [0, 1], { extrapolateRight: "clamp" });

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <AbsoluteFill><Background background={background} brand={brand} totalFrames={totalFrames} /></AbsoluteFill>

      {/* legibility scrim: darken top & bottom */}
      <AbsoluteFill style={{
        background: "linear-gradient(180deg, rgba(0,0,0,.45) 0%, rgba(0,0,0,0) 22%, rgba(0,0,0,0) 52%, rgba(0,0,0,.78) 100%)",
      }} />

      {title && t < 3.2 && (
        <div style={{
          position: "absolute", top: 110, left: 60, right: 60, opacity: titleIn,
          fontFamily: "'Space Grotesk', Inter, sans-serif", fontWeight: 700, fontSize: 52,
          color: "#fff", textShadow: "0 3px 18px rgba(0,0,0,.7)",
        }}>{title}</div>
      )}

      {active && <CaptionBlock text={active.text} accent={brand.accent} fps={fps}
        startFrame={Math.round(active.start * fps)} />}

      {/* brand lower-third */}
      <div style={{
        position: "absolute", bottom: 96, left: 0, right: 0, textAlign: "center",
        fontFamily: "'Space Grotesk', Inter, sans-serif", fontWeight: 700, fontSize: 34,
      }}>
        <span style={{ color: brand.accent }}>{brand.name}</span>
        {brand.handle ? <span style={{ color: "#fff", opacity: 0.72, marginLeft: 12 }}>{brand.handle}</span> : null}
      </div>
      {/* accent progress rule */}
      <div style={{
        position: "absolute", bottom: 70, left: 60, right: 60, height: 4, borderRadius: 2,
        background: "rgba(255,255,255,.12)",
      }}>
        <div style={{ height: "100%", width: `${interpolate(frame, [0, totalFrames], [0, 100], { extrapolateRight: "clamp" })}%`,
          background: brand.accent, borderRadius: 2 }} />
      </div>

      {audioSrc && <Audio src={staticFile(audioSrc)} />}
    </AbsoluteFill>
  );
};
