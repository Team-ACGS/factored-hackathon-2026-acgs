import { useEffect, useId, useRef, useState, type CSSProperties } from "react";

import { cn } from "../lib/cn";
import {
  ease,
  faceOf,
  geometryOf,
  interpolate,
  palette,
  smoothPath,
  stateSpecs,
  timings,
  type EntityMode,
  type EntityState,
  type FacePart,
  type Geometry,
} from "../lib/entity";

export type EntityMotion = "idle" | "thinking";

interface ClaraEntityProps {
  state: EntityState;
  mode?: EntityMode;
  motion?: EntityMotion;
  label?: string;
  className?: string;
}

const colors = palette.blobs.map((blob) => blob.color);
const [calm, warm, trust] = colors as [string, string, string, string];
const paletteVars = { "--ce-calm": calm, "--ce-warm": warm, "--ce-trust": trust } as CSSProperties;

const specOf = (geometry: Geometry) => ({ cx: geometry.faceX - 24, cy: geometry.faceY - 36 });

function apply(svg: SVGSVGElement, geometry: Geometry) {
  const d = smoothPath(geometry.points);
  svg.querySelectorAll("[data-shape]").forEach((path) => path.setAttribute("d", d));
  svg.querySelectorAll<SVGCircleElement>("[data-blob]").forEach((circle) => {
    const blob = geometry.blobs[Number(circle.dataset.blob)];
    if (!blob) return;
    circle.setAttribute("cx", String(blob.x));
    circle.setAttribute("cy", String(blob.y));
    circle.setAttribute("r", String(blob.r));
    circle.setAttribute("opacity", String(blob.opacity));
    circle.setAttribute("fill", blob.color);
  });
  svg.querySelectorAll("[data-veil]").forEach((veil) => {
    veil.setAttribute("cx", String(geometry.veil.x));
    veil.setAttribute("cy", String(geometry.veil.y));
    veil.setAttribute("fill", geometry.veil.color);
    veil.setAttribute("opacity", String(geometry.veil.opacity));
  });
  svg.querySelector("[data-rim]")?.setAttribute("stroke", geometry.rim);
  svg.querySelector("[data-face-shadow]")?.setAttribute("flood-opacity", String(geometry.faceShadowOpacity));
  const spec = specOf(geometry);
  const highlight = svg.querySelector("[data-spec]");
  highlight?.setAttribute("cx", String(spec.cx));
  highlight?.setAttribute("cy", String(spec.cy));
  highlight?.setAttribute("transform", `rotate(-30 ${spec.cx} ${spec.cy})`);
}

