"use client";

import { useEffect, useMemo, useState } from "react";
import { Canvas } from "@react-three/fiber";
import { Edges, Grid, Line, OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import { RotateCcw } from "lucide-react";
import type { Boundary, BoundaryKind, Point, Polygon } from "@/lib/study-types";
import { BOUNDARY_COLORS, FOOTPRINT_COLOR } from "./colors";
import { formatLength, formatStoreys } from "./format";
import { bounds, centroid, polygonToLocal, ringToLocal } from "./geometry";
import { type SceneColors, useSceneColors, toRgb } from "./theme-colors";

/**
 * Scene axes: Lambert x (east) → three x, Lambert y (north) → three −z,
 * height → three y; all relative to the site centroid. Shapes are drawn in
 * the XY plane with local (x, y) and rotated −90° about X, which maps
 * (x, y, z) to (x, z, −y).
 */
type Vec3 = [number, number, number];
const at = ([x, y]: Point, height = 0): Vec3 => [x, height, -y];
const FLAT: Vec3 = [-Math.PI / 2, 0, 0];

function toShape(polygon: Polygon): THREE.Shape {
  const shape = new THREE.Shape(
    polygon.exterior.map(([x, y]) => new THREE.Vector2(x, y)),
  );
  for (const hole of polygon.holes) {
    shape.holes.push(
      new THREE.Path(hole.map(([x, y]) => new THREE.Vector2(x, y))),
    );
  }
  return shape;
}

export interface Volume3DProps {
  /** Site polygon, EPSG:2154. */
  site: Polygon;
  /** Site minus setbacks, EPSG:2154. */
  footprint: Polygon;
  boundaries: Boundary[];
  maxHeight: number;
  maxStoreys: number | null;
  /** Spacing of the horizontal floor lines, metres. */
  storeyHeight: number;
}

/** A screen-sized text badge (canvas texture sprite), drawn above `position`. */
function Label({
  text,
  position,
  colors,
}: {
  text: string;
  position: Vec3;
  colors: SceneColors;
}) {
  const { texture, aspect } = useMemo(() => {
    const ratio = 3;
    const font = `600 ${12 * ratio}px ${getComputedStyle(document.body).fontFamily}`;
    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d")!;
    ctx.font = font;
    const padX = 8 * ratio;
    canvas.width = Math.ceil(ctx.measureText(text).width + 2 * padX);
    canvas.height = 22 * ratio;
    ctx.font = font;
    ctx.fillStyle = colors.background;
    ctx.strokeStyle = colors.border;
    ctx.lineWidth = ratio;
    ctx.beginPath();
    ctx.roundRect(
      ratio / 2,
      ratio / 2,
      canvas.width - ratio,
      canvas.height - ratio,
      6 * ratio,
    );
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = colors.foreground;
    ctx.textBaseline = "middle";
    ctx.fillText(text, padX, canvas.height / 2);
    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    return { texture, aspect: canvas.width / canvas.height };
  }, [text, colors]);
  useEffect(() => () => texture.dispose(), [texture]);
  const height = 0.07;
  return (
    <sprite
      position={position}
      center={[0.5, -0.25]}
      scale={[height * aspect, height, 1]}
      renderOrder={10}
    >
      <spriteMaterial
        map={texture}
        transparent
        depthTest={false}
        sizeAttenuation={false}
      />
    </sprite>
  );
}

function Scene({
  site,
  footprint,
  boundaries,
  maxHeight,
  maxStoreys,
  storeyHeight,
}: Volume3DProps) {
  const colors = useSceneColors();
  const data = useMemo(() => {
    const origin = centroid(site.exterior);
    const localSite = polygonToLocal(site, origin);
    const localFootprint = polygonToLocal(footprint, origin);
    const edges = boundaries.map((b) => ({
      kind: b.kind,
      points: ringToLocal([b.start, b.end], origin),
    }));
    const box = bounds(localSite.exterior);
    // Height marker on the footprint's south-east-most vertex, nearest the camera.
    const marker = localFootprint.exterior.reduce((best, p) =>
      p[0] - p[1] > best[0] - best[1] ? p : best,
    );
    const levels: number[] = [];
    for (let h = storeyHeight; h < maxHeight - 1e-3; h += storeyHeight) {
      levels.push(h);
    }
    return { localSite, localFootprint, edges, box, marker, levels };
  }, [site, footprint, boundaries, maxHeight, storeyHeight]);

  const volume = useMemo(
    () =>
      new THREE.ExtrudeGeometry(toShape(data.localFootprint), {
        depth: maxHeight,
        bevelEnabled: false,
      }),
    [data.localFootprint, maxHeight],
  );
  const ground = useMemo(
    () => new THREE.ShapeGeometry(toShape(data.localSite)),
    [data.localSite],
  );
  const dataColors = useMemo(
    () => ({
      footprint: toRgb(FOOTPRINT_COLOR),
      ...(Object.fromEntries(
        Object.entries(BOUNDARY_COLORS).map(([k, v]) => [k, toRgb(v)]),
      ) as Record<BoundaryKind, string>),
    }),
    [],
  );

  const { box, marker } = data;
  const extent = Math.max(box.maxX - box.minX, box.maxY - box.minY);
  const label =
    maxStoreys === null
      ? formatLength(maxHeight, 0)
      : `${formatLength(maxHeight, 0)} · ${formatStoreys(maxStoreys)}`;

  return (
    <>
      <ambientLight intensity={0.8} />
      <hemisphereLight
        args={["#ffffff", colors.muted, 0.6]}
        position={[0, 1, 0]}
      />
      <directionalLight
        position={[extent, extent * 2, extent * 1.5]}
        intensity={1.4}
      />
      <Grid
        position={[0, -0.02, 0]}
        args={[extent * 4, extent * 4]}
        cellSize={5}
        sectionSize={25}
        cellThickness={0.6}
        sectionThickness={1}
        cellColor={colors.border}
        sectionColor={colors.mutedForeground}
        fadeDistance={extent * 3}
        fadeStrength={1.5}
        infiniteGrid
      />
      <mesh
        geometry={ground}
        rotation={FLAT}
        position={[0, 0.01, 0]}
      >
        <meshStandardMaterial
          color={colors.muted}
          side={THREE.DoubleSide}
        />
      </mesh>
      {data.edges.map((e, i) => (
        <Line
          key={i}
          points={e.points.map((p) => at(p, 0.05))}
          color={dataColors[e.kind]}
          lineWidth={3}
        />
      ))}
      <mesh
        geometry={volume}
        rotation={FLAT}
      >
        <meshStandardMaterial
          color={dataColors.footprint}
          transparent
          opacity={0.32}
          depthWrite={false}
          side={THREE.DoubleSide}
        />
        <Edges
          threshold={20}
          color={dataColors.footprint}
        />
      </mesh>
      {data.levels.map((h) => (
        <Line
          key={h}
          points={data.localFootprint.exterior.map((p) => at(p, h))}
          color={dataColors.footprint}
          lineWidth={1}
          transparent
          opacity={0.55}
        />
      ))}
      <Line
        points={[at(marker, 0), at(marker, maxHeight)]}
        color={colors.foreground}
        lineWidth={1.5}
        dashed
        dashSize={1}
        gapSize={0.6}
      />
      <Label
        text={label}
        position={at(marker, maxHeight)}
        colors={colors}
      />
    </>
  );
}

function cameraFor({ site, maxHeight }: Volume3DProps) {
  const box = bounds(site.exterior);
  const w = box.maxX - box.minX;
  const d = box.maxY - box.minY;
  const radius = Math.hypot(w / 2, d / 2, maxHeight / 2);
  const fov = 35;
  const distance = (radius / Math.sin(((fov / 2) * Math.PI) / 180)) * 0.78;
  // From the south-east, above: +x east, +z south.
  const dir = new THREE.Vector3(0.9, 0.85, 1.1).normalize();
  return {
    fov,
    near: Math.max(radius / 100, 0.1),
    far: radius * 60,
    position: dir.multiplyScalar(distance).toArray() as Vec3,
    target: [0, maxHeight * 0.3, 0] as Vec3,
    radius,
  };
}

export function Volume3D(props: Volume3DProps) {
  const [view, setView] = useState(0);
  const camera = cameraFor(props);
  return (
    <div className="bg-muted/30 relative h-80 w-full overflow-hidden rounded-lg border">
      <Canvas
        key={view}
        camera={{
          fov: camera.fov,
          near: camera.near,
          far: camera.far,
          position: camera.position,
        }}
        dpr={[1, 2]}
        frameloop="demand"
        gl={{ antialias: true, alpha: true }}
        aria-label="3D view of the maximum buildable volume on the site"
        role="img"
        fallback={
          <p className="text-muted-foreground p-4 text-sm">
            3D view unavailable: this browser has no WebGL support.
          </p>
        }
      >
        <Scene {...props} />
        <OrbitControls
          makeDefault
          target={camera.target}
          enableDamping
          maxPolarAngle={Math.PI / 2 - 0.05}
          minDistance={camera.radius * 0.4}
          maxDistance={camera.radius * 6}
        />
      </Canvas>
      <button
        type="button"
        onClick={() => setView((v) => v + 1)}
        className="bg-background/80 hover:bg-background focus-visible:ring-ring/50 text-muted-foreground hover:text-foreground absolute top-2 right-2 inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs backdrop-blur outline-none focus-visible:ring-[3px]"
      >
        <RotateCcw
          aria-hidden
          className="size-3"
        />
        Reset view
      </button>
      <p
        aria-hidden
        className="text-muted-foreground pointer-events-none absolute bottom-2 left-2 text-[10px]"
      >
        Drag to orbit · scroll to zoom · right-drag to pan
      </p>
    </div>
  );
}

export default Volume3D;
