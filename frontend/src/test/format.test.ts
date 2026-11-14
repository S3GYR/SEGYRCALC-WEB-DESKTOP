import { describe, expect, it } from "vitest";
import {
  compareNumeric,
  formatApparentPower,
  formatCurrent,
  formatNumber,
  formatPower,
  formatReactivePower,
  statusLabel,
  statusTone,
} from "../format";

describe("formatage SEGYRCALC", () => {
  it("formate les puissances en W et kW", () => {
    expect(formatPower("8000")).toBe("8,00 kW");
    expect(formatPower("500")).toBe("500,00 W");
    expect(formatPower(null)).toBe("—");
  });

  it("formate les puissances apparentes et réactives", () => {
    expect(formatApparentPower("50167.858")).toBe("50,17 kVA");
    expect(formatReactivePower("6000")).toBe("6,00 kvar");
    expect(formatReactivePower("500")).toBe("500,00 var");
  });

  it("formate les courants et les nombres", () => {
    expect(formatCurrent("14.4337")).toBe("14,43 A");
    expect(formatNumber("0.8", 2)).toBe("0,80");
    expect(formatNumber(null)).toBe("—");
  });

  it("compare les nombres avec les valeurs absentes en dernier", () => {
    expect(compareNumeric("2", "10")).toBeLessThan(0);
    expect(compareNumeric(null, "10")).toBeGreaterThan(0);
    expect(compareNumeric("10", null)).toBeLessThan(0);
    expect(compareNumeric(null, null)).toBe(0);
  });

  it("traduit les statuts et les tonalités", () => {
    expect(statusLabel("OK")).toBe("Conforme");
    expect(statusLabel("NON_CALCULABLE")).toBe("Non calculable");
    expect(statusTone("OK")).toBe("ok");
    expect(statusTone("AVERTISSEMENT")).toBe("warn");
    expect(statusTone("ERREUR")).toBe("error");
    expect(statusTone("SYNTHETIC")).toBe("synthetic");
  });
});
