import React from "react";
import { createRoot } from "react-dom/client";
import { Html5QrcodeScanner } from "html5-qrcode";
import "./styles.css";

const APP_KEY = import.meta.env.VITE_KAKAO_MAP_KEY;
const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");
const QUESTS = [
  {
    title: "저녁의 필름카메라 입문",
    activity: "춘천시평생학습관 · 오늘 19:00",
    mission: "육림고개 봄빛카페에서 기록 미션",
    bus: "300번 · 7개 정류장 · 약 25분",
  },
  {
    title: "소양강 노을 산책",
    activity: "소양강 스카이워크 · 오늘 18:30",
    mission: "근처 로컬 카페에서 한 잔의 휴식",
    bus: "12번 · 4개 정류장 · 약 15분",
  },
  {
    title: "주말의 작은 공예 시간",
    activity: "춘천문화예술회관 · 토요일 14:00",
    mission: "명동 골목 가게에서 미션 인증",
    bus: "200번 · 6개 정류장 · 약 20분",
  },
];

const CITY_HALL = { lat: 37.8813, lng: 127.7298 };
const CULTURE_CENTER = { lat: 37.8746, lng: 127.7216 };

function App() {
  const mapRef = React.useRef(null);
  const [mapStatus, setMapStatus] = React.useState("카카오맵을 불러오는 중이에요.");
  const [isScanning, setIsScanning] = React.useState(false);
  const [scanResult, setScanResult] = React.useState("");
  const [showCodeInput, setShowCodeInput] = React.useState(false);
  const [manualCode, setManualCode] = React.useState("");
  const [health, setHealth] = React.useState(null);

  React.useEffect(() => {
    fetch(`${API_BASE}/api/health`)
      .then((response) => response.json())
      .then(setHealth)
      .catch(() => setHealth({ ok: false, db: false }));
  }, []);

  React.useEffect(() => {
    if (!APP_KEY) {
      setMapStatus("지도 키 설정을 확인해 주세요.");
      return undefined;
    }

    const sdkScript = document.getElementById("kakao-map-sdk");
    const drawMap = () => {
      if (!window.kakao?.maps || !mapRef.current) return;
      window.kakao.maps.load(() => {
        const cityHall = new window.kakao.maps.LatLng(CITY_HALL.lat, CITY_HALL.lng);
        const cultureCenter = new window.kakao.maps.LatLng(CULTURE_CENTER.lat, CULTURE_CENTER.lng);
        const map = new window.kakao.maps.Map(mapRef.current, {
          center: cityHall,
          level: 6,
        });
        new window.kakao.maps.Marker({ position: cityHall, map, title: "춘천시청" });
        new window.kakao.maps.Marker({ position: cultureCenter, map, title: "춘천문화예술회관" });
        new window.kakao.maps.Polyline({
          map,
          path: [cityHall, cultureCenter],
          strokeWeight: 5,
          strokeColor: "#00A3E0",
          strokeOpacity: 0.9,
          strokeStyle: "solid",
        });
        setMapStatus("마커 2개와 경로선 1개가 표시되고 있어요.");
      });
    };

    const showMapError = () => setMapStatus("지도를 불러오지 못했어요. 키와 Web 플랫폼 도메인을 확인해 주세요.");
    if (window.kakao?.maps) drawMap();
    else {
      sdkScript?.addEventListener("load", drawMap, { once: true });
      sdkScript?.addEventListener("error", showMapError, { once: true });
    }

    return () => {
      sdkScript?.removeEventListener("load", drawMap);
      sdkScript?.removeEventListener("error", showMapError);
    };
  }, []);

  React.useEffect(() => {
    if (!isScanning) return undefined;

    const scanner = new Html5QrcodeScanner(
      "qr-reader",
      { fps: 10, qrbox: { width: 220, height: 220 } },
      false,
    );
    scanner.render(
      (decodedText) => {
        setScanResult(decodedText);
        setIsScanning(false);
      },
      () => {},
    );

    return () => {
      scanner.clear().catch(() => {});
    };
  }, [isScanning]);

  return (
    <main className="spike-page">
      <header>
        <p className="eyebrow">봄내마실 · R1-02</p>
        <h1>기술 스파이크 3종</h1>
        <p>본 화면은 카드 목록, 카카오맵 경로, QR 카메라 인식을 검증하기 위한 최소 구현입니다.</p>
        <p className="health-status">
          서버 {health ? (health.ok ? "정상" : "연결 실패") : "확인 중"} / DB {health ? (health.db ? "정상" : "연결 실패") : "확인 중"}
        </p>
      </header>

      <section aria-labelledby="card-title">
        <div className="section-heading">
          <p>스파이크 ①</p>
          <h2 id="card-title">가짜 데이터 카드 3장</h2>
        </div>
        <div className="quest-list">
          {QUESTS.map((quest) => (
            <article className="quest-card" key={quest.title}>
              <h3>{quest.title}</h3>
              <p>{quest.activity}</p>
              <p>{quest.mission}</p>
              <strong>{quest.bus}</strong>
            </article>
          ))}
        </div>
      </section>

      <section aria-labelledby="map-title">
        <div className="section-heading">
          <p>스파이크 ②</p>
          <h2 id="map-title">지도 마커와 경로선</h2>
        </div>
        <p className="status">{mapStatus}</p>
        <div ref={mapRef} className="map" aria-label="춘천시청과 춘천문화예술회관을 잇는 지도" />
      </section>

      <section aria-labelledby="qr-title">
        <div className="section-heading">
          <p>스파이크 ③</p>
          <h2 id="qr-title">QR 카메라 스캔</h2>
        </div>
        <p className="status">카메라 권한을 허용한 뒤 QR 코드를 비추면 읽은 문자열이 표시됩니다.</p>
        {!isScanning && (
          <button type="button" onClick={() => setIsScanning(true)}>
            카메라로 QR 스캔 시작
          </button>
        )}
        <div id="qr-reader" className={isScanning ? "qr-reader active" : "qr-reader"} />
        {scanResult && <p className="scan-result">읽은 QR 문자열: {scanResult}</p>}
        <button className="text-button" type="button" onClick={() => setShowCodeInput((current) => !current)}>
          카메라를 사용할 수 없나요? 4자리 코드 입력하기
        </button>
        {showCodeInput && (
          <div className="code-fallback">
            <label htmlFor="manual-code">가게에 비치된 4자리 코드를 입력해 주세요.</label>
            <input
              id="manual-code"
              value={manualCode}
              onChange={(event) => setManualCode(event.target.value.replace(/\D/g, "").slice(0, 4))}
              inputMode="numeric"
              maxLength={4}
              placeholder="예: 4821"
            />
            <p>실제 코드 대조와 스탬프 적립은 R1-07 인증 화면에서 연결합니다.</p>
          </div>
        )}
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
