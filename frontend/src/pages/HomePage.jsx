import React from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { CollectionCard, CollectionModal } from "../collection-map";
import { AgeGate } from "../components/common/AgeGate";
import { AppHeader } from "../components/layout/AppHeader";
import { BottomNav } from "../components/layout/BottomNav";
import { BUDGETS, INITIAL_TIME, INTERESTS } from "../constants/home";
import { isSessionMissing } from "../hooks/useSessionRecovery";
import { serviceDateOf } from "../utils/date";
import { loadRecoSnapshot, saveRecoSnapshot, snapBudget } from "../utils/recommendation";

export function HomePage() {
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
  const storedSnapshot = React.useMemo(() => loadRecoSnapshot(), []);
  const initialRequest = React.useMemo(() => location.state?.lastRequest ?? storedSnapshot?.request ?? null, []);
  const [interests, setInterests] = React.useState(initialRequest?.interests ?? []);
  const [zoneCode, setZoneCode] = React.useState(initialRequest?.origin?.zone_code ?? "");
  const [stopId, setStopId] = React.useState(initialRequest?.origin?.stop_id ?? "");
  const pendingStopRef = React.useRef(initialRequest?.origin?.stop_id ?? "");
  const [stopQuery, setStopQuery] = React.useState("");
  const [stopSearchOpen, setStopSearchOpen] = React.useState(false);
  const [time, setTime] = React.useState(initialRequest ? { start: initialRequest.time_window.start.slice(11, 16), end: initialRequest.time_window.end.slice(11, 16) } : INITIAL_TIME);
  const [budget, setBudget] = React.useState(initialRequest ? initialRequest.max_budget_krw : 0);
  const [budgetSelected, setBudgetSelected] = React.useState(true);
  const [customBudgetMode, setCustomBudgetMode] = React.useState(false);
  const [customBudget, setCustomBudget] = React.useState("");
  const [recommendError, setRecommendError] = React.useState("");
  const [recommending, setRecommending] = React.useState(false);
  const [collectionOpen, setCollectionOpen] = React.useState(false);

  React.useEffect(() => { api.getZones().then(setZones).catch(() => setLoadError("동네 목록을 불러오지 못했어요. 다시 시도해 주세요.")); api.health().then(setHealth).catch(() => setHealth({ ok: false, db: false })); }, []);
  React.useEffect(() => {
    if (!isReturningSession || !localStorage.getItem("session_id")) return;
    api.getRecords().then((data) => { setBalance(data.balance); setTitles(data.titles ?? []); }).catch((error) => { if (isSessionMissing(error)) { setIsReturningSession(false); setShowGate(true); } });
  }, [isReturningSession]);
  React.useEffect(() => {
    if (!zoneCode) { setStops([]); setStopId(""); setStopQuery(""); setStopSearchOpen(false); return; }
    setStopsLoading(true); setStopSearchOpen(false);
    const keepStopId = pendingStopRef.current;
    pendingStopRef.current = "";
    setStopId(keepStopId || ""); setStopQuery("");
    api.getStops(zoneCode).then((data) => setStops([...data].sort((a, b) => a.name.localeCompare(b.name, "ko")))).catch(() => setLoadError("정류장 목록을 불러오지 못했어요. 다시 시도해 주세요.")).finally(() => setStopsLoading(false));
  }, [zoneCode]);

  function toggleInterest(interest) { setInterests((current) => current.includes(interest) ? current.filter((item) => item !== interest) : current.length < 3 ? [...current, interest] : current); }
  async function createSession(newNickname) {
    setSessionLoading(true); setSessionError("");
    try { const data = await api.createSession({ nickname: newNickname || undefined, age_confirmed: true }); localStorage.setItem("session_id", data.session_id); window.dispatchEvent(new Event("bomnae-session-changed")); setBalance(data.balance); setTitles([]); setNickname(newNickname); setIsReturningSession(false); setShowGate(false); }
    catch (error) { setSessionError(error?.error?.message ?? "잠시 문제가 있었어요. 다시 시도해 주세요"); }
    finally { setSessionLoading(false); }
  }

  const durationMinutes = Number(time.end.slice(0, 2)) * 60 + Number(time.end.slice(3)) - (Number(time.start.slice(0, 2)) * 60 + Number(time.start.slice(3)));
  const customBudgetValue = customBudget === "" ? null : Number(customBudget);
  const effectiveBudget = customBudgetMode ? snapBudget(customBudgetValue ?? 0) : budget;
  const budgetReady = customBudgetMode ? customBudgetValue !== null : budgetSelected;
  const isFormComplete = interests.length > 0 && zoneCode && budgetReady && durationMinutes >= 60;
  const budgetIndex = Math.max(0, BUDGETS.findIndex((item) => item.value === budget));
  const quickStart = location.state?.lastRequest && location.state?.lastResult ? { request: location.state.lastRequest, result: location.state.lastResult } : storedSnapshot?.request && storedSnapshot?.result ? { request: storedSnapshot.request, result: storedSnapshot.result } : null;
  const quickZoneName = zones.find((zone) => zone.zone_code === quickStart?.request.origin.zone_code)?.name;
  const quickBudget = BUDGETS.find((item) => item.value === quickStart?.request.max_budget_krw)?.label;
  const quickTime = quickStart?.request.time_window;
  async function submitRecommendation() {
    if (!isFormComplete || recommending) return;
    setRecommending(true); setRecommendError("");
    const serviceDate = serviceDateOf(health);
    const request = { interests, origin: { zone_code: zoneCode, stop_id: stopId || null }, time_window: { start: `${serviceDate}T${time.start}`, end: `${serviceDate}T${time.end}` }, max_budget_krw: effectiveBudget };
    try { const result = await api.recommend(request); saveRecoSnapshot(request, result); navigate("/recommend", { state: { request, result } }); }
    catch (error) { if (isSessionMissing(error)) { setIsReturningSession(false); setShowGate(true); } else setRecommendError(error?.error?.message ?? "잠시 문제가 있었어요. 다시 시도해 주세요"); }
    finally { setRecommending(false); }
  }
  const filteredStops = stops.filter((stop) => stop.name.includes(stopQuery.trim()));
  const selectedZone = zones.find((zone) => zone.zone_code === zoneCode);
  function useQuickStart() { if (quickStart) navigate("/recommend", { state: { request: quickStart.request, result: quickStart.result } }); }

  return <main className="app-shell"><div className="home-content"><AppHeader balance={balance} titles={titles} health={health} /><h1>{nickname ? <>{nickname}님,<span className="nickname-greeting-gap">오늘 뭐 하지?</span></> : "오늘 뭐 하지?"}</h1><p className="intro">네 가지만 알려주시면 오늘 갈 수 있는 퀘스트를 찾아드릴게요.</p><CollectionCard onOpen={() => setCollectionOpen(true)} />{collectionOpen && <CollectionModal onClose={() => setCollectionOpen(false)} />}{quickStart && <section className="quick-start" aria-label="지난 추천 조건"><p>지난번 조건 그대로</p><strong>{quickZoneName} 출발 · {quickTime.start.slice(11)}~{quickTime.end.slice(11)} · {quickBudget} · {quickStart.request.interests.join(" · ")}</strong><button type="button" onClick={useQuickStart}>지금 바로 추천받기</button><small>바꾸고 싶은 조건만 아래에서 고치세요</small></section>}<section className="recommend-form" aria-label="추천 조건 입력"><div className="form-section"><div className="section-title"><h2>관심사 <span>(최대 3개)</span></h2><small>{interests.length}/3</small></div><div className="chip-list">{INTERESTS.map((interest) => <button className={interests.includes(interest) ? "chip selected" : "chip"} type="button" key={interest} onClick={() => toggleInterest(interest)} aria-pressed={interests.includes(interest)}>{interest}</button>)}</div></div><div className="form-section"><div className="section-title"><h2>출발지</h2></div><div className="origin-selects"><select id="zone" className="select-input" value={zoneCode} onChange={(event) => setZoneCode(event.target.value)}><option value="">동네 선택</option>{zones.map((zone) => <option key={zone.zone_code} value={zone.zone_code}>{zone.name}</option>)}</select><select className="select-input" value={stopId} onChange={(event) => setStopId(event.target.value)} disabled={!zoneCode || stopsLoading}><option value="">잘 모르겠어요</option>{stops.map((stop) => <option key={stop.stop_id} value={stop.stop_id}>{stop.name}</option>)}</select></div>{zoneCode && !stopSearchOpen && <button className="custom-budget-link" type="button" onClick={() => setStopSearchOpen(true)}>정류장 이름으로 찾아볼래요 →</button>}{zoneCode && stopSearchOpen && <div className="stop-select"><input id="stop-search" className="text-input" value={stopQuery} onChange={(event) => setStopQuery(event.target.value)} placeholder="정류장 이름으로 찾아보기" aria-label="정류장 이름으로 찾아보기" autoFocus /><div className="stop-options" aria-label={`${selectedZone?.name ?? ""} 정류장 목록`}><button type="button" className={!stopId ? "stop-option selected" : "stop-option"} onClick={() => setStopId("")}>잘 모르겠어요</button>{stopsLoading ? <p className="loading-copy">정류장을 불러오는 중이에요.</p> : filteredStops.map((stop) => <button type="button" key={stop.stop_id} className={stopId === stop.stop_id ? "stop-option selected" : "stop-option"} onClick={() => setStopId(stop.stop_id)}>{stop.name}</button>)}</div><button className="custom-budget-link" type="button" onClick={() => setStopSearchOpen(false)}>← 목록 접기</button></div>}</div><div className="form-section"><div className="section-title"><h2>시간 <span>(최소 60분)</span></h2></div><div className="time-fields"><label><input type="time" value={time.start} onChange={(event) => setTime((current) => ({ ...current, start: event.target.value }))} /></label><span aria-hidden="true">부터</span><label><input type="time" value={time.end} onChange={(event) => setTime((current) => ({ ...current, end: event.target.value }))} /></label></div>{time.start && time.end && durationMinutes < 60 && <p className="form-error">이용 시간을 60분 이상으로 선택해 주세요.</p>}</div><div className="form-section"><div className="section-title"><h2>예산</h2><small>{customBudgetMode ? (customBudgetValue === null ? "" : `${customBudgetValue.toLocaleString()}원 · ${BUDGETS.find((item) => item.value === effectiveBudget)?.label} 구간`) : budgetSelected ? BUDGETS.find((item) => item.value === budget)?.label : ""}</small></div><div className={customBudgetMode ? "budget-slider disabled" : "budget-slider"}><input aria-label="예산 구간" type="range" min="0" max="4" step="1" value={budgetIndex} disabled={customBudgetMode} onChange={(event) => { const selected = BUDGETS[Number(event.target.value)]; setBudget(selected.value); setBudgetSelected(true); }} /><div className="budget-ticks">{BUDGETS.map((item, index) => <span className={budgetSelected && budgetIndex === index ? "selected" : ""} key={item.label}>{item.label}</span>)}</div></div>{customBudgetMode && <input className="custom-budget-input" inputMode="numeric" value={customBudget} onChange={(event) => setCustomBudget(event.target.value.replace(/\D/g, ""))} placeholder="금액 직접 입력 (원)" aria-label="금액 직접 입력" />}<button className="custom-budget-link" type="button" onClick={() => { setCustomBudgetMode((current) => !current); setCustomBudget(""); }}>{customBudgetMode ? "← 슬라이더로 고를게요" : "금액을 직접 입력할래요 →"}</button>{customBudgetMode && <p className="custom-budget-notice">{customBudgetValue === null ? "예산을 입력하면 가장 가까운 구간으로 찾아드려요 (무료만·1만·3만·5만·상관없음)." : `입력하신 ${customBudgetValue.toLocaleString()}원을 담을 수 있는 ‘${BUDGETS.find((item) => item.value === effectiveBudget)?.label}’ 구간으로 찾아드려요.`}</p>}</div>{location.state?.qrNotice && <p className="form-error" role="alert">가게 QR은 퀘스트를 시작한 뒤에 찍어주세요 — 아래에서 추천을 받아 시작할 수 있어요.</p>}{loadError && <p className="form-error" role="alert">{loadError}</p>}{recommendError && <p className="form-error" role="alert">{recommendError}</p>}<button className="primary-button recommend-button" type="button" disabled={!isFormComplete || recommending} onClick={submitRecommendation}>{recommending ? "추천을 만들고 있어요..." : "퀘스트 추천받기"}</button>{!isFormComplete && <p className="validation-hint">{customBudgetMode && customBudgetValue === null ? "예산 금액을 입력해 주세요." : "관심사, 출발 동네, 이용 시간, 예산을 모두 선택해 주세요."}</p>}</section></div><BottomNav active="home" />{showGate && <AgeGate onConfirm={createSession} submitting={sessionLoading} error={sessionError} />}</main>;
}
