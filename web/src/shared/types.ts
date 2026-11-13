export interface Summary {
  right: number;
  harmful_per_1k: number;
  contained: number;
  eur_per_conversation: number;
}

export interface Step extends Summary {
  release: string;
  decision: "in production" | "shipped" | "blocked";
  why: string;
  truly_worse?: boolean;
}

export interface Design extends Summary {
  right_and_contained: number;
  personal_data: { messages_with_personal_data: number; sent_to_the_model: number };
}

export interface Example {
  id: string;
  channel: string;
  lang?: string;
  text: string;
  model_saw: string;
  intent: string;
  confidence: number;
  outcome: string;
  reason: string;
  reply: string;
  right: boolean;
  cost_eur: number;
}

export interface Console {
  generated_from: string;
  counts: Record<string, number>;
  german_share: number;
  designs: Record<"prompt_only" | "guarded", Design>;
  business_case: Record<string, { monthly_contacts: number; handled_by_the_agent: number; eur_saved_per_month: number;
    model_eur_per_month: number; harmful_actions_per_month: number }>;
  releases: Record<"demo" | "gate", { steps: Step[]; regressions_shipped: number; harmful_actions_over_releases: number }>;
  examples: Example[];
  heldout: null | { guarded: Design; prompt_only: Design; demo_regressions: number; gate_regressions: number };
}
