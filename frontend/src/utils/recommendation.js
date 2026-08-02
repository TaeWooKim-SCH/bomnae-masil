import { BUDGETS } from "../constants/home";

const RECO_SNAPSHOT_KEY = "last_recommendation";

export function snapBudget(amount) {
  if (amount === 0) return 0;
  const bucket = BUDGETS.map((item) => item.value).find((value) => value !== null && value >= amount);
  return bucket === undefined ? null : bucket;
}

export function saveRecoSnapshot(request, result) {
  try { sessionStorage.setItem(RECO_SNAPSHOT_KEY, JSON.stringify({ request, result })); } catch { /* 저장 실패는 치명적이지 않다 */ }
}

export function loadRecoSnapshot() {
  try { return JSON.parse(sessionStorage.getItem(RECO_SNAPSHOT_KEY) ?? "null"); } catch { return null; }
}

export function formatKrw(value) {
  return `${value.toLocaleString()}원`;
}
