export const entityStates = [
  "hola",
  "escucha",
  "revisa",
  "orden",
  "confirma",
  "protege",
  "listo",
  "telefono",
  "favor",
] as const;
export type EntityState = (typeof entityStates)[number];
export type EntityMode = "hero" | "dock" | "work";
export const workingLooks = ["sweep", "warm", "read", "still"] as const;
export type WorkingLook = (typeof workingLooks)[number];
export type Aura = readonly [string, string];

type Role = "calm" | "warm" | "trust" | "fresh";
type Shape = "circle" | "small" | "pebble" | "egg" | "seal" | "droop" | "shield" | "phone";
type Eyes = "open" | "wide" | "side" | "smile" | "closed" | "plead";
type Mouth = "big" | "smile" | "soft" | "flat" | "o" | "pout";
export type Effect = "spark" | "rings" | "orbit" | "call" | "tear";

interface PaletteBlob {
  role: Role;
  color: string;
  dx: number;
  dy: number;
  r: number;
  opacity: number;
}

export interface Palette {
  ground: string;
  blobs: readonly PaletteBlob[];
}

export const tricolorAurora: Palette = {
  ground: "#f2f5f9",
  blobs: [
    { role: "calm", color: "#1f9f7c", dx: 3, dy: -24, r: 32, opacity: 0.85 },
    { role: "warm", color: "#e0677c", dx: -16, dy: -9, r: 42, opacity: 1 },
    { role: "trust", color: "#4c8fe6", dx: 22, dy: 13, r: 37, opacity: 0.9 },
    { role: "fresh", color: "#a9c9f5", dx: -7, dy: 29, r: 27, opacity: 0.8 },
  ],
};

export const palette = tricolorAurora;

export interface StateSpec {
  shape: Shape;
  eyes: Eyes;
  mouth: Mouth;
  brow?: "raise" | "plead" | "focus";
  aura?: Aura;
  effect?: Effect;
  phone?: boolean;
  lead: readonly Role[];
  listens?: boolean;
  shakes?: boolean;
}

export const stateSpecs: Record<EntityState, StateSpec> = {
  hola: { shape: "circle", eyes: "smile", mouth: "big", effect: "spark", lead: ["warm", "fresh"] },
  escucha: { shape: "circle", eyes: "open", mouth: "soft", effect: "rings", lead: ["fresh"], listens: true },
  revisa: {
    shape: "small",
    eyes: "side",
    mouth: "flat",
    brow: "focus",
    aura: ["#6fd3b5", "#9be7ff"],
    effect: "orbit",
    lead: ["trust", "calm"],
  },
  orden: { shape: "pebble", eyes: "closed", mouth: "soft", lead: ["calm"] },
  confirma: { shape: "egg", eyes: "wide", mouth: "o", brow: "raise", lead: ["warm"] },
  protege: { shape: "shield", eyes: "open", mouth: "flat", lead: ["calm", "trust"] },
  listo: { shape: "seal", eyes: "smile", mouth: "big", effect: "spark", lead: ["calm", "warm"] },
  telefono: {
    shape: "phone",
    eyes: "side",
    mouth: "smile",
    effect: "call",
    phone: true,
    lead: ["trust"],
    shakes: true,
  },
  favor: { shape: "droop", eyes: "plead", mouth: "pout", brow: "plead", effect: "tear", lead: ["trust", "warm"] },
};

export type Point = readonly [number, number];

export const SAMPLES = 72;

function polar(cx: number, cy: number, radii: (angle: number) => [number, number]): Point[] {
  return Array.from({ length: SAMPLES }, (_, index) => {
    const angle = (index / SAMPLES) * Math.PI * 2;
    const [rx, ry] = radii(angle);
    return [cx + rx * Math.cos(angle), cy + ry * Math.sin(angle)] as const;
  });
}

type Segment = (t: number) => Point;

const line =
  (from: Point, to: Point): Segment =>
  (t) => [from[0] + (to[0] - from[0]) * t, from[1] + (to[1] - from[1]) * t];

const cubic =
  (p0: Point, p1: Point, p2: Point, p3: Point): Segment =>
  (t) => {
    const u = 1 - t;
    const a = u * u * u;
    const b = 3 * u * u * t;
    const c = 3 * u * t * t;
    const d = t * t * t;
    return [a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]];
  };

const arc =
  (center: Point, radius: number, from: number, to: number): Segment =>
  (t) => {
    const angle = from + (to - from) * t;
    return [center[0] + radius * Math.cos(angle), center[1] + radius * Math.sin(angle)];
  };

