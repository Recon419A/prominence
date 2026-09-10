// MapLibre resolves its worker relative to import.meta.url, which Turbopack
// rewrites, so serve the worker (and the chunk it imports) as static files.
import { copyFile, mkdir } from "node:fs/promises";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";

const require = createRequire(import.meta.url);
const dist = dirname(require.resolve("maplibre-gl/dist/maplibre-gl.mjs"));
const target = new URL("../public/maplibre/", import.meta.url);
await mkdir(target, { recursive: true });
for (const file of ["maplibre-gl-worker.mjs", "maplibre-gl-shared.mjs"]) {
  await copyFile(join(dist, file), new URL(file, target));
}
