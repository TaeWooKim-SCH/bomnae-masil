import { formatKrw } from "../../utils/recommendation";

const SCORE_ITEMS = [
  { key: "market", label: "상권 기여", color: "#0e87c4" },
  { key: "interest", label: "관심사", color: "#7166c7" },
  { key: "access", label: "접근성", color: "#1b8a70" },
  { key: "time", label: "시간", color: "#d5903c" },
  { key: "budget", label: "예산", color: "#cf6874" },
];

export function QuestCard({ quest, onOpen }) {
  const theme = quest.activity.type === "신청형" ? "course" : quest.activity.type === "상시형" ? "always" : "today";
  const scoreItems = SCORE_ITEMS.map((item) => ({ ...item, value: quest.score.breakdown[item.key] }));
  function openWithKeyboard(event) { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onOpen(); } }
  return <article className="quest-recommend-card" role="button" tabIndex={0} onClick={onOpen} onKeyDown={openWithKeyboard} aria-label={`${quest.title} 상세 보기`}><div className={`quest-card-hero ${theme}`}><span>{quest.activity.type} · {quest.activity.place_name}</span><div className="hero-badges">{quest.revisit && <span className="revisit-badge">다시 가기</span>}{quest.activity.d_day !== null && <span className="dday-badge">개강 D-{quest.activity.d_day}</span>}</div></div><div className="quest-card-body"><div className="quest-card-title-row"><h2>{quest.title}</h2><span className="point-badge">최대 {quest.max_points}P</span></div><p className="quest-schedule">{quest.activity.name} · {quest.activity.schedule_text}</p><p className={quest.mission ? "mission-copy" : "mission-copy no-mission"}>{quest.mission ? `가게 미션 — ${quest.mission.copy}` : "이번엔 활동만 즐겨요 — 기록으로 완주 (+60점)"}</p><div className="quest-meta"><span>{quest.route.route_no}번 · {quest.route.stops_count}개 정거장 · 약 {quest.route.ride_min}분</span>{quest.route.no_transfer && <span className="no-transfer">환승 없음</span>}<span>약 {formatKrw(quest.budget_total_krw)} (버스 왕복 포함)</span></div>{quest.route.basis_note && <p className="basis-note">{quest.route.basis_note}</p>}<div className="score-bar" aria-label={`추천 점수 ${quest.score.total}점`}>{scoreItems.map((item) => <span key={item.key} style={{ width: `${item.value}%`, background: item.color }} />)}</div><div className="score-legend">{scoreItems.map((item) => <span key={item.key}><i style={{ background: item.color }} />{item.label} {item.value}</span>)}</div></div></article>;
}

export function RecommendationSkeleton() {
  return <><p className="recommend-loading-copy">오늘의 춘천을 조합하고 있어요…</p><div className="recommend-skeletons" aria-label="추천 결과를 불러오는 중">{[1, 2, 3].map((item) => <div className="recommend-skeleton" key={item}><i /><i /><i /></div>)}</div></>;
}