function sampleOutline(segments: readonly Segment[], faceY: number): Point[] {
  const steps = 64;
  const dense: Point[] = [];
  for (const segment of segments) for (let step = 0; step < steps; step++) dense.push(segment(step / steps));
  const first = dense[0];
  if (!first) return [];
  dense.push(first);
  const lengths = [0];
  for (let index = 1; index < dense.length; index++) {
    const [ax, ay] = dense[index - 1] as Point;
    const [bx, by] = dense[index] as Point;
    lengths.push((lengths[index - 1] as number) + Math.hypot(bx - ax, by - ay));
  }
  const total = lengths[lengths.length - 1] as number;
  const points: Point[] = [];
  let cursor = 1;
  for (let index = 0; index < SAMPLES; index++) {
    const target = (index / SAMPLES) * total;
    while ((lengths[cursor] as number) < target) cursor++;
    const [ax, ay] = dense[cursor - 1] as Point;
    const [bx, by] = dense[cursor] as Point;
    const start = lengths[cursor - 1] as number;
    const span = (lengths[cursor] as number) - start || 1;
    const t = (target - start) / span;
    points.push([ax + (bx - ax) * t, ay + (by - ay) * t]);
  }
  let best = 0;
  let score = -Infinity;
  points.forEach(([x, y], index) => {
    const value = x - Math.abs(y - faceY) * 0.8;
    if (value > score) {
      score = value;
      best = index;
    }
  });
  return [...points.slice(best), ...points.slice(0, best)];
}

const quarter = Math.PI / 2;

interface ShapeSpec {
  faceY: number;
  points: () => Point[];
}

const shapeSpecs: Record<Shape, ShapeSpec> = {
  circle: { faceY: 104, points: () => polar(100, 104, () => [58, 58]) },
  small: { faceY: 104, points: () => polar(100, 104, () => [52, 52]) },
  pebble: { faceY: 106, points: () => polar(100, 106, () => [64, 53]) },
  egg: { faceY: 100, points: () => polar(100, 102, (a) => [50 * (1 + 0.1 * Math.sin(a)), 62]) },
  seal: {
    faceY: 104,
    points: () =>
      polar(100, 104, (a) => {
        const radius = 60 * (1 + 0.05 * Math.cos(8 * a));
        return [radius, radius];
      }),
  },
  droop: { faceY: 106, points: () => polar(100, 108, (a) => [60 * (1 + 0.09 * Math.sin(a)), 52 + 5 * Math.sin(a)]) },
  shield: {
    faceY: 100,
    points: () =>
      sampleOutline(
        [
          line([100, 40], [154, 60]),
          cubic([154, 60], [156, 108], [136, 144], [100, 166]),
          cubic([100, 166], [64, 144], [44, 108], [46, 60]),
          line([46, 60], [100, 40]),
        ],
        96,
      ),
  },
  phone: {
    faceY: 104,
    points: () =>
      sampleOutline(
        [
          line([82, 40], [118, 40]),
          arc([118, 60], 20, -quarter, 0),
          line([138, 60], [138, 148]),
          arc([118, 148], 20, 0, quarter),
          line([118, 168], [82, 168]),
          arc([82, 148], 20, quarter, 2 * quarter),
          line([62, 148], [62, 60]),
          arc([82, 60], 20, 2 * quarter, 3 * quarter),
        ],
        104,
      ),
  },
};

const outlineCache = new Map<Shape, Point[]>();

export function outlineOf(shape: Shape): Point[] {
  let points = outlineCache.get(shape);
  if (!points) {
    points = shapeSpecs[shape].points();
    outlineCache.set(shape, points);
  }
  return points;
}

const fixed = (value: number) => value.toFixed(2);

export function smoothPath(points: readonly Point[]): string {
  const count = points.length;
  const at = (index: number) => points[(index + count) % count] as Point;
  const [x0, y0] = at(0);
  let d = `M${fixed(x0)} ${fixed(y0)}`;
  for (let index = 0; index < count; index++) {
    const p0 = at(index - 1);
    const p1 = at(index);
    const p2 = at(index + 1);
    const p3 = at(index + 2);
    d += ` C${fixed(p1[0] + (p2[0] - p0[0]) / 6)} ${fixed(p1[1] + (p2[1] - p0[1]) / 6)} ${fixed(p2[0] - (p3[0] - p1[0]) / 6)} ${fixed(p2[1] - (p3[1] - p1[1]) / 6)} ${fixed(p2[0])} ${fixed(p2[1])}`;
  }
  return `${d} Z`;
}

function channels(hex: string): [number, number, number] {
  return [1, 3, 5].map((index) => parseInt(hex.slice(index, index + 2), 16)) as [number, number, number];
}

