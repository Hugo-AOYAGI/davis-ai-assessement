import { readFile, realpath } from "node:fs/promises";
import path from "node:path";

/**
 * Serves evidence crops (PNG) saved by the agent under
 * `<PROJECT_ROOT>/data/crops/`. Takes precedence over the `/api/[..._path]`
 * proxy because a static segment beats a catch-all.
 */
export const runtime = "nodejs";

const projectRoot = () =>
  process.env.PROJECT_ROOT ?? path.resolve(process.cwd(), "..");

const notFound = () => new Response("Not found", { status: 404 });

export async function GET(
  _request: Request,
  ctx: { params: Promise<{ path: string[] }> },
) {
  const { path: segments } = await ctx.params;
  if (
    !segments?.length ||
    segments.some((s) => !s || s === "." || s === ".." || /[\\/\0]/.test(s)) ||
    path.extname(segments[segments.length - 1]).toLowerCase() !== ".png"
  ) {
    return notFound();
  }

  const cropsDir = path.resolve(projectRoot(), "data", "crops");
  const requested = path.resolve(cropsDir, ...segments);
  if (!requested.startsWith(cropsDir + path.sep)) return notFound();

  try {
    // Resolve symlinks too: the real file must still live inside data/crops.
    const [realDir, realFile] = await Promise.all([
      realpath(cropsDir),
      realpath(requested),
    ]);
    if (!realFile.startsWith(realDir + path.sep)) return notFound();
    const body = await readFile(realFile);
    return new Response(new Uint8Array(body), {
      headers: {
        "Content-Type": "image/png",
        "Content-Length": String(body.byteLength),
        "Cache-Control": "public, max-age=3600, stale-while-revalidate=86400",
        "X-Content-Type-Options": "nosniff",
      },
    });
  } catch {
    return notFound();
  }
}
