import React from "react";
import { api } from "../../api/client";
import { serviceDateOf } from "../../utils/date";

function useServiceDate() {
  const [health, setHealth] = React.useState(null);
  React.useEffect(() => { api.health().then(setHealth).catch(() => setHealth(null)); }, []);
  return serviceDateOf(health);
}

export function VerificationResultModal({ result, merchantName, onRecord, onLater }) {
  const serviceDate = useServiceDate();
  const isAlready = Boolean(result.already);
  return <div className="verify-completion-backdrop" role="dialog" aria-modal="true" aria-labelledby="verify-completion-title"><section className="verify-completion-card"><div className="mission-stamp" aria-hidden="true"><small>봄내마실</small><strong>미션 완료</strong><em>{serviceDate.replaceAll("-", ".")}</em></div><h1 id="verify-completion-title">{isAlready ? "이미 적립된 퀘스트예요" : <>스탬프 획득! <b>+{result.points_added}P</b></>}</h1><p>{isAlready ? "이미 방문 인증이 기록되어 있어요." : `${merchantName ?? "가게"} 방문이 기록됐어요.`}<br />기록까지 남기면 완주 보너스 +20P!</p><button className="primary-button" type="button" onClick={onRecord}>기록 남기기</button><button className="completion-later" type="button" onClick={onLater}>나중에 할게요</button></section></div>;
}
