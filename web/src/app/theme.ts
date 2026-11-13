// Every number the components use lives here or in tokens.css.
export const motion = {
  laneStagger: 0.06, // seconds between candidate rows as the lanes fill in
  duration: 0.32,
  ease: [0.2, 0.85, 0.25, 1] as [number, number, number, number],
};

export const skeletonStep = 12;

export const words = {
  shipped: "Shipped",
  blocked: "Blocked",
  inProduction: "In production",
};

export const outcomeWords: Record<string, string> = {
  accept_reading: "Reading saved", review_reading: "Reading to a person", change_instalment: "Instalment changed",
  offer_minimum: "Minimum offered", review_instalment: "Amount to a person", offer_plan: "Plan offered",
  no_balance: "Nothing open", escalate_priority: "Person today", escalate: "To a person",
  explain_bill: "Bill explained", explain_term: "Term explained", switch_tariff: "Tariff switched",
  explain_options: "Options listed", register_move: "Move noted", register_cancellation: "Cancellation noted",
  give_account_info: "Account answered", redirect_grid: "Sent to grid operator", answer_faq: "Answered from passage",
  ask_identity: "Asked to identify", ask_details: "Asked for detail", refuse: "Refused",
};
