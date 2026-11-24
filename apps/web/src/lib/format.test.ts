import {
  countdown,
  formatCents,
  formatShortDate,
  formatValueRange,
  isoToLocalInput,
  localInputToIso,
  parseReais,
} from "./format";

// O Intl usa espaço inseparável depois de "R$".
const plain = (s: string | null) => s?.replace(/\u00a0/g, " ");

test("formata centavos em reais", () => {
  expect(plain(formatCents(5000))).toBe("R$ 50,00");
  expect(plain(formatCents(123456))).toBe("R$ 1.234,56");
  expect(formatCents(null)).toBe("");
});

test("faixa de valores", () => {
  expect(plain(formatValueRange(5000, 10000))).toBe("R$ 50,00 a R$ 100,00");
  expect(plain(formatValueRange(null, 3000))).toBe("até R$ 30,00");
  expect(formatValueRange(null, null)).toBeNull();
});

test("converte texto em centavos", () => {
  expect(parseReais("50")).toBe(5000);
  expect(parseReais("49,90")).toBe(4990);
  expect(parseReais("1.234,56")).toBe(123456);
  expect(parseReais("R$ 10,5")).toBe(1050);
  expect(parseReais("")).toBeNull();
});

test("datas no fuso de Brasília", () => {
  expect(formatShortDate("2026-12-25T02:00:00Z")).toBe("24/12/2026");
  expect(localInputToIso("2026-12-24T20:00")).toBe("2026-12-24T23:00:00.000Z");
  expect(isoToLocalInput("2026-12-24T23:00:00Z")).toBe("2026-12-24T20:00");
});

test("contagem regressiva", () => {
  const now = Date.parse("2026-12-20T00:00:00Z");
  expect(countdown("2026-12-21T01:02:03Z", now)).toEqual({
    days: 1,
    hours: 1,
    minutes: 2,
    seconds: 3,
    past: false,
  });
  expect(countdown("2026-12-19T00:00:00Z", now).past).toBe(true);
});
