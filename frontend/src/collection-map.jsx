// 봄내 조각지도 (#100) — 홈 카드 「봄내 조각 N/M」 + 전체 화면 모달 '봄내 조각 컬렉션'.
// 디자인 정본: design/prototype.html v4 (토큰·레이아웃 동일). 단, v4의 정적 외곽 잠금은
// #100 단계3대로 zone_map(계약 §5) 동적 판정으로 교체:
//   채움 = collected(주색) / 미채움 = available−collected(점선) / 준비 중 = GeoJSON−available(빗금+자물쇠)
// 지오메트리는 대시보드 접근성 GeoJSON 재사용(별도 API 없음). "잠김·불가" 표현 금지 —
// 준비 중 동은 탭 시 "아직 준비 중인 동네예요" 안내만.
import React from "react";
import { api } from "./api/client";

const BLUE = "#0E87C4";
const NAVY = "#0B3A52";
const SUB = "#5E6B72";
const FAINT = "#93A0A8";

// 도심 수집판 14개 동 (design/prototype.html v4 확정 — 외곽 읍·면·신사우동은 '준비 중')
const CORE_DONGS = ["교동", "근화동", "소양동", "약사명동", "조운동", "효자1동", "효자2동", "효자3동", "후평1동", "후평2동", "후평3동", "석사동", "퇴계동", "강남동"];
const dongName = (f) => (f.properties?.name ?? "").split(" ").pop();
export const isCore = (f) => CORE_DONGS.includes(dongName(f));

const MILESTONES = [
  { at: 5, label: "동네 수집가" },
  { at: 10, label: "골목 탐험가" },
];

export function useCollection() {
  const [zoneMap, setZoneMap] = React.useState({ collected: [], available: [] });
  const [features, setFeatures] = React.useState([]);
  React.useEffect(() => {
    let alive = true;
    Promise.all([api.getRecords().catch(() => null), api.getDashboardAccessibility().catch(() => null)]).then(
      ([records, geo]) => {
        if (!alive) return;
        if (records?.zone_map) setZoneMap(records.zone_map);
        if (geo?.features) setFeatures(geo.features);
      },
    );
    return () => { alive = false; };
  }, []);
  return { zoneMap, features };
}

function allRings(geometry) {
  if (!geometry) return [];
  if (geometry.type === "Polygon") return geometry.coordinates;
  if (geometry.type === "MultiPolygon") return geometry.coordinates.flat();
  return [];
}

function ringPoints(geometry) {
  let best = [];
  for (const r of allRings(geometry)) if (r.length > best.length) best = r;
  return best;
}

function makeProjector(featureList, w = 360, h = 300, pad = 10) {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const f of featureList) for (const ring of allRings(f.geometry)) for (const [x, y] of ring) {
    if (x < minX) minX = x; if (x > maxX) maxX = x;
    if (y < minY) minY = y; if (y > maxY) maxY = y;
  }
  if (!Number.isFinite(minX)) return null;
  const scale = Math.min((w - pad * 2) / (maxX - minX || 1), (h - pad * 2) / (maxY - minY || 1));
  const ox = (w - (maxX - minX) * scale) / 2, oy = (h - (maxY - minY) * scale) / 2;
  const px = ([x, y]) => [ox + (x - minX) * scale, h - (oy + (y - minY) * scale)];
  return {
    path(feature) {
      return allRings(feature.geometry)
        .map((ring) => {
          const pts = ring.map(px);
          return pts.length ? `M${pts.map((p) => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join("L")}Z` : "";
        })
        .join("");
    },
    centroid(feature) {
      const pts = ringPoints(feature.geometry).map(px);
      if (!pts.length) return [0, 0];
      return [pts.reduce((s, p) => s + p[0], 0) / pts.length, pts.reduce((s, p) => s + p[1], 0) / pts.length];
    },
  };
}

function stateOf(feature, zoneMap) {
  const code = feature.properties?.zone_code;
  if (zoneMap.collected.includes(code)) return "filled";
  return isCore(feature) ? "open" : "locked";
}

const PIECE_STYLE = {
  filled: { fill: BLUE, stroke: "#0C74A9", dash: "none", label: "#fff" },
  open: { fill: "#EAF0F3", stroke: "#CBD8DF", dash: "4 3", label: SUB },
  locked: { fill: "url(#collectionHatch)", stroke: "#D3DDE2", dash: "none", label: "#8A96A0" },
};

