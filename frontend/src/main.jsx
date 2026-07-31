import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes, useLocation, useNavigate } from "react-router-dom";
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
      {showGate && <AgeGate onConfirm={createSession} submitting={sessionLoading} error={sessionError} />}
    </main>
  );
}

function PendingScreen({ title, description }) {
  const navigate = useNavigate();
  return <main className="app-shell pending-screen"><AppHeader balance={0} titles={[]} health={null} /><section><p className="eyebrow">봄내마실</p><h1>{title}</h1><p>{description}</p><button className="primary-button" type="button" onClick={() => navigate("/")}>홈으로 돌아가기</button></section></main>;
}

function RecommendHandoff() {
  const navigate = useNavigate();
  const { state } = useLocation();
  if (!state?.result) return <PendingScreen title="추천을 준비하고 있어요" description="추천 조건을 선택한 뒤 다시 시도해 주세요." />;
  return <main className="app-shell pending-screen"><AppHeader balance={0} titles={[]} health={null} /><section><p className="eyebrow">추천 조건이 전달됐어요</p><h1>오늘의 춘천을<br />조합하고 있어요</h1><p>{state.result.quests?.length ?? 0}개의 코스를 준비했어요. 카드 화면은 다음 작업에서 이어집니다.</p><button className="primary-button" type="button" onClick={() => navigate("/", { state: { lastRequest: state.request, lastResult: state.result } })}>조건 다시 고르기</button></section></main>;
}

function RouterApp() {
  return <Routes>
    <Route path="/" element={<Home />} />
    <Route path="/recommend" element={<RecommendHandoff />} />
    <Route path="/quests/:questId" element={<PendingScreen title="진행 중인 퀘스트" description="상세 화면에서 이어서 확인할 수 있어요." />} />
    <Route path="/records/:questId" element={<PendingScreen title="기록을 남겨볼까요?" description="기록 화면에서 오늘의 경험을 완성해 보세요." />} />
    <Route path="*" element={<Home />} />
  </Routes>;
}

createRoot(document.getElementById("root")).render(<BrowserRouter><RouterApp /></BrowserRouter>);
