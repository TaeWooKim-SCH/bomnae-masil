import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import "./styles.css";
import { HomePage } from "./pages/HomePage";
import { RecommendPage } from "./pages/RecommendPage";
import { QuestDetailPage } from "./pages/QuestDetailPage";
import { VerifyPage } from "./pages/VerifyPage";
import { RecordPage } from "./pages/RecordPage";
import { DashboardPage } from "./pages/DashboardPage";

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
  return <Routes>
    <Route path="/" element={<HomePage />} />
    <Route path="/recommend" element={<RecommendPage />} />
    <Route path="/quests/:questId" element={<QuestDetailPage />} />
    <Route path="/verify" element={<VerifyDeepLink />} />
    <Route path="/verify/:questId" element={<VerifyPage />} />
    <Route path="/records/:questId" element={<RecordPage />} />
    <Route path="/records" element={<RecordPage />} />
    <Route path="/dashboard" element={<DashboardPage />} />
    <Route path="*" element={<HomePage />} />
  </Routes>;
}

createRoot(document.getElementById("root")).render(<BrowserRouter><RouterApp /></BrowserRouter>);