function PieceSvg({ featureList, zoneMap, onLockedTap, showLockIcon, hideCoreLabels }) {
  const projector = React.useMemo(() => makeProjector(featureList), [featureList]);
  if (!projector) {
    return <div style={{ padding: "36px 0", textAlign: "center", font: `500 12px Pretendard,sans-serif`, color: FAINT }}>지도를 준비하고 있어요</div>;
  }
  return (
    <div style={{ position: "relative" }}>
      <svg viewBox="0 0 360 300" style={{ width: "100%", display: "block" }}>
        <defs>
          <pattern id="collectionHatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="6" height="6" fill="#EDF1F4" />
            <line x1="0" y1="0" x2="0" y2="6" stroke="#D3DDE2" strokeWidth="2" />
          </pattern>
        </defs>
        {featureList.map((f) => {
          const s = PIECE_STYLE[stateOf(f, zoneMap)];
          return (
            <path key={f.properties?.zone_code} d={projector.path(f)} fill={s.fill} stroke={s.stroke} strokeWidth="1.2" strokeDasharray={s.dash} strokeLinejoin="round" strokeLinecap="round" fillRule="evenodd" onClick={stateOf(f, zoneMap) === "locked" ? onLockedTap : undefined} style={stateOf(f, zoneMap) === "locked" ? { cursor: "pointer" } : undefined} />
          );
        })}
        {featureList.map((f) => {
          const st = stateOf(f, zoneMap);
          const [cx, cy] = projector.centroid(f);
          if (st === "locked" && showLockIcon) {
            return (
              <g key={`lock-${f.properties?.zone_code}`} transform={`translate(${cx},${cy})`} pointerEvents="none">
                <rect x="-5" y="-6" width="10" height="8" rx="2" fill={FAINT} />
                <path d="M-3,-6 v-2 a3,3 0 0 1 6,0 v2" stroke={FAINT} strokeWidth="1.8" fill="none" />
                <text x="0" y="14" textAnchor="middle" style={{ font: "600 9px Pretendard,sans-serif", fill: "#8A96A0" }}>{dongName(f)}</text>
              </g>
            );
          }
          if (hideCoreLabels) return null;
          return (
            <text key={`label-${f.properties?.zone_code}`} x={cx} y={cy} textAnchor="middle" pointerEvents="none" style={{ font: "700 9px Pretendard,sans-serif", fill: PIECE_STYLE[st].label }}>
              {dongName(f)}
            </text>
          );
        })}
      </svg>
    </div>
  );
}

function coreProgress(zoneMap, features) {
  const coreCodes = features.filter(isCore).map((f) => f.properties?.zone_code);
  const n = zoneMap.collected.filter((c) => coreCodes.includes(c)).length;
  return { n, m: coreCodes.length || CORE_DONGS.length };
}

export function CollectionCard({ onOpen }) {
  const { zoneMap, features } = useCollection();
  const { n, m } = coreProgress(zoneMap, features);
  const squares = Array.from({ length: 10 }, (_, i) => (m > 0 && i < Math.round((n / m) * 10) ? BLUE : "#EAF0F3"));
  const hint = m > 0 && n >= m ? "완성! 리워드를 확인하세요" : "동 조각을 모아 춘천을 완성해 보세요";
  return (
    <div onClick={onOpen} role="button" tabIndex={0} onKeyDown={(e) => e.key === "Enter" && onOpen()} style={{ marginTop: 14, background: "#fff", border: "1px solid #DFE6EA", borderRadius: 14, padding: "11px 14px", display: "flex", alignItems: "center", gap: 12, cursor: "pointer" }}>
      <svg width="40" height="33" viewBox="0 0 48 40">
        {squares.map((c, i) => (
          <rect key={i} x={(i % 5) * 10} y={i < 5 ? 3 : 20} width="8" height="11" rx="2" fill={c} />
        ))}
      </svg>
      <div style={{ flex: 1 }}>
        <div style={{ font: "700 13px Pretendard,sans-serif", color: NAVY }}>
          봄내 조각 <span style={{ color: BLUE }}>{n}/{m || "—"}</span>
        </div>
        <div style={{ font: "500 11px Pretendard,sans-serif", color: FAINT, marginTop: 1 }}>{hint}</div>
      </div>
      <div style={{ font: "700 16px Pretendard,sans-serif", color: "#7A8790" }}>›</div>
    </div>
  );
}

