import React from "react";
import { Composition } from "remotion";
import { BrandVideo, DEFAULT_PROPS, type BrandVideoProps } from "./BrandVideo";
import { CairnTabs, CAIRN_FPS, CAIRN_DURATION } from "./CairnTabs";

/** Single parametrized composition. Per-channel look is data-driven via `brand` in props,
 *  so one template serves all 4 accounts (Airdrop Edge / Clear Charts / Quiet Yield / Aurea).
 *  Duration/size are derived from props by calculateMetadata. */
export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="BrandVideo"
        component={BrandVideo}
        durationInFrames={900}
        fps={30}
        width={1080}
        height={1920}
        defaultProps={DEFAULT_PROPS}
        calculateMetadata={({ props }: { props: BrandVideoProps }) => {
          const fps = props.fps || 30;
          return {
            fps,
            width: props.width || 1080,
            height: props.height || 1920,
            durationInFrames: Math.max(1, Math.round((props.durationInSeconds || 30) * fps)),
          };
        }}
      />
      {/* Standalone product demo (landscape). Unrelated to the matrix-loop channel pipeline. */}
      <Composition
        id="CairnTabs"
        component={CairnTabs}
        durationInFrames={CAIRN_DURATION}
        fps={CAIRN_FPS}
        width={1920}
        height={1080}
      />
    </>
  );
};
