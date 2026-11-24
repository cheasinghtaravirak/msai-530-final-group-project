const AMOUNT = /^(\d+)(?:\.(\d{1,2}))?$/;

/** "3.4" or "3.40" -> 340. Null for anything that is not a non-negative amount with at most 2 decimals. */
export function toCents(amount: string): number | null {
  const m = AMOUNT.exec(amount.trim());
  if (!m) return null;
  return Number(m[1]) * 100 + Number((m[2] ?? "").padEnd(2, "0"));
}

/** 340 -> "3.40", the API's money format. */
export function fromCents(cents: number): string {
  const sign = cents < 0 ? "-" : "";
  const abs = Math.abs(cents);
  return `${sign}${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, "0")}`;
}
