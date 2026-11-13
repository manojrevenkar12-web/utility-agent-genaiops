import type { Console } from "../../shared/types";
import { Empty } from "../../shared/ui";

const NAMES = { prompt_only: "Model decides", guarded: "Model reads, code decides" } as const;
const eur = (x: number) => `€${x.toLocaleString("en", { maximumFractionDigits: 0 })}`;

export function Designs({ designs, business, traffic }: { designs: Console["designs"]; business: Console["business_case"]; traffic: number }) {
  const keys = Object.keys(designs) as (keyof typeof NAMES)[];
  if (!keys.length) return <Empty>No designs measured in this run.</Empty>;
  const g = business.guarded;
  return (
    <>
      <div className="panel" style={{ overflowX: "auto" }}>
        <table>
          <thead><tr><th scope="col">On {traffic.toLocaleString("en")} production messages</th>{keys.map((k) => <th scope="col" key={k}>{NAMES[k]}</th>)}</tr></thead>
          <tbody>
            <tr><th scope="row">Handled right</th>{keys.map((k) => <td key={k}>{designs[k].right}%</td>)}</tr>
            <tr><th scope="row">Harmful actions per 1,000</th>{keys.map((k) => <td key={k}>{designs[k].harmful_per_1k}</td>)}</tr>
            <tr><th scope="row">Without a person</th>{keys.map((k) => <td key={k}>{designs[k].contained}%</td>)}</tr>
            <tr><th scope="row">Messages with personal data sent to the model</th>{keys.map((k) => <td key={k}>{designs[k].personal_data.sent_to_the_model.toLocaleString("en")}</td>)}</tr>
            <tr><th scope="row">Model cost per conversation</th>{keys.map((k) => <td key={k}>€{designs[k].eur_per_conversation.toFixed(4)}</td>)}</tr>
          </tbody>
        </table>
      </div>
      {g && (
        <div className="figures" style={{ marginTop: "var(--space-5)" }}>
          <div className="figure"><b>{g.handled_by_the_agent.toLocaleString("en")}</b><span>of {g.monthly_contacts.toLocaleString("en")} contacts a month handled right without a person (assumed volume)</span></div>
          <div className="figure"><b>{eur(g.eur_saved_per_month)}</b><span>a month at an assumed €5.20 per handled contact</span></div>
          <div className="figure"><b>{eur(g.model_eur_per_month)}</b><span>model cost a month</span></div>
        </div>
      )}
    </>
  );
}
