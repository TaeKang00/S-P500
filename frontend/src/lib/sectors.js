const SECTOR_KO = {
  "Communication Services": "커뮤니케이션",
  "Consumer Discretionary": "경기소비재",
  "Consumer Staples": "필수소비재",
  "Energy": "에너지",
  "Financials": "금융",
  "Health Care": "헬스케어",
  "Industrials": "산업재",
  "Information Technology": "IT",
  "Materials": "소재",
  "Real Estate": "리츠",
  "Utilities": "유틸리티",
};

export function sectorKo(name) {
  if (!name) return "—";
  return SECTOR_KO[name] ?? name;
}