export function CollectionModal({ onClose }) {
  const { zoneMap, features } = useCollection();
  const [notice, setNotice] = React.useState("");
  const { n, m } = coreProgress(zoneMap, features);
  const complete = m > 0 && n >= m;
  const coreFeatures = features.filter(isCore);
  const lockedTap = () => {
    setNotice("아직 준비 중인 동네예요");
    window.setTimeout(() => setNotice(""), 1800);
  };
  const chips = [
    ...MILESTONES.map(({ at, label }) => ({ label, done: n >= at, sub: n >= at ? "달성" : `${Math.min(n, at)}/${at}` })),
    { label: "봄내 완주", done: complete, sub: complete ? "달성" : `${n}/${m || "—"}` },
  ];
  return (
    <div onClick={onClose} style={{ position: "fixed", top: 0, bottom: 0, left: "50%", width: "min(100%, 430px)", transform: "translateX(-50%)", background: "rgba(10,26,36,.55)", display: "flex", alignItems: "flex-end", zIndex: 55, backdropFilter: "blur(2px)" }}>
      <div onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" style={{ background: "#fff", borderRadius: "22px 22px 0 0", padding: "22px 20px 30px", width: "100%", boxSizing: "border-box", maxHeight: "86%", overflowY: "auto" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ font: "800 18px Pretendard,sans-serif", color: NAVY }}>봄내 조각 컬렉션</div>
          <div onClick={onClose} role="button" tabIndex={0} onKeyDown={(e) => e.key === "Enter" && onClose()} style={{ width: 32, height: 32, borderRadius: "50%", background: "#EEF3F5", font: "600 15px/32px Pretendard,sans-serif", textAlign: "center", cursor: "pointer", color: SUB }}>✕</div>
        </div>
        <div style={{ font: "500 12.5px/1.5 Pretendard,sans-serif", color: SUB, marginTop: 5 }}>
          퀘스트를 완주한 동의 조각이 채워져요. {m || "—"}조각을 모으면 리워드!
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 12 }}>
          <div style={{ flex: 1, height: 8, borderRadius: 99, background: "#EAF0F3", overflow: "hidden" }}>
            <div style={{ width: m ? `${Math.min(100, (n / m) * 100)}%` : 0, height: "100%", background: BLUE, borderRadius: 99 }} />
          </div>
          <div style={{ font: "800 13px Pretendard,sans-serif", color: BLUE, flex: "none" }}>{n}/{m || "—"}</div>
        </div>

        <div style={{ position: "relative", marginTop: 14, background: "#F7FAFB", border: "1px solid #EAF0F3", borderRadius: 14, overflow: "hidden" }}>
          <PieceSvg featureList={coreFeatures} zoneMap={zoneMap} />
          <div style={{ position: "absolute", top: 10, left: 12, background: "rgba(255,255,255,.92)", borderRadius: 8, padding: "4px 9px", font: "700 10.5px Pretendard,sans-serif", color: NAVY }}>도심 — 조각을 모으는 동네</div>
        </div>

        <div style={{ font: "700 12px Pretendard,sans-serif", color: "#7A8790", marginTop: 14 }}>
          춘천시 전체 <span style={{ fontWeight: 500, color: FAINT }}>— 실제 행정동 경계 · 외곽은 준비 중</span>
        </div>
        <div style={{ marginTop: 6 }}>
          <PieceSvg featureList={features} zoneMap={zoneMap} onLockedTap={lockedTap} showLockIcon hideCoreLabels />
        </div>

        <div style={{ display: "flex", gap: 12, marginTop: 8, justifyContent: "center" }}>
          {[["모은 조각", { background: BLUE }], ["미획득", { background: "#EAF0F3", border: "1px dashed #CBD8DF", boxSizing: "border-box" }], ["준비 중", { background: "repeating-linear-gradient(45deg,#EDF1F4,#EDF1F4 2px,#D3DDE2 2px,#D3DDE2 3px)" }]].map(([label, style]) => (
            <div key={label} style={{ display: "flex", alignItems: "center", gap: 5, font: "500 11px Pretendard,sans-serif", color: SUB }}>
              <span style={{ width: 10, height: 10, borderRadius: 3, ...style }} />{label}
            </div>
          ))}
        </div>

        <div style={{ display: "flex", gap: 8, marginTop: 14, flexWrap: "wrap" }}>
          {chips.map((chip) => (
            <div key={chip.label} style={{ padding: "8px 12px", borderRadius: 999, font: "600 12px Pretendard,sans-serif", background: chip.done ? BLUE : "#F1F5F7", color: chip.done ? "#fff" : SUB, border: `1px solid ${chip.done ? BLUE : "#DFE6EA"}` }}>
              {chip.done ? "✦ " : ""}{chip.label} <span style={{ opacity: 0.75, fontWeight: 500 }}>{chip.sub}</span>
            </div>
          ))}
        </div>

        {complete ? (
          <div style={{ marginTop: 14, background: "linear-gradient(135deg,#F5B935,#C98A1B)", borderRadius: 14, padding: "15px 16px", color: "#fff" }}>
            <div style={{ font: "800 15px Pretendard,sans-serif" }}>춘천 한 바퀴 완성! 🏅</div>
            <div style={{ font: "500 12.5px/1.5 Pretendard,sans-serif", marginTop: 4, color: "rgba(255,255,255,.9)" }}>
              춘천사랑상품권 5,000원 신청 대상이에요 — 신청 시 최소한의 본인 확인이 필요하며, 1인 1회 제공돼요.
            </div>
          </div>
        ) : (
          <div style={{ marginTop: 14, background: "#E7F3FA", borderRadius: 12, padding: "12px 14px", font: "500 12px/1.55 Pretendard,sans-serif", color: "#2A5670" }}>
            도심 {m || "—"}개 동을 모두 모으면 <b>춘천사랑상품권 5,000원</b>을 신청할 수 있어요. 외곽 읍·면 지역은 준비 중이에요.
          </div>
        )}

        {notice && (
          <div style={{ position: "fixed", left: "50%", bottom: 42, transform: "translateX(-50%)", background: NAVY, color: "#fff", borderRadius: 99, padding: "9px 16px", font: "600 12.5px Pretendard,sans-serif", zIndex: 60 }}>{notice}</div>
        )}
      </div>
    </div>
  );
}


