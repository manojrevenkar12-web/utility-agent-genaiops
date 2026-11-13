import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import committedData from "../../public/data/console.json";
import { App } from "./App";

// the committed dashboard data, not a hand-written sample: a field the report stops writing breaks this test
const committed = JSON.stringify(committedData);
afterEach(() => vi.restoreAllMocks());

it("renders the committed console data without errors", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(committed));
  render(<QueryClientProvider client={new QueryClient()}><App /></QueryClientProvider>);
  expect(await screen.findByText(/regressions shipped, demo vs gate/)).toBeTruthy();
  expect(screen.getAllByRole("tab").length).toBeGreaterThan(0);
  expect(screen.getByText("The model saw")).toBeTruthy();
});
