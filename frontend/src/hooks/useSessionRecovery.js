import React from "react";
import { useNavigate } from "react-router-dom";

export function isSessionMissing(error) {
  return error?.error?.code === "SESSION_NOT_FOUND" || !localStorage.getItem("session_id");
}

export function useSessionRecovery() {
  const navigate = useNavigate();
  return React.useCallback((error) => {
    if (!isSessionMissing(error)) return false;
    localStorage.removeItem("session_id");
    localStorage.removeItem("active_quest_id");
    navigate("/", { replace: true });
    return true;
  }, [navigate]);
}
