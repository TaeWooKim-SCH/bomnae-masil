export function AppHeader({ balance, titles, health }) {
  return (
    <header className="app-header">
      <a className="brand" href="/" aria-label="봄내마실 홈">봄내마실 · 춘천</a>
      <div className="header-status">
        {titles?.[0] && <span className="title-badge">{titles[0]}</span>}
        <strong className="balance">{balance.toLocaleString()}P</strong>
        <span className={health?.ok && health?.db ? "health health-ok" : "health"}>
          {health ? (health.ok && health.db ? "서비스 연결됨" : "서비스 확인 중") : "연결 확인 중"}
        </span>
      </div>
    </header>
  );
}