export function mixHex(from: string, to: string, t: number): string {
  const a = channels(from);
  const b = channels(to);
  return `#${a.map((value, index) => Math.round(value + ((b[index] as number) - value) * t).toString(16).padStart(2, "0")).join("")}`;
}

export function luminance(hex: string): number {
  const [r, g, b] = channels(hex)
    .map((value) => value / 255)
    .map((value) => (value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4)) as [number, number, number];
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

const fallbacks: Record<Role, Role[]> = {
  fresh: ["fresh", "trust"],
  trust: ["trust", "calm"],
  warm: ["warm"],
  calm: ["calm"],
};

function blobIndexOf(role: Role, blobs: readonly PaletteBlob[]): number {
  for (const candidate of fallbacks[role]) {
    const index = blobs.findIndex((blob) => blob.role === candidate);
    if (index >= 0) return index;
  }
  return -1;
}

export interface Blob {
  x: number;
  y: number;
  r: number;
  opacity: number;
  color: string;
}

export interface Geometry {
  points: Point[];
  faceX: number;
  faceY: number;
  blobs: Blob[];
  veil: { x: number; y: number; color: string; opacity: number };
  rim: string;
  faceShadowOpacity: number;
  lead: string;
}

export const lookAuras: Partial<Record<WorkingLook, Aura>> = { warm: ["#ffc56b", "#6fd3b5"] };

export function auraOf(state: EntityState, look?: WorkingLook): Aura | undefined {
  return (look && stateSpecs[state].aura && lookAuras[look]) || stateSpecs[state].aura;
}

export function geometryOf(state: EntityState, colors: Palette = palette, aura = auraOf(state)): Geometry {
  const spec = stateSpecs[state];
  const faceX = 100;
  const { faceY } = shapeSpecs[spec.shape];
  const leads: number[] = [];
  for (const role of spec.lead) {
    const index = blobIndexOf(role, colors.blobs);
    if (index >= 0 && !leads.includes(index)) leads.push(index);
  }
  const phone = spec.shape === "phone";
  const blobs = colors.blobs.map((blob, index): Blob => {
    let dx = blob.dx * (phone ? 0.55 : 1);
    let dy = blob.dy * (phone ? 1.4 : 1);
    let r = blob.r;
    let opacity = blob.opacity;
    const rank = leads.indexOf(index);
    if (rank === 0) {
      dx *= 0.3;
      dy = dy * 0.3 - 4;
      r *= 1.5;
      opacity = 1;
    } else if (rank === 1) {
      dx *= 0.75;
      dy *= 0.75;
      r *= 1.18;
      opacity = 1;
    } else if (leads.length > 0) {
      const push = 1.35 + 10 / (Math.hypot(dx, dy) || 1);
      dx *= push;
      dy *= push;
      r *= 0.7;
      opacity *= 0.85;
    }
    const color = (aura && rank >= 0 ? aura[rank] : undefined) ?? blob.color;
    return { x: faceX + dx, y: faceY + dy, r, opacity, color };
  });
  const lead = aura?.[0] ?? colors.blobs[leads[0] ?? 0]?.color ?? "#000000";
  const light = luminance(lead);
  return {
    points: outlineOf(spec.shape),
    faceX,
    faceY,
    blobs,
    veil: {
      x: faceX,
      y: faceY + 4,
      color: mixHex(lead, "#000000", light > 0.4 ? 0.62 : 0.55),
      opacity: Math.min(0.85, 0.26 + light * 0.85),
    },
    rim: mixHex(lead, "#000000", 0.15),
    faceShadowOpacity: Math.min(0.8, 0.45 + light * 0.5),
    lead,
  };
}

const between = (a: number, b: number, t: number) => a + (b - a) * t;

export function interpolate(from: Geometry, to: Geometry, shapeT: number, colorT: number): Geometry {
  return {
    points: from.points.map(([x, y], index) => {
      const [tx, ty] = to.points[index] ?? [x, y];
      return [between(x, tx, shapeT), between(y, ty, shapeT)] as const;
    }),
    faceX: between(from.faceX, to.faceX, shapeT),
    faceY: between(from.faceY, to.faceY, shapeT),
    blobs: from.blobs.map((blob, index) => {
      const target = to.blobs[index] ?? blob;
      return {
        x: between(blob.x, target.x, colorT),
        y: between(blob.y, target.y, colorT),
        r: between(blob.r, target.r, colorT),
        opacity: between(blob.opacity, target.opacity, colorT),
        color: mixHex(blob.color, target.color, colorT),
      };
    }),
    veil: {
      x: between(from.veil.x, to.veil.x, colorT),
      y: between(from.veil.y, to.veil.y, colorT),
      color: mixHex(from.veil.color, to.veil.color, colorT),
      opacity: between(from.veil.opacity, to.veil.opacity, colorT),
    },
    rim: mixHex(from.rim, to.rim, colorT),
    faceShadowOpacity: to.faceShadowOpacity,
    lead: to.lead,
  };
}

export function ease(t: number): number {
  const clamped = Math.min(1, Math.max(0, t));
  return clamped < 0.5 ? 4 * clamped ** 3 : 1 - (-2 * clamped + 2) ** 3 / 2;
}

export const timings = { shape: 800, color: 900, face: 180 } as const;

export type FacePart =
  | { kind: "dot"; cx: number; cy: number; r: number }
  | { kind: "stroke"; d: string; width: number }
  | { kind: "fill"; d: string }
  | { kind: "oval"; cx: number; cy: number; rx: number; ry: number }
  | { kind: "tear"; d: string };

export function faceOf(state: EntityState, faceX: number, faceY: number): FacePart[] {
  const spec = stateSpecs[state];
  const eyeY = faceY - 6;
  const mouthY = faceY + 16;
  const left = faceX - 15;
  const right = faceX + 15;
  const width = 6;
  const pair = (dx: number, dy: number, r: number): FacePart[] => [
    { kind: "dot", cx: left + dx, cy: eyeY + dy, r },
    { kind: "dot", cx: right - (spec.eyes === "plead" ? dx : -dx), cy: eyeY + dy, r },
  ];
  const arcs = (y1: number, y2: number): FacePart => ({
    kind: "stroke",
    width,
    d: `M${left - 8} ${eyeY + y1} Q${left} ${eyeY + y2} ${left + 8} ${eyeY + y1}M${right - 8} ${eyeY + y1} Q${right} ${eyeY + y2} ${right + 8} ${eyeY + y1}`,
  });
  const eyes: Record<Eyes, FacePart[]> = {
    open: pair(0, 0, 6),
    wide: pair(0, 0, 7.5),
    side: [
      { kind: "dot", cx: left + 4, cy: eyeY - 2, r: 6 },
      { kind: "dot", cx: right + 4, cy: eyeY - 2, r: 6 },
    ],
    smile: [arcs(3, -7)],
    closed: [arcs(-2, 6)],
    plead: pair(1, -1, 7.5),
  };
  const mouths: Record<Mouth, FacePart> = {
    big: { kind: "fill", d: `M${faceX - 15} ${mouthY - 3} Q${faceX} ${mouthY + 16} ${faceX + 15} ${mouthY - 3} Z` },
    smile: { kind: "stroke", width, d: `M${faceX - 13} ${mouthY - 1} Q${faceX} ${mouthY + 12} ${faceX + 13} ${mouthY - 1}` },
    soft: { kind: "stroke", width, d: `M${faceX - 10} ${mouthY} Q${faceX} ${mouthY + 8} ${faceX + 10} ${mouthY}` },
    flat: { kind: "stroke", width, d: `M${faceX - 9} ${mouthY + 2} L${faceX + 9} ${mouthY + 2}` },
    o: { kind: "oval", cx: faceX, cy: mouthY + 3, rx: 5.5, ry: 6.5 },
    pout: { kind: "stroke", width, d: `M${faceX - 10} ${mouthY + 6} Q${faceX} ${mouthY - 2} ${faceX + 10} ${mouthY + 6}` },
  };
  const brows: FacePart[] =
    spec.brow === "raise"
      ? [{ kind: "stroke", width: 4.5, d: `M${right - 8} ${eyeY - 15} Q${right} ${eyeY - 21} ${right + 8} ${eyeY - 16}` }]
      : spec.brow === "plead"
        ? [
            {
              kind: "stroke",
              width: 4.5,
              d: `M${left - 9} ${eyeY - 13} Q${left - 1} ${eyeY - 16} ${left + 6} ${eyeY - 21}M${right + 9} ${eyeY - 13} Q${right + 1} ${eyeY - 16} ${right - 6} ${eyeY - 21}`,
            },
          ]
        : spec.brow === "focus"
          ? [
              {
                kind: "stroke",
                width: 4.5,
                d: `M${left - 2} ${eyeY - 16} Q${left + 4} ${eyeY - 18} ${left + 10} ${eyeY - 15}M${right + 10} ${eyeY - 16} Q${right + 4} ${eyeY - 18} ${right - 2} ${eyeY - 15}`,
              },
            ]
          : [];
  const tear: FacePart[] =
    spec.effect === "tear" ? [{ kind: "tear", d: `M${right + 6} ${eyeY + 9} q-4 6 0 9 q4 -3 0 -9z` }] : [];
  return [...eyes[spec.eyes], ...brows, mouths[spec.mouth], ...tear];
}
