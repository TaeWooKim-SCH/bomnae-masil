import React from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import { NavIcon } from "../common/NavIcon";

function useActiveQuest() {
  const { pathname } = useLocation();
  const [quest, setQuest] = React.useState(null);
  React.useEffect(() => {
    let alive = true;
    const questId = localStorage.getItem("active_quest_id");
    if (!questId || !localStorage.getItem("session_id")) { setQuest(null); return undefined; }
    api.getQuest(questId)
      .then((data) => { if (alive) setQuest(data.status === "started" || data.status === "stamped" ? data : null); })
      .catch(() => { if (alive) setQuest(null); });
    return () => { alive = false; };
  }, [pathname]);
  return quest;
}

function QuestMiniBar() {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const quest = useActiveQuest();
  if (!quest) return null;
  const own = [`/quests/${quest.quest_id}`, `/verify/${quest.quest_id}`, `/records/${quest.quest_id}`];
  if (own.includes(pathname)) return null;
  const stamped = quest.status === "stamped";
  const target = stamped ? `/records/${quest.quest_id}` : `/quests/${quest.quest_id}`;
  return <button className="quest-mini-bar" type="button" onClick={() => navigate(target)}><span className="mini-dot" aria-hidden="true" /><span className="mini-text"><strong>{stamped ? "기록만 남기면 완주예요 (+60점)" : "진행 중"} · {quest.title}</strong><small>{stamped ? "기록을 남기고 오늘의 경험을 완성해 보세요" : `${quest.route.route_no}번 · ${quest.activity.place_name}`}</small></span><span className="mini-arrow" aria-hidden="true">›</span></button>;
}

export function BottomNav({ active }) {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const current = active ?? (pathname === "/" ? "home" : pathname === "/records" ? "archive" : "quest");
  async function goQuestTab() {
    const activeId = localStorage.getItem("active_quest_id");
    if (activeId) {
      try {
        const quest = await api.getQuest(activeId);
        if (quest.status === "stamped") { navigate(`/records/${activeId}`); return; }
        if (quest.status === "started") { navigate(`/quests/${activeId}`); return; }
      } catch { /* 조회 실패면 추천 목록으로 */ }
    }
    navigate("/recommend");
  }
  return <><QuestMiniBar /><nav className="bottom-nav" aria-label="주요 메뉴"><button className={current === "home" ? "active" : ""} onClick={() => navigate("/")}><NavIcon name="home" />홈</button><button className={current === "quest" ? "active" : ""} onClick={goQuestTab}><NavIcon name="quest" />퀘스트</button><button className={current === "archive" ? "active" : ""} onClick={() => navigate("/records")}><NavIcon name="archive" />보관함</button></nav></>;
}
