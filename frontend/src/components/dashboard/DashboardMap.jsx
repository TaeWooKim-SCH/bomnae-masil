import React from "react";

export const ACCESSIBILITY_COLORS = { 1: "#dceff7", 2: "#acd9e9", 3: "#70b9d5", 4: "#3388b0", 5: "#0b587d" };
export const INFLOW_COLORS = { "확정저유입": "#c84e3a", "추정후보": "#d79545", "일반": "#5b9a87", "붐빔": "#6e7c86" };
const CLUSTERING_THRESHOLD = 200;

function createMarkerImage(kakao, color) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14"><circle cx="7" cy="7" r="5" fill="${color}" stroke="white" stroke-width="2"/></svg>`;
  return new kakao.maps.MarkerImage(`data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`, new kakao.maps.Size(14, 14), { offset: new kakao.maps.Point(7, 7) });
}

function renderAccessibilityLayer(kakao, map, bounds, feature, registerOverlay, setMapStatus) {
  const geometry = feature.geometry;
  const polygons = geometry.type === "MultiPolygon" ? geometry.coordinates : [geometry.coordinates];
  const hoverLabel = document.createElement("div");
  hoverLabel.className = "dashboard-zone-label";
  const hoverOverlay = new kakao.maps.CustomOverlay({ content: hoverLabel, yAnchor: 1.35 });
  registerOverlay(hoverOverlay);

  polygons.forEach((rings) => {
    const paths = rings.map((ring) => ring.map(([lng, lat]) => {
      const point = new kakao.maps.LatLng(lat, lng);
      bounds.extend(point);
      return point;
    }));
    const polygon = new kakao.maps.Polygon({
      map,
      path: paths.length === 1 ? paths[0] : paths,
      strokeWeight: 1.5,
      strokeColor: "#fff",
      strokeOpacity: .9,
      fillColor: ACCESSIBILITY_COLORS[feature.properties.quintile] ?? ACCESSIBILITY_COLORS[1],
      fillOpacity: .58,
    });
    registerOverlay(polygon);
    const showZone = (event) => {
      hoverLabel.textContent = `${feature.properties.name} · ${feature.properties.score}점`;
      hoverOverlay.setPosition(event.latLng);
      hoverOverlay.setMap(map);
    };
    const hideZone = () => hoverOverlay.setMap(null);
    kakao.maps.event.addListener(polygon, "mouseover", showZone);
    kakao.maps.event.addListener(polygon, "mouseout", hideZone);
    kakao.maps.event.addListener(polygon, "click", (event) => {
      showZone(event);
      setMapStatus(`${feature.properties.name} 접근성 점수는 ${feature.properties.score}점이에요.`);
    });
  });
}

function renderInflowLayer(kakao, map, bounds, features, registerOverlay) {
  const useClustering = features.length > CLUSTERING_THRESHOLD && kakao.maps.MarkerClusterer;
  const markerImages = new Map();
  const getMarkerImage = (status) => {
    const color = INFLOW_COLORS[status] ?? INFLOW_COLORS.일반;
    if (!markerImages.has(color)) markerImages.set(color, createMarkerImage(kakao, color));
    return markerImages.get(color);
  };

  if (useClustering) {
    const detailLabel = document.createElement("div");
    detailLabel.className = "dashboard-store-label";
    const detailOverlay = new kakao.maps.CustomOverlay({ yAnchor: 2.2, xAnchor: .5, content: detailLabel });
    registerOverlay(detailOverlay);
    const markers = features.map((feature) => {
      const [lng, lat] = feature.geometry.coordinates;
      const position = new kakao.maps.LatLng(lat, lng);
      bounds.extend(position);
      const marker = new kakao.maps.Marker({ position, image: getMarkerImage(feature.properties.inflow_status), title: feature.properties.name });
      kakao.maps.event.addListener(marker, "click", () => {
        detailLabel.textContent = `${feature.properties.name} · ${feature.properties.category}`;
        detailOverlay.setPosition(position);
        detailOverlay.setMap(map);
      });
      return marker;
    });
    const clusterer = new kakao.maps.MarkerClusterer({ map, averageCenter: true, minLevel: 7, minClusterSize: 4, markers });
    registerOverlay({ clear: () => clusterer.clear() });
    return;
  }

  features.forEach((feature) => {
    const [lng, lat] = feature.geometry.coordinates;
    const position = new kakao.maps.LatLng(lat, lng);
    bounds.extend(position);
    const dot = document.createElement("span");
    dot.className = "dashboard-store-dot";
    dot.style.background = INFLOW_COLORS[feature.properties.inflow_status] ?? INFLOW_COLORS.일반;
    const label = document.createElement("div");
    label.className = "dashboard-store-label";
    label.textContent = `${feature.properties.name} · ${feature.properties.category}`;
    registerOverlay(new kakao.maps.CustomOverlay({ map, position, content: dot, yAnchor: .5, xAnchor: .5 }));
    registerOverlay(new kakao.maps.CustomOverlay({ map, position, content: label, yAnchor: 2.2, xAnchor: .5 }));
  });
}

export function DashboardMap({ layer, data }) {
  const mapRef = React.useRef(null); const mapOverlaysRef = React.useRef([]); const [mapStatus, setMapStatus] = React.useState("지도를 불러오는 중이에요.");
  React.useEffect(() => {
    let cancelled = false; const sdkScript = document.getElementById("kakao-map-sdk");
    const clearMap = () => { mapOverlaysRef.current.forEach((overlay) => { overlay.clear?.(); overlay.setMap?.(null); }); mapOverlaysRef.current = []; mapRef.current?.replaceChildren(); };
    const drawMap = () => {
      if (!window.kakao?.maps || !mapRef.current) { setMapStatus("지도를 불러오지 못했어요. 잠시 후 다시 시도해 주세요."); return; }
      window.kakao.maps.load(() => {
        if (cancelled || !mapRef.current) return; clearMap();
        const center = new window.kakao.maps.LatLng(37.8813, 127.7298); const map = new window.kakao.maps.Map(mapRef.current, { center, level: 7 }); const bounds = new window.kakao.maps.LatLngBounds();
        if (layer === "accessibility") {
          data.features.forEach((feature) => renderAccessibilityLayer(window.kakao, map, bounds, feature, (overlay) => mapOverlaysRef.current.push(overlay), setMapStatus));
        } else {
          renderInflowLayer(window.kakao, map, bounds, data.features, (overlay) => mapOverlaysRef.current.push(overlay));
        }
        if (data.features.length) map.setBounds(bounds, 42, 42, 42, 42); setMapStatus(layer === "accessibility" ? "동별 접근성 점수를 5단계 색으로 표시하고 있어요." : "상권별 방문 현황을 표시하고 있어요.");
      });
    };
    const onError = () => setMapStatus("지도를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.");
    if (window.kakao?.maps) drawMap(); else { sdkScript?.addEventListener("load", drawMap, { once: true }); sdkScript?.addEventListener("error", onError, { once: true }); }
    return () => { cancelled = true; clearMap(); sdkScript?.removeEventListener("load", drawMap); sdkScript?.removeEventListener("error", onError); };
  }, [data, layer]);
  return <><div className="dashboard-map" ref={mapRef} /><p className="dashboard-map-status" aria-live="polite">{mapStatus}</p></>;
}
