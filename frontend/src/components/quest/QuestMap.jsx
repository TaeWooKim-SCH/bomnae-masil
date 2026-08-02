import React from "react";

export function QuestMap({ quest, expanded, onToggleExpanded }) {
  const mapRef = React.useRef(null);
  const mapInstanceRef = React.useRef(null);
  const mapOverlaysRef = React.useRef([]);
  const [mapStatus, setMapStatus] = React.useState("지도를 불러오는 중이에요.");
  React.useEffect(() => {
    let disposed = false;
    const sdkScript = document.getElementById("kakao-map-sdk");
    const clearMap = () => { mapOverlaysRef.current.forEach((overlay) => overlay.setMap?.(null)); mapOverlaysRef.current = []; mapInstanceRef.current = null; mapRef.current?.replaceChildren(); };
    const createMap = () => {
      if (!window.kakao?.maps || !mapRef.current) { setMapStatus("지도를 불러오지 못했어요."); return; }
      window.kakao.maps.load(() => {
        if (disposed || !mapRef.current) return;
        clearMap();
        const { activity, mission, board_stop: boardStop, alight_stop: alightStop, path } = quest.coords;
        const map = new window.kakao.maps.Map(mapRef.current, { center: new window.kakao.maps.LatLng(activity.lat, activity.lng), level: 5 });
        mapInstanceRef.current = map;
        const bounds = new window.kakao.maps.LatLngBounds();
        const locations = [{ point: activity, label: "활동지", kind: "activity" }, ...(mission ? [{ point: mission, label: "미션 가게", kind: "mission" }] : []), { point: boardStop, label: "승차 정류장", kind: "stop" }, { point: alightStop, label: "하차 정류장", kind: "stop" }];
        locations.forEach(({ point, label, kind }) => { const position = new window.kakao.maps.LatLng(point.lat, point.lng); bounds.extend(position); const marker = new window.kakao.maps.Marker({ map, position, title: label }); const markerLabel = document.createElement("span"); markerLabel.className = `map-marker-label ${kind}`; markerLabel.textContent = label; const markerOverlay = new window.kakao.maps.CustomOverlay({ map, position, content: markerLabel, yAnchor: 2.1 }); mapOverlaysRef.current.push(marker, markerOverlay); });
        const pathPoints = path.map(([lat, lng]) => new window.kakao.maps.LatLng(lat, lng));
        pathPoints.forEach((point) => bounds.extend(point));
        const polyline = new window.kakao.maps.Polyline({ map, path: pathPoints, strokeWeight: 5, strokeColor: "#0E87C4", strokeOpacity: .9, strokeStyle: "solid" });
        mapOverlaysRef.current.push(polyline);
        map.setBounds(bounds, 34, 34, 34, 34);
        setMapStatus("활동지, 미션 가게, 승하차 정류장을 표시하고 있어요.");
      });
    };
    const mapError = () => setMapStatus("지도를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.");
    if (window.kakao?.maps) createMap(); else { sdkScript?.addEventListener("load", createMap, { once: true }); sdkScript?.addEventListener("error", mapError, { once: true }); }
    return () => { disposed = true; clearMap(); sdkScript?.removeEventListener("load", createMap); sdkScript?.removeEventListener("error", mapError); };
  }, [quest]);
  React.useEffect(() => { const map = mapInstanceRef.current; if (!map) return undefined; const relayout = window.setTimeout(() => map.relayout(), 0); return () => window.clearTimeout(relayout); }, [expanded]);
  return <section className={expanded ? "detail-map-wrap expanded" : "detail-map-wrap"} aria-label="퀘스트 지도"><div ref={mapRef} className="detail-map" /><button className="map-expand-button" type="button" onClick={onToggleExpanded} aria-label={expanded ? "지도 전체 화면 닫기" : "지도를 전체 화면으로 보기"}>{expanded ? "×" : "⛶"}</button><div className="map-legend" aria-hidden="true"><span className="activity">● 활동지</span>{quest.mission && <span className="mission">● 미션 가게</span>}<span className="stop">■ 승하차 정류장</span></div><p className="map-status">{mapStatus}</p></section>;
}
