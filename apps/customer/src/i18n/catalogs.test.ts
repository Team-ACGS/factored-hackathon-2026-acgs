import { describe, expect, it } from "vitest";

import { en } from "./en";
import { es } from "./es";
import { ptBR } from "./pt-BR";

const catalogs = { en, es, "pt-BR": ptBR };

const claraFacing = (catalog: Record<string, string>) =>
  Object.entries(catalog).filter(([key]) => /^(clara|claim|help|transaction|pill)\./.test(key));

describe.each(Object.entries(catalogs))("%s catalog", (_, catalog) => {
  it("never says fraud in what Clara or the claims show", () => {
    for (const [key, text] of claraFacing(catalog)) expect(`${key}: ${text}`).not.toMatch(/fraud|fraude/i);
  });

  it("never mentions a due date or a legal term", () => {
    for (const [key, text] of Object.entries(catalog)) {
      expect(`${key}: ${text}`).not.toMatch(
        /\bdue\b|deadline|business days|a más tardar|plazo|días hábiles|prazo|dias úteis|até o dia/i,
      );
    }
  });
});
