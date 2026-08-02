export function NavIcon({ name }) {
  const paths = {
    home: <><path d="m3 10 9-7 9 7v9a2 2 0 0 1-2 2h-4v-6H9v6H5a2 2 0 0 1-2-2z" /></>,
    quest: <><path d="M12 21s7-5.1 7-11A7 7 0 1 0 5 10c0 5.9 7 11 7 11Z" /><circle cx="12" cy="10" r="2.4" /></>,
    archive: <path d="M5 3h14a1 1 0 0 1 1 1v17l-8-4-8 4V4a1 1 0 0 1 1-1Z" />,
  };
  return <svg viewBox="0 0 24 24" aria-hidden="true">{paths[name]}</svg>;
}
