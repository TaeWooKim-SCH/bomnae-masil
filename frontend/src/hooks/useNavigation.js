import React from "react";
import { useLocation, useNavigate } from "react-router-dom";

export function useBackTo(fallback) {
  const navigate = useNavigate();
  const location = useLocation();
  return () => {
    if (location.key !== "default") navigate(-1);
    else navigate(fallback, { replace: true });
  };
}
