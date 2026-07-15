// Headless render: node render.mjs <props.json> <out.mp4>
// Bundles once into .bundle/ and reuses it (set FORCE_BUNDLE=1 to rebuild after template edits).
import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

async function main() {
  const [, , propsPath, outPath] = process.argv;
  if (!propsPath || !outPath) {
    console.error("usage: node render.mjs <props.json> <out.mp4>");
    process.exit(2);
  }
  const inputProps = JSON.parse(readFileSync(propsPath, "utf8"));

  const bundleDir = path.join(__dirname, ".bundle");
  let serveUrl;
  if (existsSync(path.join(bundleDir, "index.html")) && process.env.FORCE_BUNDLE !== "1") {
    serveUrl = bundleDir;
  } else {
    serveUrl = await bundle({
      entryPoint: path.join(__dirname, "src", "index.ts"),
      publicDir: path.join(__dirname, "public"),
      outDir: bundleDir,
    });
  }

  const composition = await selectComposition({ serveUrl, id: "BrandVideo", inputProps });
  await renderMedia({
    composition,
    serveUrl,
    codec: "h264",
    outputLocation: outPath,
    inputProps,
    // reuse the machine's Chrome; falls back to Remotion's own download if absent
    chromiumOptions: { gl: "angle" },
  });
  console.log("RENDER_OK " + outPath);
}

main().catch((e) => { console.error(e); process.exit(1); });
