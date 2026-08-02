import React from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { NavIcon } from "../components/common/NavIcon";
import { AppHeader } from "../components/layout/AppHeader";
import { BottomNav } from "../components/layout/BottomNav";
import { QuestCard, RecommendationSkeleton } from "../components/recommendation/QuestCard";
import { loadRecoSnapshot } from "../utils/recommendation";

export function PendingScreen({ title, description }) {
  const navigate = useNavigate();
  const [balance, setBalance] = React.useState(0);
  const [titles, setTitles] = React.useState([]);
  React.useEffect(() => { if (!localStorage.getItem("session_id")) return; api.getRecords().then((data) => { setBalance(data.balance ?? 0); setTitles(data.titles ?? []); }).catch(() => {}); }, []);
  return <main className="app-shell pending-screen"><AppHeader balance={balance} titles={titles} health={null} /><section><span className="pending-icon" aria-hidden="true"><NavIcon name="quest" /></span><h1>{title}</h1><p>{description}</p><button className="primary-button" type="button" onClick={() => navigate("/")}>홈으로 돌아가기</button></section><BottomNav /></main>;
}

export function RecommendPage() {
  const navigate = useNavigate();
  const { state } = useLocation();
  const [wallet, setWallet] = React.useState({ balance: 0, titles: [] });
  React.useEffect(() => { if (!localStorage.getItem("session_id")) return; api.getRecords().then((data) => setWallet({ balance: data.balance ?? 0, titles: data.titles ?? [] })).catch(() => {}); }, []);
  const snapshot = state?.result ? { request: state.request, result: state.result } : loadRecoSnapshot();
  const [loading, setLoading] = React.useState(Boolean(state?.result));
  const [moreShown, setMoreShown] = React.useState(false);
  React.useEffect(() => { if (!state?.result) return undefined; const timer = window.setTimeout(() => setLoading(false), 450); return () => window.clearTimeout(timer); }, [state?.result]);
  if (!snapshot?.result) return <PendingScreen title="아직 받은 추천이 없어요" description="홈에서 조건을 선택하면 오늘의 퀘스트를 추천해 드려요." />;
  const result = snapshot.result;
  const isEmpty = result.quests.length === 0;
  const quests = moreShown ? [...result.quests, ...result.more] : result.quests;
  const hasMore = result.more.length > 0 && !moreShown;
  return <main className="app-shell"><div className="recommend-content"><AppHeader balance={wallet.balance} titles={wallet.titles} health={null} /><button className="back-link" type="button" onClick={() => navigate("/", { state: { lastRequest: snapshot.request, lastResult: snapshot.result } })}>‹ 조건 다시 고르기</button><h1>오늘의 추천 퀘스트</h1><p className="recommend-summary">선택한 시간과 출발지에서 가볍게 즐길 수 있는 코스예요.</p>{loading ? <RecommendationSkeleton /> : isEmpty ? <section className="recommend-empty"><p className="recommend-empty-eyebrow">NO QUEST FOR NOW</p><h2>{result.relaxed?.message ?? "지금 조건에서는 활동을 찾지 못했어요"}</h2><p className="recommend-empty-copy">시간이나 관심사 중 한 가지만 조정하면, 오늘 갈 수 있는 새로운 코스를 찾아드릴게요.</p><div className="recommend-empty-visual" aria-hidden="true"><span>0</span><svg viewBox="0 0 120 46" fill="none"><path d="M9 35C27 35 27 11 47 11c15 0 14 23 29 23 13 0 15-14 31-14" stroke="currentColor" strokeWidth="1.7" strokeDasharray="3 4" /><circle cx="9" cy="35" r="4" fill="currentColor" /><path d="M108 14c0 5-7 12-7 12s-7-7-7-12a7 7 0 1 1 14 0Z" fill="#0E87C4" /><circle cx="101" cy="14" r="2.3" fill="#F7FAFB" /></svg></div><button className="primary-button" type="button" onClick={() => navigate("/", { state: { lastRequest: snapshot.request } })}>조건 바꾸기</button><p className="recommend-empty-footnote">입력한 조건은 그대로 남아 있어요.</p></section> : <>{result.relaxed && <p className="relaxed-notice">{result.relaxed.message}</p>}<p className="market-notice">골목의 <b>숨은 가게</b>를 먼저 소개해 드려요 — 순위에 상권 기여 30%가 반영돼요.</p><section className="recommend-card-list" aria-label="추천 퀘스트 목록">{quests.map((quest) => <QuestCard key={quest.quest_id} quest={quest} onOpen={() => navigate(`/quests/${quest.quest_id}`)} />)}</section>{hasMore && <button className="more-button" type="button" onClick={() => setMoreShown(true)}>다른 추천 보기</button>}{result.more.length === 0 || moreShown ? <p className="more-exhausted">추천을 모두 보여드렸어요 — 조건을 바꿔 다시 받아보세요.</p> : null}</>}</div><BottomNav active="quest" /></main>;
}
