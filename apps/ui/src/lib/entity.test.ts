import { describe, expect, it } from "vitest";

import {
  SAMPLES,
  auraOf,
  entityStates,
  faceOf,
  geometryOf,
  interpolate,
  luminance,
  outlineOf,
  palette,
  smoothPath,
  stateSpecs,
  type Point,
  type WorkingLook,
} from "./entity";

const distance = (a: Point, b: Point) => Math.hypot(a[0] - b[0], a[1] - b[1]);

function gaps(points: readonly Point[]): number[] {
  return points.map((point, index) => distance(point, points[(index + 1) % points.length] as Point));
}

describe("outlines", () => {
  it.each(entityStates)("samples %s into the same number of points so any shape morphs into any other", (state) => {
    const { points } = geometryOf(state);
    expect(points).toHaveLength(SAMPLES);
    expect(smoothPath(points).match(/ C/g)).toHaveLength(SAMPLES);
  });

  it.each(["shield", "phone"] as const)("samples the %s outline at even steps along its length", (shape) => {
    const steps = gaps(outlineOf(shape));
    const mean = steps.reduce((sum, step) => sum + step, 0) / steps.length;
    expect(Math.max(...steps)).toBeLessThan(mean * 1.05);
  });

  it("starts every outline at its rightmost point level with the face, so morphs do not twist", () => {
    for (const state of entityStates) {
      const { points, faceY } = geometryOf(state);
      const [startX, startY] = points[0] as Point;
      const maxX = Math.max(...points.map(([x]) => x));
      expect(maxX - startX).toBeLessThan(3);
      expect(Math.abs(startY - faceY)).toBeLessThan(12);
    }
  });
});

describe("the color that leads", () => {
  it("grows the first lead toward the face and pushes the others aside, dimmer", () => {
    const { blobs } = geometryOf("confirma");
    const warmIndex = palette.blobs.findIndex((blob) => blob.role === "warm");
    const warm = palette.blobs[warmIndex];
    expect(blobs[warmIndex]?.r).toBeCloseTo((warm?.r ?? 0) * 1.5);
    expect(blobs[warmIndex]?.opacity).toBe(1);
    palette.blobs.forEach((blob, index) => {
      if (index === warmIndex) return;
      const moved = blobs[index];
      expect(moved?.r).toBeCloseTo(blob.r * 0.7);
      expect(moved?.opacity).toBeCloseTo(blob.opacity * 0.85);
      expect(Math.hypot((moved?.x ?? 0) - 100, (moved?.y ?? 0) - 100)).toBeGreaterThan(Math.hypot(blob.dx, blob.dy));
    });
  });

  it("falls back to trust when a palette has no fresh color", () => {
    const withoutFresh = { ...palette, blobs: palette.blobs.filter((blob) => blob.role !== "fresh") };
    const { lead } = geometryOf("escucha", withoutFresh);
    expect(lead).toBe(palette.blobs.find((blob) => blob.role === "trust")?.color);
  });

  it("lights Revisando with its own aura, and a warmer one while it reads the cases", () => {
    const leads = (look?: WorkingLook) =>
      [...geometryOf("revisa", palette, auraOf("revisa", look)).blobs].sort((a, b) => b.r - a.r).map((blob) => blob.color);
    expect(leads().slice(0, 2)).toEqual(["#6fd3b5", "#9be7ff"]);
    expect(leads("sweep").slice(0, 2)).toEqual(["#6fd3b5", "#9be7ff"]);
    expect(leads("warm").slice(0, 2)).toEqual(["#ffc56b", "#6fd3b5"]);
    expect(geometryOf("revisa").lead).toBe("#6fd3b5");
    expect(auraOf("hola", "warm")).toBeUndefined();
  });

  it("darkens the veil behind the face more when the lead color is lighter", () => {
    const light = geometryOf("escucha");
    const dark = geometryOf("orden");
    expect(luminance(light.lead)).toBeGreaterThan(luminance(dark.lead));
    expect(light.veil.opacity).toBeGreaterThan(dark.veil.opacity);
    expect(light.veil.opacity).toBeLessThanOrEqual(0.85);
  });
});

describe("interpolate", () => {
  const from = geometryOf("hola");
  const to = geometryOf("protege");

  it("starts at the current geometry and ends at the target", () => {
    expect(interpolate(from, to, 0, 0).points).toEqual(from.points);
    expect(interpolate(from, to, 1, 1).points).toEqual(to.points);
    expect(interpolate(from, to, 1, 1).blobs.map((blob) => blob.r)).toEqual(to.blobs.map((blob) => blob.r));
    expect(interpolate(from, to, 1, 1).veil.color).toBe(to.veil.color);
  });

  it("moves shape and color on their own clocks", () => {
    const halfway = interpolate(from, to, 1, 0);
    expect(halfway.points).toEqual(to.points);
    expect(halfway.blobs.map((blob) => blob.x)).toEqual(from.blobs.map((blob) => blob.x));
  });
});

describe("faces", () => {
  it("draws the brows a state declares, focused for Revisando", () => {
    for (const state of entityStates) {
      const brows = faceOf(state, 100, 104).filter((part) => part.kind === "stroke" && part.width === 4.5);
      expect(brows.length > 0).toBe(stateSpecs[state].brow !== undefined);
    }
    expect(stateSpecs.revisa.brow).toBe("focus");
  });

  it("sheds a tear only when Clara asks a favor", () => {
    for (const state of entityStates) {
      const parts = faceOf(state, 100, 104);
      expect(parts.some((part) => part.kind === "tear")).toBe(stateSpecs[state].effect === "tear");
    }
  });
});
