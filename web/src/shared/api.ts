import { useQuery } from "@tanstack/react-query";
import type { Console } from "./types";

export async function fetchConsole(): Promise<Console> {
  const res = await fetch("data/console.json");
  if (!res.ok) throw new Error(`console data: HTTP ${res.status}`);
  return res.json();
}

export const useConsole = () => useQuery({ queryKey: ["console"], queryFn: fetchConsole, retry: false });
