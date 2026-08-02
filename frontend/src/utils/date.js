export function localToday() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

export function serviceDateOf(health) {
  return typeof health?.demo_now === "string" && health.demo_now.length >= 10
    ? health.demo_now.slice(0, 10)
    : localToday();
}
