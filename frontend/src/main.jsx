import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes, useLocation, useNavigate, useParams } from "react-router-dom";
import { Html5Qrcode } from "html5-qrcode";
import { api } from "./api/client";
import "./styles.css";

const INTERESTS = [
  "운동·건강",
  "문화·공연",
  "공예·만들기",
  "사진·미디어",
  "요리·먹거리",
  "학습·어학",
  "자연·나들이",
];

const BUDGETS = [
  { label: "무료만", value: 0 },
  { label: "1만", value: 10000 },
  { label: "3만", value: 30000 },
  { label: "5만", value: 50000 },
  { label: "상관없음", value: null },
];

// 화면의 날짜 선택은 없으며, 데모 기준일을 요청에 함께 보냅니다.
const DEMO_DATE = "2026-08-01";
const INITIAL_TIME = { start: "14:00", end: "16:00" };
const ROUND_TRIP_BUS_FARE = 3000;

function isSessionMissing(error) {
  return error?.error?.code === "SESSION_NOT_FOUND" || !localStorage.getItem("session_id");
}

function AppHeader({ balance, titles, health }) {
  return (
    <header className="app-header">
      <a className="brand" href="/" aria-label="봄내마실 홈">봄내마실 · 춘천</a>
      <div className="header-status">
        {titles?.[0] && <span className="title-badge">{titles[0]}</span>}
        <strong className="balance">{balance.toLocaleString()}P</strong>
        <span className={health?.ok && health?.db ? "health health-ok" : "health"}>
          {health ? (health.ok && health.db ? "서비스 연결됨" : "서비스 확인 중") : "연결 확인 중"}
        </span>
      </div>
    </header>
  );
}

function NavIcon({ name }) {
  const paths = {
    home: <><path d="m3 10 9-7 9 7v9a2 2 0 0 1-2 2h-4v-6H9v6H5a2 2 0 0 1-2-2z" /></>,
    quest: <><path d="M12 21s7-5.1 7-11A7 7 0 1 0 5 10c0 5.9 7 11 7 11Z" /><circle cx="12" cy="10" r="2.4" /></>,
    archive: <path d="M5 3h14a1 1 0 0 1 1 1v17l-8-4-8 4V4a1 1 0 0 1 1-1Z" />,
  };
  return <svg viewBox="0 0 24 24" aria-hidden="true">{paths[name]}</svg>;
}

function QrMark() {
  return <svg className="qr-mark" viewBox="0 0 96 96" aria-hidden="true">
    <g fill="none" stroke="currentColor" strokeWidth="8"><rect x="6" y="6" width="28" height="28" rx="2" /><rect x="62" y="6" width="28" height="28" rx="2" /><rect x="6" y="62" width="28" height="28" rx="2" /></g>
    <g fill="currentColor"><rect x="15" y="15" width="10" height="10" /><rect x="71" y="15" width="10" height="10" /><rect x="15" y="71" width="10" height="10" /><rect x="43" y="43" width="10" height="10" /><rect x="57" y="43" width="9" height="9" /><rect x="43" y="57" width="9" height="9" /><rect x="57" y="59" width="16" height="9" /><rect x="76" y="45" width="10" height="23" /><rect x="43" y="75" width="10" height="10" /><rect x="60" y="76" width="25" height="9" /></g>
  </svg>;
}

function BottomNav({ active = "home" }) {
  const navigate = useNavigate();
  return <nav className="bottom-nav" aria-label="주요 메뉴"><button className={active === "home" ? "active" : ""} onClick={() => navigate("/")}><NavIcon name="home" />홈</button><button className={active === "quest" ? "active" : ""} onClick={() => navigate("/recommend")}><NavIcon name="quest" />퀘스트</button><button className={active === "archive" ? "active" : ""} onClick={() => navigate("/records")}><NavIcon name="archive" />보관함</button></nav>;
}

function AgeGate({ onConfirm, submitting, error }) {
  const [ageConfirmed, setAgeConfirmed] = React.useState(false);
  const [nickname, setNickname] = React.useState("");

  function submit(event) {
    event.preventDefault();
    if (ageConfirmed) onConfirm(nickname.trim());
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <section className="age-gate" role="dialog" aria-modal="true" aria-labelledby="age-gate-title">
        <h1 id="age-gate-title">봄내마실에 오신 걸 환영해요</h1>

        <form onSubmit={submit}>
          <label className="check-row" htmlFor="age-confirmed">
            <input
              id="age-confirmed"
              type="checkbox"
              checked={ageConfirmed}
              onChange={(event) => setAgeConfirmed(event.target.checked)}
            />
            <span>만 14세 이상입니다 <em>(필수)</em></span>
          </label>

          <input
            id="nickname"
            className="text-input"
            value={nickname}
            onChange={(event) => setNickname(event.target.value.slice(0, 12))}
            maxLength={12}
            placeholder="닉네임 (선택)"
          />
          <p className="privacy-notice">실명은 쓰지 마세요 · 위치 추적 없이, 최소한의 정보만 저장해요. 기록은 언제든 직접 삭제할 수 있어요.</p>
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="primary-button gate-button" type="submit" disabled={!ageConfirmed || submitting}>
            {submitting ? "시작 준비 중..." : "시작하기"}
          </button>
        </form>
      </section>
    </div>
  );
}

function ContinueBanner({ activeQuest, onNavigate }) {
  if (!activeQuest) return null;
  const stamped = activeQuest.status === "stamped";
  return (
    <button className="continue-banner" type="button" onClick={() => onNavigate(stamped ? `/records/${activeQuest.quest_id}` : `/quests/${activeQuest.quest_id}`)}>
      <span className="continue-icon" aria-hidden="true">↗</span>
      <span>
        <strong>{stamped ? "기록만 남기면 완주예요 (+60점)" : "진행 중인 퀘스트가 있어요"}</strong>
        <small>{stamped ? "기록을 남기고 오늘의 경험을 완성해 보세요" : "이어서 봄내마실을 즐겨 보세요"}</small>
      </span>
      <span aria-hidden="true">›</span>
    </button>
  );
}