// ---- 조각 획득 연출 (#100 — v4 pieceReveal) ----------------------------------
function pointInRing(ring, lng, lat) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i], [xj, yj] = ring[j];
    if (yi > lat !== yj > lat && lng < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

export function findDongByPoint(features, lat, lng) {
  // 활동 좌표가 속한 행정동 — 서버·계약 변경 없이 클라이언트 점포함 판정
  for (const f of features) {
    const g = f.geometry;
    const polys = g?.type === "Polygon" ? [g.coordinates] : g?.type === "MultiPolygon" ? g.coordinates : [];
    for (const poly of polys) if (poly[0] && pointInRing(poly[0], lng, lat)) return f;
  }
  return null;
}

export function PieceRevealModal({ feature, features, zoneMap, onDone }) {
  const { n, m } = coreProgress(zoneMap, features);
  const code = feature.properties?.zone_code;
  const already = zoneMap.collected.includes(code);
  const count = Math.min(m, n + (already || !isCore(feature) ? 0 : 1));
  const projector = makeProjector(features);
  return (
    <div style={{ position: "fixed", top: 0, bottom: 0, left: "50%", width: "min(100%, 430px)", transform: "translateX(-50%)", background: "rgba(10,26,36,.6)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 58, backdropFilter: "blur(3px)" }}>
      <div style={{ background: "#fff", borderRadius: 22, padding: "24px 22px", width: "84%", textAlign: "center" }}>
        <div style={{ font: "700 11.5px Pretendard,sans-serif", color: BLUE, letterSpacing: 1 }}>봄내 조각</div>
        <div style={{ font: "800 19px Pretendard,sans-serif", color: NAVY, marginTop: 4 }}>{dongName(feature)} 조각 획득!</div>
        <div style={{ position: "relative", marginTop: 12, background: "#F7FAFB", borderRadius: 14, overflow: "hidden" }}>
          {projector && (
            <svg viewBox="0 0 360 300" style={{ width: "100%", display: "block" }}>
              <defs>
                <pattern id="revealHatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                  <rect width="6" height="6" fill="#EDF1F4" />
                  <line x1="0" y1="0" x2="0" y2="6" stroke="#D3DDE2" strokeWidth="2" />
                </pattern>
              </defs>
              {features.filter((f) => f !== feature).map((f) => {
                const st = stateOf(f, zoneMap);
                const fill = st === "filled" ? "#BBDDF0" : st === "open" ? "#EAF0F3" : "url(#revealHatch)";
                return <path key={f.properties?.zone_code} d={projector.path(f)} fill={fill} stroke="#D3DDE2" strokeWidth="1" strokeDasharray={st === "open" ? "4 3" : "none"} fillRule="evenodd" />;
              })}
              <path className="piece-in" d={projector.path(feature)} fill={BLUE} stroke="#fff" strokeWidth="2" fillRule="evenodd" />
              {(() => { const [cx, cy] = projector.centroid(feature); return <text x={cx} y={cy} textAnchor="middle" style={{ font: "700 11px Pretendard,sans-serif", fill: "#fff", textShadow: "0 1px 3px rgba(10,26,36,.4)" }}>{dongName(feature)}</text>; })()}
            </svg>
          )}
        </div>
        <div style={{ font: "600 13px Pretendard,sans-serif", color: SUB, marginTop: 10 }}>
          봄내 조각 <span style={{ color: BLUE, fontWeight: 800 }}>{count}/{m || "—"}</span>
        </div>
        <div onClick={onDone} role="button" tabIndex={0} onKeyDown={(e) => e.key === "Enter" && onDone()} style={{ marginTop: 16, background: BLUE, color: "#fff", borderRadius: 12, padding: "14px 0", font: "700 14px Pretendard,sans-serif", cursor: "pointer" }}>확인</div>
      </div>
    </div>
  );
}
