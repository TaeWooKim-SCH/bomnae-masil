import React from "react";

export function AgeGate({ onConfirm, submitting, error }) {
  const [ageConfirmed, setAgeConfirmed] = React.useState(false);
  const [nickname, setNickname] = React.useState("");
  function submit(event) {
    event.preventDefault();
    if (ageConfirmed) onConfirm(nickname.trim());
  }
  return <div className="modal-backdrop" role="presentation"><section className="age-gate" role="dialog" aria-modal="true" aria-labelledby="age-gate-title"><h1 id="age-gate-title">봄내마실에 오신 걸 환영해요</h1><form onSubmit={submit}><label className="check-row" htmlFor="age-confirmed"><input id="age-confirmed" type="checkbox" checked={ageConfirmed} onChange={(event) => setAgeConfirmed(event.target.checked)} /><span>만 14세 이상입니다 <em>(필수)</em></span></label><input id="nickname" className="text-input" value={nickname} onChange={(event) => setNickname(event.target.value.slice(0, 12))} maxLength={12} placeholder="닉네임 (선택)" /><p className="privacy-notice">실명은 쓰지 마세요 · 위치 추적 없이, 최소한의 정보만 저장해요. 기록은 언제든 직접 삭제할 수 있어요.</p>{error && <p className="form-error" role="alert">{error}</p>}<button className="primary-button gate-button" type="submit" disabled={!ageConfirmed || submitting}>{submitting ? "시작 준비 중..." : "시작하기"}</button></form></section></div>;
}