function Home() {
  const navigate = useNavigate();
  const location = useLocation();
  const [isReturningSession, setIsReturningSession] = React.useState(() => Boolean(localStorage.getItem("session_id")));
  const [showGate, setShowGate] = React.useState(() => !localStorage.getItem("session_id"));
  const [sessionLoading, setSessionLoading] = React.useState(false);
  const [sessionError, setSessionError] = React.useState("");
  const [loadError, setLoadError] = React.useState("");
  const [zones, setZones] = React.useState([]);
  const [stops, setStops] = React.useState([]);
  const [stopsLoading, setStopsLoading] = React.useState(false);
  const [balance, setBalance] = React.useState(0);
  const [titles, setTitles] = React.useState([]);
  const [nickname, setNickname] = React.useState("");
  const [health, setHealth] = React.useState(null);
  const [activeQuest, setActiveQuest] = React.useState(null);
  const [interests, setInterests] = React.useState([]);
  const [zoneCode, setZoneCode] = React.useState("");
  const [stopId, setStopId] = React.useState("");
  const [stopQuery, setStopQuery] = React.useState("");
  const [time, setTime] = React.useState(INITIAL_TIME);
  const [budget, setBudget] = React.useState(0);
  const [budgetSelected, setBudgetSelected] = React.useState(true);
  const [customBudgetMode, setCustomBudgetMode] = React.useState(false);
  const [customBudget, setCustomBudget] = React.useState("");
  const [recommendError, setRecommendError] = React.useState("");
  const [recommending, setRecommending] = React.useState(false);

  React.useEffect(() => {
    api.getZones().then(setZones).catch(() => setLoadError("동네 목록을 불러오지 못했어요. 다시 시도해 주세요."));
    api.health().then(setHealth).catch(() => setHealth({ ok: false, db: false }));
  }, []);

  React.useEffect(() => {
    if (!isReturningSession || !localStorage.getItem("session_id")) return;
    api.getRecords()
      .then((data) => {
        setBalance(data.balance);
        setTitles(data.titles ?? []);
      })
      .catch((error) => {
        if (isSessionMissing(error)) {
          setIsReturningSession(false);
          setShowGate(true);
        }
      });
  }, [isReturningSession]);

  React.useEffect(() => {
    const questId = localStorage.getItem("active_quest_id");
    if (!questId || showGate) {
      setActiveQuest(null);
      return;
    }
    api.getQuest(questId)
      .then((quest) => setActiveQuest(quest.status === "started" || quest.status === "stamped" ? quest : null))
      .catch((error) => {
        if (isSessionMissing(error)) {
          setIsReturningSession(false);
          setShowGate(true);
        }
      });
  }, [showGate]);

  React.useEffect(() => {
    if (!zoneCode) {
      setStops([]);
      setStopId("");
      setStopQuery("");
      return;
    }
    setStopsLoading(true);
    setStopId("");
    setStopQuery("");
    api.getStops(zoneCode)
      .then((data) => setStops([...data].sort((a, b) => a.name.localeCompare(b.name, "ko"))))
      .catch(() => setLoadError("정류장 목록을 불러오지 못했어요. 다시 시도해 주세요."))
      .finally(() => setStopsLoading(false));
  }, [zoneCode]);

  function toggleInterest(interest) {
    setInterests((current) => {
      if (current.includes(interest)) return current.filter((item) => item !== interest);
      return current.length < 3 ? [...current, interest] : current;
    });
  }

  async function createSession(nickname) {
    setSessionLoading(true);
    setSessionError("");
    try {
      const data = await api.createSession({ nickname: nickname || undefined, age_confirmed: true });
      localStorage.setItem("session_id", data.session_id);
      setBalance(data.balance);
      setTitles([]);
      setNickname(nickname);
      setIsReturningSession(false);
      setShowGate(false);
    } catch (error) {
      setSessionError(error?.error?.message ?? "잠시 문제가 있었어요. 다시 시도해 주세요");
    } finally {
      setSessionLoading(false);
    }
  }

  const durationMinutes = Number(time.end.slice(0, 2)) * 60 + Number(time.end.slice(3)) - (Number(time.start.slice(0, 2)) * 60 + Number(time.start.slice(3)));
  const isFormComplete = interests.length > 0 && zoneCode && budgetSelected && !customBudgetMode && durationMinutes >= 60;
  const budgetIndex = Math.max(0, BUDGETS.findIndex((item) => item.value === budget));
  const quickStart = location.state?.lastRequest && location.state?.lastResult
    ? { request: location.state.lastRequest, result: location.state.lastResult }
    : null;
  const quickZoneName = zones.find((zone) => zone.zone_code === quickStart?.request.origin.zone_code)?.name;
  const quickBudget = BUDGETS.find((item) => item.value === quickStart?.request.max_budget_krw)?.label;
  const quickTime = quickStart?.request.time_window;

  async function submitRecommendation() {
    if (!isFormComplete || recommending) return;
    setRecommending(true);
    setRecommendError("");
    const request = {
      interests,
      origin: { zone_code: zoneCode, stop_id: stopId || null },
      time_window: { start: `${DEMO_DATE}T${time.start}`, end: `${DEMO_DATE}T${time.end}` },
      max_budget_krw: budget,
    };
    try {
      const result = await api.recommend(request);
      navigate("/recommend", { state: { request, result } });
    } catch (error) {
      if (isSessionMissing(error)) {
        setIsReturningSession(false);
        setShowGate(true);
      }
      else setRecommendError(error?.error?.message ?? "잠시 문제가 있었어요. 다시 시도해 주세요");
    } finally {
      setRecommending(false);
    }
  }

  const filteredStops = stops.filter((stop) => stop.name.includes(stopQuery.trim()));
  const selectedZone = zones.find((zone) => zone.zone_code === zoneCode);

  function useQuickStart() {
    if (!quickStart) return;
    navigate("/recommend", { state: { request: quickStart.request, result: quickStart.result } });
  }

  return (
    <main className="app-shell">
      <div className="home-content">
        <AppHeader balance={balance} titles={titles} health={health} />
        <h1>{nickname ? <>{nickname}님,<span className="nickname-greeting-gap">오늘 뭐 하지?</span></> : "오늘 뭐 하지?"}</h1>
        <p className="intro">네 가지만 알려주시면 오늘 갈 수 있는 퀘스트를 찾아드릴게요.</p>

        <ContinueBanner activeQuest={activeQuest} onNavigate={navigate} />
        {quickStart && (
          <section className="quick-start" aria-label="지난 추천 조건">
            <p>지난번 조건 그대로</p>
            <strong>{quickZoneName} 출발 · {quickTime.start.slice(11)}~{quickTime.end.slice(11)} · {quickBudget} · {quickStart.request.interests.join(" · ")}</strong>
            <button type="button" onClick={useQuickStart}>지금 바로 추천받기</button>
            <small>바꾸고 싶은 조건만 아래에서 고치세요</small>
          </section>
        )}

        <section className="recommend-form" aria-label="추천 조건 입력">
          <div className="form-section">
            <div className="section-title"><h2>관심사 <span>(최대 3개)</span></h2><small>{interests.length}/3</small></div>
            <div className="chip-list">
              {INTERESTS.map((interest) => (
                <button
                  className={interests.includes(interest) ? "chip selected" : "chip"}
                  type="button"
                  key={interest}
                  onClick={() => toggleInterest(interest)}
                  aria-pressed={interests.includes(interest)}
                >{interest}</button>
              ))}
            </div>
          </div>

          <div className="form-section">
            <div className="section-title"><h2>출발지</h2></div>
            <div className="origin-selects"><select id="zone" className="select-input" value={zoneCode} onChange={(event) => setZoneCode(event.target.value)}>
                <option value="">동네 선택</option>
                {zones.map((zone) => <option key={zone.zone_code} value={zone.zone_code}>{zone.name}</option>)}
              </select>
              <select className="select-input" value={stopId} onChange={(event) => setStopId(event.target.value)} disabled={!zoneCode || stopsLoading}>
                <option value="">잘 모르겠어요</option>
                {stops.map((stop) => <option key={stop.stop_id} value={stop.stop_id}>{stop.name}</option>)}
              </select>
            </div>
            {zoneCode && (
              <div className="stop-select">
                <input id="stop-search" className="text-input" value={stopQuery} onChange={(event) => setStopQuery(event.target.value)} placeholder="정류장 이름으로 찾아보기" aria-label="정류장 이름으로 찾아보기" />
                <div className="stop-options" aria-label={`${selectedZone?.name ?? ""} 정류장 목록`}>
                  <button type="button" className={!stopId ? "stop-option selected" : "stop-option"} onClick={() => setStopId("")}>잘 모르겠어요</button>
                  {stopsLoading ? <p className="loading-copy">정류장을 불러오는 중이에요.</p> : filteredStops.map((stop) => (
                    <button type="button" key={stop.stop_id} className={stopId === stop.stop_id ? "stop-option selected" : "stop-option"} onClick={() => setStopId(stop.stop_id)}>{stop.name}</button>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="form-section">
            <div className="section-title"><h2>시간 <span>(최소 60분)</span></h2></div>
            <div className="time-fields">
              <label><input type="time" value={time.start} onChange={(event) => setTime((current) => ({ ...current, start: event.target.value }))} /></label>
              <span aria-hidden="true">부터</span>
              <label><input type="time" value={time.end} onChange={(event) => setTime((current) => ({ ...current, end: event.target.value }))} /></label>
            </div>
            {time.start && time.end && durationMinutes < 60 && <p className="form-error">이용 시간을 60분 이상으로 선택해 주세요.</p>}
          </div>

          <div className="form-section">
            <div className="section-title"><h2>예산</h2><small>{budgetSelected ? BUDGETS.find((item) => item.value === budget)?.label : ""}</small></div>
            <div className={customBudgetMode ? "budget-slider disabled" : "budget-slider"}>
              <input
                aria-label="예산 구간"
                type="range"
                min="0"
                max="4"
                step="1"
                value={budgetIndex}
                disabled={customBudgetMode}
                onChange={(event) => {
                  const selected = BUDGETS[Number(event.target.value)];
                  setBudget(selected.value);
                  setBudgetSelected(true);
                }}
              />
              <div className="budget-ticks">
                {BUDGETS.map((item, index) => <span className={budgetSelected && budgetIndex === index ? "selected" : ""} key={item.label}>{item.label}</span>)}
              </div>
            </div>
            {customBudgetMode && <input className="custom-budget-input" inputMode="numeric" value={customBudget} onChange={(event) => setCustomBudget(event.target.value.replace(/\D/g, ""))} placeholder="금액 직접 입력 (원)" aria-label="금액 직접 입력" />}
            <button className="custom-budget-link" type="button" onClick={() => { setCustomBudgetMode((current) => !current); setCustomBudget(""); }}>
              {customBudgetMode ? "← 슬라이더로 고를게요" : "금액을 직접 입력할래요 →"}
            </button>
            {customBudgetMode && <p className="custom-budget-notice">추천 예산 구간은 현재 무료만·1만·3만·5만·상관없음 중에서만 선택할 수 있어요.</p>}
          </div>

          {loadError && <p className="form-error" role="alert">{loadError}</p>}
          {recommendError && <p className="form-error" role="alert">{recommendError}</p>}
          <button className="primary-button recommend-button" type="button" disabled={!isFormComplete || recommending} onClick={submitRecommendation}>
            {recommending ? "추천을 만들고 있어요..." : "퀘스트 추천받기"}
          </button>
          {!isFormComplete && <p className="validation-hint">{customBudgetMode ? "추천 예산 구간을 선택해 주세요." : "관심사, 출발 동네, 이용 시간, 예산을 모두 선택해 주세요."}</p>}
        </section>
      </div>
      <BottomNav active="home" />
      {showGate && <AgeGate onConfirm={createSession} submitting={sessionLoading} error={sessionError} />}
    </main>
  );
}

function PendingScreen({ title, description }) {
  const navigate = useNavigate();
  return <main className="app-shell pending-screen"><AppHeader balance={0} titles={[]} health={null} /><section><p className="eyebrow">봄내마실</p><h1>{title}</h1><p>{description}</p><button className="primary-button" type="button" onClick={() => navigate("/")}>홈으로 돌아가기</button></section><BottomNav /></main>;
}

const SCORE_ITEMS = [
  { key: "market", label: "상권 기여", color: "#0e87c4" },
  { key: "interest", label: "관심사", color: "#7166c7" },
  { key: "access", label: "접근성", color: "#1b8a70" },
  { key: "time", label: "시간", color: "#d5903c" },
  { key: "budget", label: "예산", color: "#cf6874" },
];

function formatKrw(value) {
  return `${value.toLocaleString()}원`;
}

function QuestCard({ quest, onOpen }) {
  const theme = quest.activity.type === "신청형" ? "course" : quest.activity.type === "상시형" ? "always" : "today";
  const scoreItems = SCORE_ITEMS.map((item) => ({ ...item, value: quest.score.breakdown[item.key] }));

  function openWithKeyboard(event) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onOpen();
    }
  }

  return (
    <article className="quest-recommend-card" role="button" tabIndex={0} onClick={onOpen} onKeyDown={openWithKeyboard} aria-label={`${quest.title} 상세 보기`}>
      <div className={`quest-card-hero ${theme}`}>
        <span>{quest.activity.type} · {quest.activity.place_name}</span>
        <div className="hero-badges">
          {quest.revisit && <span className="revisit-badge">다시 가기</span>}
          {quest.activity.d_day !== null && <span className="dday-badge">개강 D-{quest.activity.d_day}</span>}
        </div>
      </div>
      <div className="quest-card-body">
        <div className="quest-card-title-row">
          <h2>{quest.title}</h2>
          <span className="point-badge">최대 {quest.max_points}P</span>
        </div>
        <p className="quest-schedule">{quest.activity.name} · {quest.activity.schedule_text}</p>
        <p className={quest.mission ? "mission-copy" : "mission-copy no-mission"}>
          {quest.mission ? `가게 미션 — ${quest.mission.copy}` : "이번엔 활동만 즐겨요 — 기록으로 완주 (+60점)"}
        </p>
        <div className="quest-meta">
          <span>{quest.route.route_no}번 · {quest.route.stops_count}개 정거장 · 약 {quest.route.ride_min}분</span>
          {quest.route.no_transfer && <span className="no-transfer">환승 없음</span>}
          <span>약 {formatKrw(quest.budget_total_krw)} (버스 왕복 포함)</span>
        </div>
        {quest.route.basis_note && <p className="basis-note">{quest.route.basis_note}</p>}
        <div className="score-bar" aria-label={`추천 점수 ${quest.score.total}점`}>
          {scoreItems.map((item) => <span key={item.key} style={{ width: `${item.value}%`, background: item.color }} />)}
        </div>
        <div className="score-legend">
          {scoreItems.map((item) => <span key={item.key}><i style={{ background: item.color }} />{item.label} {item.value}</span>)}
        </div>
      </div>
    </article>
  );
}

function RecommendationSkeleton() {
  return (
    <>
      <p className="recommend-loading-copy">오늘의 춘천을 조합하고 있어요…</p>
      <div className="recommend-skeletons" aria-label="추천 결과를 불러오는 중">
        {[1, 2, 3].map((item) => <div className="recommend-skeleton" key={item}><i /><i /><i /></div>)}
      </div>
    </>
  );
}

function QuestMap({ quest, expanded, onToggleExpanded }) {
  const mapRef = React.useRef(null);
  const [mapStatus, setMapStatus] = React.useState("지도를 불러오는 중이에요.");

  React.useEffect(() => {
    const sdkScript = document.getElementById("kakao-map-sdk");
    const createMap = () => {
      if (!window.kakao?.maps || !mapRef.current) {
        setMapStatus("지도를 불러오지 못했어요.");
        return;
      }
      window.kakao.maps.load(() => {
        if (!mapRef.current) return;
        const { activity, mission, board_stop: boardStop, alight_stop: alightStop, path } = quest.coords;
        const map = new window.kakao.maps.Map(mapRef.current, { center: new window.kakao.maps.LatLng(activity.lat, activity.lng), level: 5 });
        const bounds = new window.kakao.maps.LatLngBounds();
        const locations = [
          { point: activity, label: "활동지", kind: "activity" },
          ...(mission ? [{ point: mission, label: "미션 가게", kind: "mission" }] : []),
          { point: boardStop, label: "승차 정류장", kind: "stop" },
          { point: alightStop, label: "하차 정류장", kind: "stop" },
        ];
        locations.forEach(({ point, label, kind }) => {
          const position = new window.kakao.maps.LatLng(point.lat, point.lng);
          bounds.extend(position);
          new window.kakao.maps.Marker({ map, position, title: label });
          const markerLabel = document.createElement("span");
          markerLabel.className = `map-marker-label ${kind}`;
          markerLabel.textContent = label;
          new window.kakao.maps.CustomOverlay({ map, position, content: markerLabel, yAnchor: 2.1 });
        });
        const pathPoints = path.map(([lat, lng]) => new window.kakao.maps.LatLng(lat, lng));
        pathPoints.forEach((point) => bounds.extend(point));
        new window.kakao.maps.Polyline({ map, path: pathPoints, strokeWeight: 5, strokeColor: "#0E87C4", strokeOpacity: .9, strokeStyle: "solid" });
        map.setBounds(bounds, 34, 34, 34, 34);
        setMapStatus("활동지, 미션 가게, 승하차 정류장을 표시하고 있어요.");
      });
    };
    const mapError = () => setMapStatus("지도를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.");
    if (window.kakao?.maps) createMap();
    else {
      sdkScript?.addEventListener("load", createMap, { once: true });
      sdkScript?.addEventListener("error", mapError, { once: true });
    }
    return () => {
      sdkScript?.removeEventListener("load", createMap);
      sdkScript?.removeEventListener("error", mapError);
    };
  }, [quest, expanded]);

  return <section className={expanded ? "detail-map-wrap expanded" : "detail-map-wrap"} aria-label="퀘스트 지도"><div ref={mapRef} className="detail-map" /><button className="map-expand-button" type="button" onClick={onToggleExpanded} aria-label={expanded ? "지도 전체 화면 닫기" : "지도를 전체 화면으로 보기"}>{expanded ? "×" : "⛶"}</button><div className="map-legend" aria-hidden="true"><span className="activity">● 활동지</span>{quest.mission && <span className="mission">● 미션 가게</span>}<span className="stop">■ 승하차 정류장</span></div><p className="map-status">{mapStatus}</p></section>;
}

function QuestDetail() {
  const { questId } = useParams();
  const navigate = useNavigate();
  const [quest, setQuest] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState("");
  const [starting, setStarting] = React.useState(false);
  const [startConflict, setStartConflict] = React.useState(false);
  const [mapExpanded, setMapExpanded] = React.useState(false);

  React.useEffect(() => {
    let mounted = true;
    setLoading(true);
    api.getQuest(questId).then((data) => { if (mounted) setQuest(data); }).catch(() => { if (mounted) setError("잠시 문제가 있었어요. 다시 시도해 주세요"); }).finally(() => { if (mounted) setLoading(false); });
    return () => { mounted = false; };
  }, [questId]);

  async function startQuest(abandonCurrent = false) {
    if (!quest || starting) return;
    const currentQuestId = localStorage.getItem("active_quest_id");
    if (!abandonCurrent && currentQuestId && currentQuestId !== quest.quest_id) {
      setStartConflict(true);
      return;
    }
    setStarting(true);
    try {
      const result = await api.startQuest(quest.quest_id, { abandon_current: abandonCurrent });
      localStorage.setItem("active_quest_id", quest.quest_id);
      setQuest((current) => ({ ...current, status: result.status, started_at: result.started_at }));
      navigate(`/verify/${quest.quest_id}`);
    } catch (requestError) {
      if (requestError?.error?.code === "QUEST_IN_PROGRESS") setStartConflict(true);
      else setError(requestError?.error?.message ?? "잠시 문제가 있었어요. 다시 시도해 주세요");
    } finally { setStarting(false); }
  }

  if (loading) return <main className="app-shell detail-loading"><p>퀘스트 정보를 불러오는 중이에요.</p></main>;
  if (!quest) return <PendingScreen title="퀘스트를 찾지 못했어요" description={error || "잠시 후 다시 시도해 주세요."} />;

  const started = quest.status === "started" || quest.status === "stamped";
  const hasMission = Boolean(quest.mission);
  return <main className="app-shell detail-page">
    <QuestMap quest={quest} expanded={mapExpanded} onToggleExpanded={() => setMapExpanded((current) => !current)} />
    <button className="detail-back" type="button" onClick={() => navigate(-1)} aria-label="추천 목록으로 돌아가기">‹</button>
    <section className="detail-content">
      <div className="detail-title-row"><div><p className="detail-type">{quest.activity.type}</p><h1>{quest.title}</h1></div><span className="point-badge">최대 {quest.max_points}P</span></div>
      <p className="detail-schedule">{quest.activity.place_name} · {quest.activity.schedule_text} · {quest.activity.price_krw === 0 ? "무료" : `입장 ${formatKrw(quest.activity.price_krw)}`}</p>
      {quest.activity.d_day !== null && <><span className="detail-dday">개강 D-{quest.activity.d_day}</span><p className="today-todo"><b>오늘 할 일</b> — 신청하기 → 장소 미리 가보기 → 근처 가게 미션</p></>}
      <section className="detail-timeline" aria-label="퀘스트 순서">
        <div className="timeline-item bus"><i /><div><div><h2>{quest.route.route_no}번 버스 · {quest.route.stops_count}개 정거장</h2><strong>약 {quest.route.ride_min}분</strong></div><p>{quest.activity.place_name} 인근 하차 · 환승 없음</p></div></div>
        <div className="timeline-item activity"><i /><div><div><h2>{quest.title}</h2><strong>{quest.activity.schedule_text.replace("오늘 ", "")}</strong></div><p>{quest.activity.place_name} · {quest.activity.price_krw === 0 ? "무료" : `입장 ${formatKrw(quest.activity.price_krw)}`}</p></div></div>
        {hasMission && <div className="timeline-item mission"><i /><div><div><h2>가게 미션 — {quest.mission.merchant_name}</h2><strong>활동 후</strong></div><p>QR/코드/영수증 인증</p></div></div>}
      </section>
      <section className="detail-bus-block"><strong>{quest.route.route_no}번</strong><div><b>{quest.route.route_no}번 · {quest.route.stops_count}개 정거장 · 약 {quest.route.ride_min}분</b><p>{quest.route.board_stop_name} → {quest.activity.place_name} · 환승 없음</p>{quest.route.basis_note && <small>{quest.route.basis_note}</small>}</div></section>
      <section className="detail-card"><h2>가게 미션</h2>{hasMission ? <><h3>{quest.mission.merchant_name}</h3><p>{quest.mission.copy}</p><small>인증 방법 — QR 스캔 · 4자리 코드 · 영수증 중 하나면 돼요.</small></> : <p className="no-mission-detail">이번엔 활동만 즐겨요 — 기록으로 바로</p>}</section>
      <section className="detail-card budget-detail"><h2>예산 합계</h2><div className="budget-row"><span>{quest.activity.name}</span><b>{quest.activity.price_krw === 0 ? "무료" : formatKrw(quest.activity.price_krw)}</b></div><div className="budget-row"><span>버스 (왕복)</span><b>{formatKrw(ROUND_TRIP_BUS_FARE)}</b></div>{hasMission && <div className="budget-row"><span>가게 미션</span><b>{formatKrw(quest.mission.expected_spend_krw)}</b></div>}<div className="budget-total"><span>합계</span><strong>약 {formatKrw(quest.budget_total_krw)} <small>(버스 왕복 포함)</small></strong></div></section>
      {error && <p className="form-error" role="alert">{error}</p>}
      {!started ? <button className="primary-button detail-start" type="button" onClick={() => startQuest()} disabled={starting}>{starting ? "시작하는 중..." : "퀘스트 시작"}</button> : <div className="started-actions">{hasMission && <button type="button" onClick={() => navigate(`/verify/${quest.quest_id}`)}>인증하러 가기</button>}<button type="button" onClick={() => navigate(`/records/${quest.quest_id}`)}>기록 쓰기</button></div>}
    </section>
    {startConflict && <div className="modal-backdrop detail-conflict"><section className="start-conflict" role="dialog" aria-modal="true" aria-labelledby="start-conflict-title"><h2 id="start-conflict-title">진행 중인 퀘스트가 있어요</h2><p>새로 시작하면 기존 퀘스트는 중단돼요.</p><div><button type="button" onClick={() => setStartConflict(false)}>돌아가기</button><button type="button" onClick={() => { setStartConflict(false); startQuest(true); }}>새 퀘스트 시작</button></div></section></div>}
    <BottomNav active="quest" />
  </main>;
}

function VerificationResultModal({ result, onRecord, onLater }) {
  const isAlready = Boolean(result.already);
  return <div className="verify-completion-backdrop" role="dialog" aria-modal="true" aria-labelledby="verify-completion-title">
    <section className="verify-completion-card">
      <div className="mission-stamp" aria-hidden="true"><small>봄내마실</small><strong>미션 완료</strong><em>{DEMO_DATE.replaceAll("-", ".")}</em></div>
      <h1 id="verify-completion-title">{isAlready ? "이미 적립된 퀘스트예요" : <>스탬프 획득! <b>+{result.points_added}P</b></>}</h1>
      <p>{isAlready ? "이미 방문 인증이 기록되어 있어요." : "카페 소양담 (육림고개) 방문이 기록됐어요."}<br />기록까지 남기면 완주 보너스 +20P!</p>
      <button className="primary-button" type="button" onClick={onRecord}>기록 남기기</button>
      <button className="completion-later" type="button" onClick={onLater}>나중에 할게요</button>
    </section>
  </div>;
}

function VerifyScreen() {
  const { questId } = useParams();
  const navigate = useNavigate();
  const [method, setMethod] = React.useState("qr");
  const [code, setCode] = React.useState("");
  const [amount, setAmount] = React.useState("");
  const [receiptName, setReceiptName] = React.useState("");
  const [result, setResult] = React.useState(null);
  const [error, setError] = React.useState("");
  const [scanning, setScanning] = React.useState(false);

  React.useEffect(() => {
    if (!scanning) return undefined;
    const scanner = new Html5Qrcode("verify-qr-reader");
    scanner.start(
      { facingMode: "environment" },
      { fps: 10, qrbox: { width: 210, height: 210 } },
      (text) => {
        let scannedCode = "";
        let merchantId = "";
        try { const payload = new URL(text); scannedCode = payload.searchParams.get("c") ?? ""; merchantId = payload.searchParams.get("m") ?? ""; } catch { scannedCode = text.slice(-4); }
        setCode(scannedCode);
        setScanning(false);
        verifyCode(scannedCode, "qr", merchantId);
      },
      () => {},
    ).catch(() => {
      setScanning(false);
      setError("카메라를 열 수 없어요. 4자리 코드로 인증해 주세요.");
    });
    return () => { scanner.stop().catch(() => {}); };
  }, [scanning]);

  React.useEffect(() => {
    if (!result) return undefined;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = previousOverflow; };
  }, [result]);

  async function verifyCode(value, verificationMethod = "code", merchantId = null) {
    if (value.length !== 4) { setError("QR 코드를 다시 비춰 주세요."); return; }
    const scenario = value === "0000" ? "already" : value !== "2097" ? "fail" : "success";
    try {
      const body = verificationMethod === "qr" ? { method: "qr", merchant_id: merchantId, code: value } : { method: "code", code: value };
      const response = await api.verifyQuest(questId, body, scenario);
      setResult(response);
    } catch (requestError) { setError(requestError?.error?.message ?? "잠시 문제가 있었어요. 다시 시도해 주세요"); }
  }

  async function verify() {
    setError("");
    if (method === "qr") { setError("QR 스캔을 먼저 완료해 주세요."); return; }
    if (method === "receipt" && (!receiptName || !amount || Number(amount) < 1000 || Number(amount) > 200000)) { setError("금액을 확인해 주세요 (1,000~200,000원)"); return; }
    if (method === "code" && code.length !== 4) { setError("4자리 코드를 입력해 주세요."); return; }
    if (method === "code") { await verifyCode(code); return; }
    try { const response = await api.verifyQuest(questId, { method: "receipt", amount_krw: Number(amount) }, "success"); setResult(response); }
    catch (requestError) { setError(requestError?.error?.message ?? "잠시 문제가 있었어요. 다시 시도해 주세요"); }
  }

  const codeTap = (key) => setCode((v) => key === "del" ? v.slice(0,-1) : v.length < 4 ? v + key : v);
  const formattedAmount = amount ? Number(amount).toLocaleString("ko-KR") : "";
  return <main className={`app-shell verify-page${result ? " is-complete" : ""}`}><section className="verify-content"><header className="verify-head"><button onClick={() => navigate(-1)}>‹</button><h1>가게 미션 인증</h1><b>40P</b></header><div className="merchant-card"><small>미션 장소</small><strong>카페 소양담 (육림고개)</strong><p>전시 보고 나와서, 필름 감성 그대로 따뜻한 한 잔 어때요?</p></div><p className="verify-done">이미 적립된 퀘스트예요 — 기록만 남기면 완주!</p><div className="verify-tabs">{[["qr","QR 스캔"],["code","4자리 코드"],["receipt","영수증"]].map(([key,label]) => <button key={key} className={method===key?"selected":""} onClick={() => { setMethod(key); setError(""); }}>{label}</button>)}</div>{method === "qr" && <div className="verify-panel qr-panel"><div className={`qr-frame${scanning ? " scanning" : ""}`}>{scanning ? <div id="verify-qr-reader" /> : <><QrMark /><p>가게의 QR 스탠드를 비춰주세요</p></>}</div>{!scanning && <button className="scan-button" onClick={() => setScanning(true)}>QR 스캔 시작</button>}<p>카메라가 안 되면 4자리 코드 탭을 이용해 주세요</p></div>}{method === "code" && <div className="verify-panel code-panel"><p>QR 스탠드 아래 적힌 4자리 숫자를 입력해 주세요</p><div className="code-boxes">{[0,1,2,3].map(i=><i key={i}>{code[i]||""}</i>)}</div><div className="keypad">{["1","2","3","4","5","6","7","8","9","","0","del"].map(k=><button key={k} disabled={!k} onClick={()=>codeTap(k)}>{k==="del"?"⌫":k}</button>)}</div></div>}{method === "receipt" && <div className="verify-panel receipt-panel"><p>협약이 안 된 가게도 괜찮아요. 영수증 사진과 금액만 있으면 미션 완료!</p><label className="receipt-upload"><b>＋</b>영수증 사진 찍기 / 올리기<input type="file" accept="image/*" onChange={(e)=>setReceiptName(e.target.files?.[0]?.name??"")} /></label><small>사진은 저장되지 않아요 — 확인 후 바로 폐기돼요</small><input className="receipt-amount" inputMode="numeric" value={formattedAmount} onChange={(e)=>setAmount(e.target.value.replace(/\D/g,""))} placeholder="결제 금액 (1,000~200,000원)" /></div>}{error && <p className="form-error">{error}</p>}<button className="primary-button verify-submit" onClick={verify}>{method==="receipt"?"소비 인증하기":"인증하고 +40P 받기"}</button><button className="text-action record-without" onClick={() => navigate(`/records/${questId}`)}>인증 없이 기록만 남길래요</button></section><BottomNav active="quest" />{result && <VerificationResultModal result={result} onRecord={() => navigate(`/records/${questId}`)} onLater={() => setResult(null)} />}</main>;
}

const RECORD_QUESTIONS = [
  { question: "오늘 가장 기억에 남는 순간은 무엇인가요?", chips: ["새로운 풍경", "따뜻한 대화", "몰입했던 순간"] },
  { question: "새롭게 알게 된 점이 있나요?", chips: ["춘천의 새로운 장소", "활동의 즐거움", "가게의 이야기"] },
  { question: "다음에는 어떻게 해보고 싶나요?", chips: ["다른 코스도 가보기", "친구와 함께", "다시 천천히"] },
];

function RecordScreen() {
  const { questId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const [mode, setMode] = React.useState(questId ? "write" : "archive");
  const [purpose, setPurpose] = React.useState("hobby");
  const [answers, setAnswers] = React.useState(["", "", ""]);
  const [pickedChips, setPickedChips] = React.useState([null, null, null]);
  const [draft, setDraft] = React.useState(null);
  const [regenerations, setRegenerations] = React.useState(0);
  const [generating, setGenerating] = React.useState(false);
  const [slowNotice, setSlowNotice] = React.useState(false);
  const [saving, setSaving] = React.useState(false);
  const [saveResult, setSaveResult] = React.useState(null);
  const [quest, setQuest] = React.useState(null);
  const [records, setRecords] = React.useState([]);
  const [balance, setBalance] = React.useState(0);
  const [titles, setTitles] = React.useState([]);
  const [selectedRecord, setSelectedRecord] = React.useState(null);
  const [deleteOpen, setDeleteOpen] = React.useState(false);
  const [error, setError] = React.useState("");

  const resolvedAnswers = answers.map((answer, index) => answer.trim() || (pickedChips[index] ?? ""));
  const hasAnswer = resolvedAnswers.some(Boolean);

  const loadArchive = React.useCallback(async () => {
    try {
      const data = await api.getRecords();
      setRecords(data.records ?? []);
      setBalance(data.balance ?? 0);
      setTitles(data.titles ?? []);
    } catch (requestError) { setError(requestError?.error?.message ?? "잠시 문제가 있었어요. 다시 시도해 주세요"); }
  }, []);

  React.useEffect(() => { loadArchive(); }, [loadArchive]);
  React.useEffect(() => {
    if (!questId) return;
    api.getQuest(questId).then(setQuest).catch(() => setError("퀘스트 정보를 불러오지 못했어요."));
  }, [questId]);

  function chooseChip(questionIndex, chip) {
    setPickedChips((current) => current.map((value, index) => index === questionIndex ? (value === chip ? null : chip) : value));
  }

  async function generateDraft() {
    if (!questId || generating || (draft && regenerations >= 2)) return;
    setGenerating(true); setError(""); setSlowNotice(false);
    const template = { title: "오늘의 춘천 기록", body: "오늘은 춘천에서 나만의 시간을 보냈습니다. 활동을 따라 천천히 걸으며 평소에는 지나치던 풍경과 이야기를 새롭게 만났습니다. 작은 선택 하나가 하루를 조금 더 풍성하게 만들었고, 다음에는 오늘의 경험을 바탕으로 또 다른 코스를 찾아보고 싶습니다.", tags: ["춘천", "오늘", "기록"] };
    try {
      const timeout = new Promise((resolve) => window.setTimeout(() => resolve({ draft: template, from_template: true }), 8000));
      const response = await Promise.race([api.generateRecord({ quest_id: questId, action: "generate", purpose, answers: resolvedAnswers, attempt: regenerations }), timeout]);
      setDraft(response.draft);
      setSlowNotice(Boolean(response.from_template));
      if (draft) setRegenerations((count) => count + 1);
    } catch { setDraft(template); setSlowNotice(true); }
    finally { setGenerating(false); }
  }

  async function saveRecord() {
    if (!questId || !draft || saving) return;
    setSaving(true); setError("");
    try {
      const response = await api.saveRecord({ quest_id: questId, action: "save", purpose, answers: resolvedAnswers, final: draft });
      localStorage.removeItem("active_quest_id");
      setSaveResult(response);
      const completedRecord = { record_id: response.record_id, title: draft.title, tags: draft.tags, created_at: `${DEMO_DATE}T14:00:00`, verified: response.verified, body: draft.body };
      await loadArchive();
      setRecords((current) => [completedRecord, ...current.filter((record) => record.record_id !== completedRecord.record_id)]);
      setMode("archive");
    } catch (requestError) { setError(requestError?.error?.message ?? "잠시 문제가 있었어요. 다시 시도해 주세요"); }
    finally { setSaving(false); }
  }

  async function deleteAll() {
    const sessionId = localStorage.getItem("session_id");
    if (!sessionId) { navigate("/"); return; }
    try {
      await api.deleteSession(sessionId);
      localStorage.removeItem("session_id");
      localStorage.removeItem("active_quest_id");
      navigate("/");
    } catch { setError("잠시 문제가 있었어요. 다시 시도해 주세요"); setDeleteOpen(false); }
  }

  if (selectedRecord) return <main className="app-shell record-page"><section className="record-content readonly-record"><header className="record-head"><button onClick={() => setSelectedRecord(null)}>‹</button><h1>나의 기록</h1><strong>{balance.toLocaleString()}P</strong></header><p className="record-date">{selectedRecord.created_at.slice(0, 10).replaceAll("-", ".")}</p><h2>{selectedRecord.title}</h2><div className="record-tags">{selectedRecord.tags.map((tag) => <span key={tag}>#{tag}</span>)}</div>{!selectedRecord.verified && <span className="unverified-badge">인증 없음</span>}<article>{selectedRecord.body ?? "이 기록의 본문은 생성 당시 읽기 전용으로 보관됩니다."}</article></section><BottomNav active="archive" /></main>;

  if (mode === "archive") return <main className="app-shell record-page"><section className="record-content archive-content"><header className="record-head"><button onClick={() => navigate(-1)}>‹</button><h1>보관함</h1><strong>{balance.toLocaleString()}P</strong></header><p className="archive-lead">오늘의 경험을 차곡차곡 모아 보세요.</p>{titles.map((title) => <span className="archive-title" key={title}>✦ {title}</span>)}{saveResult && <p className="record-earned">{saveResult.points_added > 0 ? `기록 +${saveResult.points_added}P` : "기록을 저장했어요"}{saveResult.completion_bonus > 0 ? ` · 완주 보너스 +${saveResult.completion_bonus}P` : ""}</p>}<section className="archive-list">{records.length ? records.map((record) => <button className="archive-card" key={record.record_id} onClick={() => setSelectedRecord(record)}><small>{record.created_at.slice(0, 10).replaceAll("-", ".")}</small><b>{record.title}</b><span>{record.tags.map((tag) => `#${tag}`).join("  ")}</span>{!record.verified && <em>인증 없음</em>}</button>) : <p className="archive-empty">아직 저장한 기록이 없어요.<br />오늘의 경험을 첫 기록으로 남겨 보세요.</p>}</section>{error && <p className="form-error">{error}</p>}<button className="delete-records" type="button" onClick={() => setDeleteOpen(true)}>내 기록 전체 삭제</button></section><BottomNav active="archive" />{deleteOpen && <div className="modal-backdrop delete-modal"><section role="dialog" aria-modal="true"><h2>기록을 모두 삭제할까요?</h2><p>모든 기록·스탬프·포인트가 삭제돼요.<br />개인 식별이 불가능한 통계는 유지됩니다.</p><div><button onClick={() => setDeleteOpen(false)}>취소</button><button onClick={deleteAll}>전체 삭제</button></div></section></div>}</main>;

  return <main className="app-shell record-page"><section className="record-content"><header className="record-head"><button onClick={() => navigate(-1)}>‹</button><h1>오늘을 기록해 볼까요?</h1><strong>{balance.toLocaleString()}P</strong></header><p className="record-subtitle">짧게 답해 주시면 오늘의 경험을 기록으로 정리해 드려요.</p><section className="purpose-section"><h2>이 기록을 어디에 쓸까요?</h2><div>{[["portfolio", "포트폴리오"], ["hobby", "취미 아카이브"], ["learning", "배움일지"]].map(([value, label]) => <button className={purpose === value ? "selected" : ""} key={value} onClick={() => setPurpose(value)}>{label}</button>)}</div></section><p className="privacy-hint">실명·연락처는 적지 마세요.</p>{RECORD_QUESTIONS.map((item, index) => <section className="record-question" key={item.question}><h2>{index + 1}. {item.question}</h2><div className="answer-chips">{item.chips.map((chip) => <button className={pickedChips[index] === chip ? "selected" : ""} key={chip} onClick={() => chooseChip(index, chip)}>{chip}</button>)}</div><textarea value={answers[index]} maxLength={200} placeholder="직접 적어도 좋아요 (최대 200자)" onChange={(event) => setAnswers((current) => current.map((value, answerIndex) => answerIndex === index ? event.target.value : value))} /></section>)}{!hasAnswer && <p className="answer-warning">한 가지만 골라주시면 포인트가 적립돼요 (+60점)</p>}<button className="draft-button" disabled={generating || Boolean(draft && regenerations >= 2)} onClick={generateDraft}>{generating ? "AI가 기록을 정리하고 있어요…" : draft ? `다시 생성 (${2 - regenerations}회 남음)` : "AI 초안 만들기"}</button>{slowNotice && <p className="slow-notice">연결이 느려 기본 초안을 먼저 드려요.</p>}{draft && <section className="draft-editor"><h2>AI 초안</h2><input value={draft.title} maxLength={100} onChange={(event) => setDraft((current) => ({ ...current, title: event.target.value }))} /><textarea value={draft.body} maxLength={500} onChange={(event) => setDraft((current) => ({ ...current, body: event.target.value }))} /><div className="record-tags">{draft.tags.map((tag) => <span key={tag}>#{tag}</span>)}</div><button className="primary-button" onClick={saveRecord} disabled={saving}>{saving ? "저장하는 중…" : "기록 저장하기"}</button></section>}{error && <p className="form-error">{error}</p>}</section><BottomNav active="quest" /></main>;
}

function RecommendHandoff() {
  const navigate = useNavigate();
  const { state } = useLocation();
  const [loading, setLoading] = React.useState(Boolean(state?.result));
  const [moreShown, setMoreShown] = React.useState(false);

  React.useEffect(() => {
    if (!state?.result) return undefined;
    const timer = window.setTimeout(() => setLoading(false), 450);
    return () => window.clearTimeout(timer);
  }, [state?.result]);

  if (!state?.result) return <PendingScreen title="추천을 준비하고 있어요" description="홈에서 조건을 선택하면 오늘의 퀘스트를 추천해 드려요." />;

  const result = state.result;
  const quests = moreShown ? [...result.quests, ...result.more] : result.quests;
  const hasMore = result.more.length > 0 && !moreShown;

  return (
    <main className="app-shell">
      <div className="recommend-content">
        <AppHeader balance={0} titles={[]} health={null} />
        <button className="back-link" type="button" onClick={() => navigate("/", { state: { lastRequest: state.request, lastResult: state.result } })}>‹ 조건 다시 고르기</button>
        <h1>오늘의 추천 퀘스트</h1>
        <p className="recommend-summary">선택한 시간과 출발지에서 가볍게 즐길 수 있는 코스예요.</p>
        {loading ? <RecommendationSkeleton /> : (
          <>
            {result.relaxed && <p className="relaxed-notice">{result.relaxed.message}</p>}
            <p className="market-notice">골목의 <b>숨은 가게</b>를 먼저 소개해 드려요 — 순위에 상권 기여 30%가 반영돼요.</p>
            <section className="recommend-card-list" aria-label="추천 퀘스트 목록">
              {quests.map((quest) => <QuestCard key={quest.quest_id} quest={quest} onOpen={() => navigate(`/quests/${quest.quest_id}`)} />)}
            </section>
            {hasMore && <button className="more-button" type="button" onClick={() => setMoreShown(true)}>다른 추천 보기</button>}
            {result.more.length === 0 || moreShown ? <p className="more-exhausted">추천을 모두 보여드렸어요 — 조건을 바꿔 다시 받아보세요.</p> : null}
          </>
        )}
      </div>
      <BottomNav active="quest" />
    </main>
  );
}

const ACCESSIBILITY_COLORS = {
  1: "#dceff7",
  2: "#acd9e9",
  3: "#70b9d5",
  4: "#3388b0",
  5: "#0b587d",
};

const INFLOW_COLORS = {
  "확정저유입": "#c84e3a",
  "추정후보": "#d79545",
  "일반": "#5b9a87",
  "붐빔": "#6e7c86",
};

function DashboardMap({ layer, data }) {
  const mapRef = React.useRef(null);
  const [mapStatus, setMapStatus] = React.useState("지도를 불러오는 중이에요.");

  React.useEffect(() => {
    let cancelled = false;
    const sdkScript = document.getElementById("kakao-map-sdk");
    const drawMap = () => {
      if (!window.kakao?.maps || !mapRef.current) {
        setMapStatus("지도를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.");
        return;
      }
      window.kakao.maps.load(() => {
        if (cancelled || !mapRef.current) return;
        mapRef.current.replaceChildren();
        const center = new window.kakao.maps.LatLng(37.8813, 127.7298);
        const map = new window.kakao.maps.Map(mapRef.current, { center, level: 7 });
        const bounds = new window.kakao.maps.LatLngBounds();

        if (layer === "accessibility") {
          const hoverLabel = document.createElement("div");
          hoverLabel.className = "dashboard-zone-label";
          const hoverOverlay = new window.kakao.maps.CustomOverlay({ content: hoverLabel, yAnchor: 1.35 });
          data.features.forEach((feature) => {
            const points = feature.geometry.coordinates[0].map(([lng, lat]) => new window.kakao.maps.LatLng(lat, lng));
            points.forEach((point) => bounds.extend(point));
            const polygon = new window.kakao.maps.Polygon({
              map,
              path: points,
              strokeWeight: 1.5,
              strokeColor: "#fff",
              strokeOpacity: .9,
              fillColor: ACCESSIBILITY_COLORS[feature.properties.quintile] ?? ACCESSIBILITY_COLORS[1],
              fillOpacity: .58,
            });
            const showZone = (event) => {
              hoverLabel.textContent = `${feature.properties.name} · ${feature.properties.score}점`;
              hoverOverlay.setPosition(event.latLng);
              hoverOverlay.setMap(map);
            };
            const hideZone = () => hoverOverlay.setMap(null);
            window.kakao.maps.event.addListener(polygon, "mouseover", showZone);
            window.kakao.maps.event.addListener(polygon, "mouseout", hideZone);
            window.kakao.maps.event.addListener(polygon, "click", (event) => {
              showZone(event);
              setMapStatus(`${feature.properties.name} 접근성 점수는 ${feature.properties.score}점이에요.`);
            });
          });
        } else {
          data.features.forEach((feature) => {
            const [lng, lat] = feature.geometry.coordinates;
            const position = new window.kakao.maps.LatLng(lat, lng);
            bounds.extend(position);
            const dot = document.createElement("span");
            dot.className = "dashboard-store-dot";
            dot.style.background = INFLOW_COLORS[feature.properties.inflow_status] ?? INFLOW_COLORS.일반;
            new window.kakao.maps.CustomOverlay({ map, position, content: dot, yAnchor: .5, xAnchor: .5 });
            const label = document.createElement("div");
            label.className = "dashboard-store-label";
            label.textContent = `${feature.properties.name} · ${feature.properties.category}`;
            new window.kakao.maps.CustomOverlay({ map, position, content: label, yAnchor: 2.2, xAnchor: .5 });
          });
        }
        if (data.features.length) map.setBounds(bounds, 42, 42, 42, 42);
        setMapStatus(layer === "accessibility" ? "동별 접근성 점수를 5단계 색으로 표시하고 있어요." : "상권별 방문 현황을 표시하고 있어요.");
      });
    };
    const onError = () => setMapStatus("지도를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.");
    if (window.kakao?.maps) drawMap();
    else {
      sdkScript?.addEventListener("load", drawMap, { once: true });
      sdkScript?.addEventListener("error", onError, { once: true });
    }
    return () => {
      cancelled = true;
      sdkScript?.removeEventListener("load", drawMap);
      sdkScript?.removeEventListener("error", onError);
    };
  }, [data, layer]);

  return <><div className="dashboard-map" ref={mapRef} /><p className="dashboard-map-status" aria-live="polite">{mapStatus}</p></>;
}

function DashboardScreen() {
  const [layer, setLayer] = React.useState("accessibility");
  const [dashboard, setDashboard] = React.useState(null);
  const [error, setError] = React.useState("");

  React.useEffect(() => {
    let mounted = true;
    Promise.all([api.getDashboardAccessibility(), api.getDashboardInflow(), api.getDashboardKpi()])
      .then(([accessibility, inflow, kpi]) => { if (mounted) setDashboard({ accessibility, inflow, kpi }); })
      .catch(() => { if (mounted) setError("잠시 문제가 있었어요. 다시 시도해 주세요"); });
    return () => { mounted = false; };
  }, []);

  if (error) return <main className="dashboard-page"><section className="dashboard-error"><h1>정책 대시보드</h1><p>{error}</p><button type="button" onClick={() => window.location.reload()}>다시 시도</button></section></main>;
  if (!dashboard) return <main className="dashboard-page"><section className="dashboard-loading"><p>정책 데이터를 불러오는 중이에요.</p></section></main>;

  const mapData = layer === "accessibility" ? dashboard.accessibility : dashboard.inflow;
  const kpiCards = [
    ["방문 전환율", dashboard.kpi.conversion_pct === null ? "—" : `${dashboard.kpi.conversion_pct}%`, "가게 미션 시작 후 인증 비율"],
    ["저유입 추천 비중", dashboard.kpi.low_inflow_pct === null ? "—" : `${dashboard.kpi.low_inflow_pct}%`, "추천 카드 중 저유입 상권 비중"],
    ["탐색 시간(중앙값)", dashboard.kpi.median_search_min === null ? "—" : `${dashboard.kpi.median_search_min}분`, "세션 생성부터 첫 퀘스트 시작까지"],
    ["실행 가능성", dashboard.kpi.feasibility_pct === null ? "—" : `${dashboard.kpi.feasibility_pct}%`, "무환승 경로를 보유한 추천 비율"],
  ];

  return <main className="dashboard-page">
    <header className="dashboard-header"><a href="/">봄내마실</a><span>춘천시 정책 대시보드</span><small>시범 운영</small></header>
    <section className="dashboard-intro"><p>정책 인사이트</p><h1>시민의 이동 경험이<br />지역 상권으로 이어지는 흐름</h1><span>추천 엔진의 접근성·상권 데이터를 한눈에 확인하세요.</span></section>
    <section className="dashboard-grid">
      <article className="dashboard-map-card">
        <div className="dashboard-card-heading"><div><p>지역 현황 지도</p><h2>{layer === "accessibility" ? "동별 접근성 히트맵" : "상권 방문 현황"}</h2></div><span>{mapData.features.length}개 영역</span></div>
        <div className="dashboard-tabs" role="tablist" aria-label="지도 종류"><button type="button" role="tab" aria-selected={layer === "accessibility"} className={layer === "accessibility" ? "selected" : ""} onClick={() => setLayer("accessibility")}>접근성 지도</button><button type="button" role="tab" aria-selected={layer === "inflow"} className={layer === "inflow" ? "selected" : ""} onClick={() => setLayer("inflow")}>상권 현황</button></div>
        <div className="dashboard-map-wrap"><DashboardMap layer={layer} data={mapData} /></div>
        {layer === "accessibility" ? <div className="dashboard-legend"><span>높음</span>{[1, 2, 3, 4, 5].map((value) => <i key={value} style={{ background: ACCESSIBILITY_COLORS[value] }} />)}<span>낮음</span></div> : <div className="dashboard-legend inflow-legend">{Object.entries(INFLOW_COLORS).map(([label, color]) => <span key={label}><i style={{ background: color }} />{label}</span>)}</div>}
      </article>
      <section className="dashboard-kpi-panel"><div className="dashboard-card-heading"><div><p>운영 성과</p><h2>핵심 지표</h2></div></div><div className="dashboard-kpi-grid">{kpiCards.map(([label, value, detail]) => <article className="dashboard-kpi" key={label}><p>{label}</p><strong>{value}</strong><span>{detail}</span></article>)}</div><p className="dashboard-footnote">{dashboard.kpi.seed_included ? "시범 운영 시뮬레이션 데이터 포함" : "운영 데이터 기준"}</p></section>
    </section>
  </main>;
}

function RouterApp() {
  return <Routes>
    <Route path="/" element={<Home />} />
    <Route path="/recommend" element={<RecommendHandoff />} />
    <Route path="/quests/:questId" element={<QuestDetail />} />
    <Route path="/verify/:questId" element={<VerifyScreen />} />
    <Route path="/records/:questId" element={<RecordScreen />} />
    <Route path="/records" element={<RecordScreen />} />
    <Route path="/dashboard" element={<DashboardScreen />} />
    <Route path="*" element={<Home />} />
  </Routes>;
}

createRoot(document.getElementById("root")).render(<BrowserRouter><RouterApp /></BrowserRouter>);
