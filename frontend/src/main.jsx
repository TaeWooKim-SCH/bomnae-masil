import React, { Suspense, lazy } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import "./styles.css";

function lazyPage(loadPage, exportName) {
  return lazy(() => loadPage().then((module) => ({ default: module[exportName] })));
}

// 첫 방문에 필요한 화면만 내려받고, 나머지 화면은 실제 진입할 때 불러온다.
// 라우팅·화면 구성은 그대로 유지해 초기 번들만 가볍게 만든다.
const HomePage = lazyPage(() => import("./pages/HomePage"), "HomePage");
const RecommendPage = lazyPage(() => import("./pages/RecommendPage"), "RecommendPage");
const QuestDetailPage = lazyPage(() => import("./pages/QuestDetailPage"), "QuestDetailPage");
const VerifyPage = lazyPage(() => import("./pages/VerifyPage"), "VerifyPage");
const RecordPage = lazyPage(() => import("./pages/RecordPage"), "RecordPage");
const DashboardPage = lazyPage(() => import("./pages/DashboardPage"), "DashboardPage");

function VerifyDeepLink() {
  const navigate = useNavigate();
  const location = useLocation();
  React.useEffect(() => {
    const params = new URLSearchParams(location.search);
    const code = params.get("c") ?? "";
    const activeId = localStorage.getItem("active_quest_id");
    if (activeId) navigate(`/verify/${activeId}`, { replace: true, state: { code } });
    else navigate("/", { replace: true, state: { qrNotice: true } });
  }, [navigate, location.search]);
  return null;
}

function RouterApp() {
  return <Suspense fallback={null}><Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/recommend" element={<RecommendPage />} />
      <Route path="/quests/:questId" element={<QuestDetailPage />} />
      <Route path="/verify" element={<VerifyDeepLink />} />
      <Route path="/verify/:questId" element={<VerifyPage />} />
      <Route path="/records/:questId" element={<RecordPage />} />
      <Route path="/records" element={<RecordPage />} />
      <Route path="/dashboard" element={<DashboardPage />} />
      <Route path="*" element={<HomePage />} />
    </Routes></Suspense>;
}

createRoot(document.getElementById("root")).render(<BrowserRouter><RouterApp /></BrowserRouter>);
