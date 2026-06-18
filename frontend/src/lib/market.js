export function isMarketOpen() {
  const now = new Date();
  const et = new Date(now.toLocaleString("en-US", { timeZone: "America/New_York" }));
  const day = et.getDay(); // 0=Sun 6=Sat
  if (day === 0 || day === 6) return false;
  const h = et.getHours(), m = et.getMinutes();
  return (h > 9 || (h === 9 && m >= 30)) && h < 16;
}
