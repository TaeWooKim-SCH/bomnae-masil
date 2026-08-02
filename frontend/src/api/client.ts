import dashboardStats from "../mocks/dashboard_stats.json";
import dashboardAccessibility from "../mocks/dashboard_accessibility.json";
import dashboardInflow from "../mocks/dashboard_inflow.json";
import health from "../mocks/health.json";
import questDetail from "../mocks/quest_detail.json";
import questStart from "../mocks/quest_start.json";
import recommend from "../mocks/recommend.json";
import recommendRelaxed from "../mocks/recommend_relaxed.json";
import recordDraft from "../mocks/record_draft.json";
import recordSave from "../mocks/record_save.json";
import recordSaveNoPoints from "../mocks/record_save_no_points.json";
import recordSaveUnverified from "../mocks/record_save_unverified.json";
import recordsList from "../mocks/records_list.json";
import session from "../mocks/session.json";
import sessionNotFound from "../mocks/session_not_found.json";
import stops from "../mocks/stops.json";
import verifyAlready from "../mocks/verify_already.json";
import verifyFail from "../mocks/verify_fail.json";
import verifySuccess from "../mocks/verify_success.json";
import verifyWrongStore from "../mocks/verify_wrong_store.json";
import zones from "../mocks/zones.json";

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");
const USE_MOCK = import.meta.env.VITE_USE_MOCK !== "false";
const MOCK_STATE_KEY = "mock_quest_states";
let mockSessionSequence = 0;

function loadMockStates(): Map<string, { status: string; started_at: string | null }> {
  try {
    return new Map(Object.entries(JSON.parse(localStorage.getItem(MOCK_STATE_KEY) ?? "{}")));
  } catch {
    return new Map();
  }
}

// 목 모드 상태를 localStorage에 함께 적어 새로고침에도 진행(started/stamped)이 유지되게 한다
const mockQuestStates = loadMockStates();

function rememberMockState(questId: string, state: { status: string; started_at: string | null }) {
  mockQuestStates.set(questId, state);
  try { localStorage.setItem(MOCK_STATE_KEY, JSON.stringify(Object.fromEntries(mockQuestStates))); } catch { /* 저장 실패 무시 */ }
}

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value));
}

function clearExpiredSession(payload: unknown) {
  if (typeof payload !== "object" || payload === null || !("error" in payload)) return;
  const error = payload.error;
  if (typeof error === "object" && error !== null && "code" in error && error.code === "SESSION_NOT_FOUND") {
    localStorage.removeItem("session_id");
    localStorage.removeItem("active_quest_id");
  }
}

async function request<T>(path: string, init: RequestInit = {}, mockResponse?: T): Promise<T> {
  if (USE_MOCK) {
    if (mockResponse === undefined) throw new Error("대시보드 GeoJSON 목 파일을 기다리고 있어요.");
    const response = clone(mockResponse);
    clearExpiredSession(response);
    return response;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  });
  if (response.status === 204) return null as T;

  const payload = await response.json();
  if (!response.ok) {
    clearExpiredSession(payload);
    throw payload;
  }
  return payload as T;
}

function sessionHeaders() {
  const sessionId = localStorage.getItem("session_id");
  return sessionId ? { Authorization: `Bearer ${sessionId}` } : {};
}

// 목 모드에서도 첫 방문은 새 세션처럼 시작한다. 실제 서비스의 수집 현황은
// 서버가 session_id 기준으로 돌려주므로 이 분기는 목 모드에만 적용된다.
function emptyMockRecords() {
  return {
    records: [],
    balance: 0,
    titles: [],
    zone_map: { collected: [], available: [] },
  };
}

function mockRecordsForCurrentSession() {
  const sessionId = localStorage.getItem("session_id");
  // 새로 만든 목 세션은 새로고침 후에도 0조각 상태를 유지한다.
  if (!sessionId || sessionId.startsWith("ses_mock_")) return emptyMockRecords();
  // 기존 데모 세션은 발표용 시드(8조각)를 그대로 쓴다.
  return clone(recordsList);
}

export const api = {
  health: () => request("/api/health", {}, health),
  createSession: async (body: unknown) => {
    if (!USE_MOCK) return request("/api/sessions", { method: "POST", body: JSON.stringify(body) }, session);
    const created = clone(session);
    mockSessionSequence += 1;
    created.session_id = `ses_mock_${mockSessionSequence}`;
    created.balance = 0;
    return created;
  },
  deleteSession: async (sessionId: string) => {
    const result = await request(`/api/sessions/${sessionId}`, { method: "DELETE", headers: sessionHeaders() }, null);
    mockQuestStates.clear();
    try { localStorage.removeItem(MOCK_STATE_KEY); } catch { /* 무시 */ }
    return result;
  },
  getZones: () => request("/api/zones", {}, zones),
  getStops: (zoneCode: string) => request(`/api/stops?zone=${encodeURIComponent(zoneCode)}`, {}, stops),
  recommend: (body: unknown, relaxed = false) => request("/api/quests/recommend", { method: "POST", headers: sessionHeaders(), body: JSON.stringify(body) }, relaxed ? recommendRelaxed : recommend),
  getQuest: async (questId: string) => {
    const detail = await request(`/api/quests/${questId}`, { headers: sessionHeaders() }, questDetail);
    const state = USE_MOCK ? mockQuestStates.get(questId) : undefined;
    return state ? { ...detail, ...state } : detail;
  },
  startQuest: async (questId: string, body: unknown) => {
    const started = await request(`/api/quests/${questId}/start`, { method: "POST", headers: sessionHeaders(), body: JSON.stringify(body) }, questStart);
    if (USE_MOCK) rememberMockState(questId, { status: started.status, started_at: started.started_at });
    return started;
  },
  verifyQuest: async (questId: string, body: unknown, scenario: "success" | "fail" | "already" | "wrongStore" = "success") => {
    const mock = { success: verifySuccess, fail: verifyFail, already: verifyAlready, wrongStore: verifyWrongStore }[scenario];
    const verified = await request(`/api/quests/${questId}/verify`, { method: "POST", headers: sessionHeaders(), body: JSON.stringify(body) }, mock);
    if (USE_MOCK && "error" in verified) throw verified;
    if (USE_MOCK && !verified.already) {
      const current = mockQuestStates.get(questId);
      rememberMockState(questId, { status: "stamped", started_at: current?.started_at ?? null });
    }
    return verified;
  },
  generateRecord: (body: unknown) => request("/api/records", { method: "POST", headers: sessionHeaders(), body: JSON.stringify(body) }, recordDraft),
  saveRecord: (body: { quest_id?: string; answers?: string[] }) => {
    const answered = body.answers?.some(Boolean);
    const status = body.quest_id ? mockQuestStates.get(body.quest_id)?.status : undefined;
    const mock = !answered ? recordSaveNoPoints : status === "stamped" || !questDetail.mission ? recordSave : recordSaveUnverified;
    return request("/api/records", { method: "POST", headers: sessionHeaders(), body: JSON.stringify(body) }, mock);
  },
  getRecords: () => USE_MOCK
    ? Promise.resolve(mockRecordsForCurrentSession())
    : request("/api/records", { headers: sessionHeaders() }, recordsList),
  getDashboardAccessibility: () => request("/api/dashboard/accessibility", {}, dashboardAccessibility),
  getDashboardInflow: () => request("/api/dashboard/inflow", {}, dashboardInflow),
  getDashboardKpi: () => request("/api/dashboard/kpi", {}, dashboardStats),
  mockSessionNotFound: () => request("/api/records", {}, sessionNotFound),
};