export function ClaraEntity({ state, mode, motion, label, className }: ClaraEntityProps) {
  const id = useId().replace(/[^a-zA-Z0-9_-]/g, "");
  const svg = useRef<SVGSVGElement>(null);
  const [initial] = useState(() => geometryOf(state));
  const shown = useRef(initial);
  const target = useRef(state);
  const [face, setFace] = useState(state);

  useEffect(() => {
    const element = svg.current;
    if (!element || target.current === state) return;
    target.current = state;
    const from = shown.current;
    const to = geometryOf(state);
    const start = performance.now();
    let frame = 0;
    const step = (now: number) => {
      const elapsed = now - start;
      shown.current = interpolate(from, to, ease(elapsed / timings.shape), ease(elapsed / timings.color));
      apply(element, shown.current);
      if (elapsed < timings.color) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [state]);

  useEffect(() => {
    if (face === state) return;
    const timer = setTimeout(() => setFace(state), timings.face);
    return () => clearTimeout(timer);
  }, [face, state]);

  const spec = stateSpecs[state];
  const faceGeometry = geometryOf(face);
  const d = smoothPath(initial.points);
  const highlight = specOf(initial);
  const filter = (name: string) => `url(#${id}-${name})`;
  const activeMotion = motion === "thinking" ? "thinking" : spec.listens ? "listening" : motion;

  const body = (veil: boolean) => (
    <>
      <rect x="0" y="0" width="200" height="200" fill={palette.ground} />
      <g filter={filter("b10")}>
        <g className="ce-blobs">
          {initial.blobs.map((blob, index) => (
            <circle
              key={index}
              data-blob={index}
              cx={blob.x}
              cy={blob.y}
              r={blob.r}
              fill={blob.color}
              opacity={blob.opacity}
            />
          ))}
        </g>
      </g>
      {veil && (
        <ellipse
          data-veil
          cx={initial.veil.x}
          cy={initial.veil.y}
          rx="32"
          ry="27"
          fill={initial.veil.color}
          opacity={initial.veil.opacity}
          filter={filter("b9")}
        />
      )}
    </>
  );

  return (
    <span
      className={cn("clara-entity", className)}
      data-mode={mode}
      data-motion={activeMotion}
      style={paletteVars}
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
    >
      <svg ref={svg} viewBox="-20 -20 240 240" aria-hidden="true" focusable="false">
        <defs>
          {(
            [
              ["b10", 10, 50],
              ["b9", 9, 50],
              ["b2", 2.5, 50],
              ["b6", 6, 50],
              ["soft", 5, 50],
              ["bloom", 15, 60],
            ] as const
          ).map(([name, deviation, margin]) => (
            <filter
              key={name}
              id={`${id}-${name}`}
              x={`-${margin}%`}
              y={`-${margin}%`}
              width={`${100 + 2 * margin}%`}
              height={`${100 + 2 * margin}%`}
            >
              <feGaussianBlur stdDeviation={deviation} />
            </filter>
          ))}
          <filter id={`${id}-fs`} x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow
              data-face-shadow
              dx="0"
              dy="1.2"
              stdDeviation="1.8"
              floodColor="#0b2a24"
              floodOpacity={initial.faceShadowOpacity}
            />
          </filter>
          <clipPath id={`${id}-s`}>
            <path data-shape d={d} />
          </clipPath>
        </defs>
        <ellipse className="ce-shadow" cx="100" cy="188" rx="52" ry="7" fill="#0f2a24" opacity=".12" filter={filter("b6")} />
        <g className="ce-fx">
          <Effect state={state} />
        </g>
        <g transform="translate(100 104) scale(1.24) translate(-100 -104)">
          <g className="ce-breathe">
            <g className={spec.shakes ? "ce-shake" : undefined}>
              <g filter={filter("bloom")} opacity=".55">
                <g clipPath={`url(#${id}-s)`}>{body(false)}</g>
              </g>
              <g filter={filter("soft")}>
                <g clipPath={`url(#${id}-s)`}>{body(true)}</g>
              </g>
              <path data-shape data-rim d={d} fill="none" stroke={initial.rim} strokeOpacity=".3" strokeWidth="1.1" />
              <g clipPath={`url(#${id}-s)`}>
                <path data-shape d={d} fill="none" stroke="#ffffff" strokeOpacity=".5" strokeWidth="3" />
              </g>
              <ellipse
                data-spec
                cx={highlight.cx}
                cy={highlight.cy}
                rx="13"
                ry="5.5"
                transform={`rotate(-30 ${highlight.cx} ${highlight.cy})`}
                fill="#ffffff"
                opacity=".45"
                filter={filter("b2")}
              />
              <g className="ce-deco">
                {spec.phone && (
                  <>
                    <path d="M90 50 H110" stroke="#ffffff" strokeOpacity=".75" strokeWidth="3.5" strokeLinecap="round" />
                    <path d="M92 159 H108" stroke="#ffffff" strokeOpacity=".6" strokeWidth="3" strokeLinecap="round" />
                  </>
                )}
              </g>
              <g className="ce-face" filter={filter("fs")} opacity={face === state ? 1 : 0}>
                {faceOf(face, faceGeometry.faceX, faceGeometry.faceY).map((part, index) => (
                  <FaceShape key={`${face}-${index}`} part={part} />
                ))}
              </g>
            </g>
          </g>
        </g>
      </svg>
    </span>
  );
}

function FaceShape({ part }: { part: FacePart }) {
  switch (part.kind) {
    case "dot":
      return <circle cx={part.cx} cy={part.cy} r={part.r} fill="#ffffff" />;
    case "oval":
      return <ellipse cx={part.cx} cy={part.cy} rx={part.rx} ry={part.ry} fill="#ffffff" />;
    case "fill":
      return <path d={part.d} fill="#ffffff" />;
    case "tear":
      return <path className="ce-tear" d={part.d} fill="#ffffff" />;
    case "stroke":
      return <path d={part.d} fill="none" stroke="#ffffff" strokeWidth={part.width} strokeLinecap="round" />;
  }
}

function Effect({ state }: { state: EntityState }) {
  switch (stateSpecs[state].effect) {
    case "rings":
      return (
        <g fill="none" strokeWidth="2.5">
          {[trust, warm, calm].map((color, index) => (
            <circle key={color} className="ce-radar" style={{ animationDelay: `${index * 0.7}s` }} cx="100" cy="104" r="76" stroke={color} />
          ))}
        </g>
      );
    case "orbit":
      return (
        <g className="ce-orbit">
          <circle cx="100" cy="20" r="6" fill={calm} />
          <circle cx="172" cy="146" r="5" fill={warm} />
          <circle cx="28" cy="146" r="4.5" fill={trust} />
        </g>
      );
    case "spark":
      return (
        <g>
          <path className="ce-spark" fill={warm} d="M168 34 l4 10 10 4 -10 4 -4 10 -4 -10 -10 -4 10 -4z" />
          <path
            className="ce-spark"
            style={{ animationDelay: ".6s" }}
            fill={trust}
            d="M30 52 l3 7 7 3 -7 3 -3 7 -3 -7 -7 -3 7 -3z"
          />
        </g>
      );
    case "call":
      return (
        <g fill="none" stroke={trust} strokeWidth="3.5" strokeLinecap="round">
          <path className="ce-callwave" d="M160 86 Q168 104 160 122" />
          <path className="ce-callwave ce-late" d="M172 76 Q184 104 172 132" />
          <path className="ce-callwave" d="M40 86 Q32 104 40 122" />
          <path className="ce-callwave ce-late" d="M28 76 Q16 104 28 132" />
        </g>
      );
    default:
      return null;
  }
}

export function ClaraGlyph({ className }: { className?: string }) {
  const id = useId().replace(/[^a-zA-Z0-9_-]/g, "");
  const [calmBlob, warmBlob, trustBlob, freshBlob] = colors;
  return (
    <svg viewBox="0 0 40 40" aria-hidden="true" focusable="false" className={cn("size-[26px] shrink-0", className)}>
      <defs>
        <filter id={`${id}-g`} x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="3" />
        </filter>
        <clipPath id={`${id}-c`}>
          <circle cx="20" cy="20" r="15" />
        </clipPath>
      </defs>
      <g clipPath={`url(#${id}-c)`}>
        <rect width="40" height="40" fill={palette.ground} />
        <g filter={`url(#${id}-g)`}>
          <circle cx="15" cy="17" r="10" fill={warmBlob} />
          <circle cx="25" cy="23" r="9" fill={trustBlob} />
          <circle cx="21" cy="11" r="7" fill={calmBlob} />
          <circle cx="18" cy="28" r="6" fill={freshBlob} />
        </g>
      </g>
      <circle cx="20" cy="20" r="15" fill="none" stroke="#ffffff" strokeOpacity=".7" strokeWidth="1.4" />
    </svg>
  );
}
