import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { marks } from "../features/inspector/Inspector";
import type { Console } from "../shared/types";
import { App } from "./App";

const sum = { right: 96.5, harmful_per_1k: 2, contained: 84.8, eur_per_conversation: 0.0045 };
const design = { ...sum, right_and_contained: 84.4, personal_data: { messages_with_personal_data: 1517, sent_to_the_model: 3 } };
const sample = {
  generated_from: "reports/dev.json", counts: { golden: 600, traffic: 2000, demo: 10 }, german_share: 0.66,
  designs: { prompt_only: { ...design, harmful_per_1k: 97 }, guarded: design },
  business_case: { guarded: { monthly_contacts: 60000, handled_by_the_agent: 50640, eur_saved_per_month: 263060,
    model_eur_per_month: 267.6, harmful_actions_per_month: 120 } },
  releases: {
    demo: { regressions_shipped: 3, harmful_actions_over_releases: 205, steps: [
      { release: "r0", decision: "in production", why: "", ...sum },
      { release: "r2 mini model to cut cost", decision: "shipped", why: "every demo chat handled right", truly_worse: true, ...sum }] },
    gate: { regressions_shipped: 1, harmful_actions_over_releases: 44, steps: [
      { release: "r0", decision: "in production", why: "", ...sum },
      { release: "r2 mini model to cut cost", decision: "blocked", why: "+20 harmful actions on the golden set", truly_worse: true, ...sum }] },
  },
  examples: [{ id: "g1", channel: "chat", lang: "de", text: "Kundennummer 1065482, PLZ 20176.\nViele Grüße\nAnna Schmidt",
    model_saw: "Kundennummer [KUNDENNR_1], PLZ [PLZ].\nViele Grüße\n[NAME]", intent: "account_info", confidence: 0.9,
    outcome: "give_account_info", reason: "", reply: "Offener Betrag: 0,00 €.", right: true, cost_eur: 0.0044 }],
  heldout: null,
} as unknown as Console;

const renderApp = () => render(<QueryClientProvider client={new QueryClient()}><App /></QueryClientProvider>);
afterEach(() => vi.restoreAllMocks());

describe("console", () => {
  it("shows a skeleton, then which release reached customers and why the gate stopped it", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(sample)));
    renderApp();
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect(await screen.findByText("A regression reached customers.")).toBeTruthy();
    expect(screen.getByText("+20 harmful actions on the golden set")).toBeTruthy();
    expect(screen.getByText("3 vs 1")).toBeTruthy();
    expect(screen.getByText("[KUNDENNR_1]")).toBeTruthy();
  });

  it("offers a retry when the data does not load", async () => {
    const f = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(new Response("", { status: 500 }));
    renderApp();
    expect(await screen.findByRole("alert")).toBeTruthy();
    f.mockResolvedValueOnce(new Response(JSON.stringify(sample)));
    fireEvent.click(screen.getByText("Retry"));
    await waitFor(() => expect(screen.getByText("3 vs 1")).toBeTruthy());
  });

  it("says what to do when the run is empty", async () => {
    const empty = { ...sample, examples: [], releases: { demo: { ...sample.releases.demo, steps: [] }, gate: sample.releases.gate } };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(empty)));
    renderApp();
    expect(await screen.findByText(/No candidate releases/)).toBeTruthy();
    expect(screen.getByText(/No conversations in this run/)).toBeTruthy();
  });

  it("marks every placeholder the model saw", () => {
    const { container } = render(<p>{marks("PLZ [PLZ], IBAN [IBAN].")}</p>);
    expect(container.querySelectorAll("mark").length).toBe(2);
  });
});
