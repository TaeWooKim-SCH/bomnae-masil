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
    </main>
  );
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
