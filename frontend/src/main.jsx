import React, { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const APP_KEY = import.meta.env.VITE_KAKAO_MAP_KEY;
const CITY_HALL = { lat: 37.8813, lng: 127.7298 };

function App() {
  const mapRef = React.useRef(null);
  const [status, setStatus] = React.useState("카카오맵을 불러오는 중이에요.");

  React.useEffect(() => {
    if (!APP_KEY) {
      setStatus("지도 키 설정을 확인해 주세요.");
      return undefined;
    }

    const script = document.createElement("script");
    script.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${APP_KEY}&autoload=false`;
    script.async = true;
    script.onload = () => {
      window.kakao.maps.load(() => {
        const position = new window.kakao.maps.LatLng(CITY_HALL.lat, CITY_HALL.lng);
        const map = new window.kakao.maps.Map(mapRef.current, {
          center: position,
          level: 4,
        });
        new window.kakao.maps.Marker({ position, map });
        setStatus("춘천시청 지도가 정상적으로 표시되고 있어요.");
      });
    };
    script.onerror = () => setStatus("지도를 불러오지 못했어요. 키와 Web 플랫폼 도메인을 확인해 주세요.");
    document.head.appendChild(script);

    return () => script.remove();
  }, []);

  return (
    <main>
      <p className="eyebrow">봄내마실 · R1-01</p>
      <h1>카카오맵 연결 확인</h1>
      <p className="status">{status}</p>
      <div ref={mapRef} className="map" aria-label="춘천시청 지도" />
    </main>
  );
}

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
