import dashboardStats from "../mocks/dashboard_stats.json";
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
const mockQuestStates = new Map<string, { status: string; started_at: string | null }>();

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

export const api = {
  health: () => request("/api/health", {}, health),
  createSession: (body: unknown) => request("/api/sessions", { method: "POST", body: JSON.stringify(body) }, session),
  deleteSession: (sessionId: string) => request(`/api/sessions/${sessionId}`, { method: "DELETE", headers: sessionHeaders() }, null),
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
    if (USE_MOCK) mockQuestStates.set(questId, { status: started.status, started_at: started.started_at });
    return started;
  },
  verifyQuest: async (questId: string, body: unknown, scenario: "success" | "fail" | "already" | "wrongStore" = "success") => {
    const mock = { success: verifySuccess, fail: verifyFail, already: verifyAlready, wrongStore: verifyWrongStore }[scenario];
    const verified = await request(`/api/quests/${questId}/verify`, { method: "POST", headers: sessionHeaders(), body: JSON.stringify(body) }, mock);
    if (USE_MOCK && "error" in verified) throw verified;
    if (USE_MOCK && !verified.already) {
      const current = mockQuestStates.get(questId);
      mockQuestStates.set(questId, { status: "stamped", started_at: current?.started_at ?? null });
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
  getRecords: () => request("/api/records", { headers: sessionHeaders() }, recordsList),
  getDashboardAccessibility: () => request("/api/dashboard/accessibility", {}),
  getDashboardInflow: () => request("/api/dashboard/inflow", {}),
  getDashboardKpi: () => request("/api/dashboard/kpi", {}, dashboardStats),
  mockSessionNotFound: () => request("/api/records", {}, sessionNotFound),
};
