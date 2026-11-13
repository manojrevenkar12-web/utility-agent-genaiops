import { AnimatePresence, motion as m } from "framer-motion";
import { useState } from "react";
import { motion, outcomeWords } from "../../app/theme";
import type { Example } from "../../shared/types";
import { Empty } from "../../shared/ui";
import "./inspector.css";

export function marks(text: string) {
  return text.split(/(\[[A-Z_0-9]+\])/g).map((part, i) =>
    /^\[[A-Z_0-9]+\]$/.test(part) ? <mark key={i} className="masked">{part}</mark> : <span key={i}>{part}</span>);
}

export function Inspector({ examples }: { examples: Example[] }) {
  const [i, setI] = useState(0);
  if (!examples.length) return <Empty>No conversations in this run yet. Run python3 scripts/evaluate.py.</Empty>;
  const ex = examples[Math.min(i, examples.length - 1)];
  return (
    <div className="inspector">
      <div className="chips" role="tablist" aria-label="Conversations">
        {examples.map((e, k) => (
          <button key={e.id} role="tab" aria-selected={k === i} className="chip" onClick={() => setI(k)}>
            {outcomeWords[e.outcome] ?? e.outcome}, {e.lang.toUpperCase()}
          </button>
        ))}
      </div>
      <AnimatePresence mode="wait">
        <m.div key={ex.id} className="flow" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          transition={{ duration: motion.duration, ease: motion.ease }}>
          <section className="panel">
            <h3>The customer wrote ({ex.channel})</h3>
            <p className="msg">{ex.text}</p>
          </section>
          <section className="panel">
            <h3>The model saw</h3>
            <p className="msg">{marks(ex.model_saw)}</p>
            <p className="muted read">Read as <b>{ex.intent.replace("_", " ")}</b>, confidence {ex.confidence}</p>
          </section>
          <section className={`panel decision ${ex.right ? "is-right" : "is-wrong"}`}>
            <h3>Code decided: {outcomeWords[ex.outcome] ?? ex.outcome}</h3>
            <p className="muted">{ex.reason}</p>
            <p className="msg">{ex.reply}</p>
            <p className="muted">{ex.right ? "As the service team labelled it" : "Not what the service team labelled"}, model cost €{ex.cost_eur.toFixed(4)}</p>
          </section>
        </m.div>
      </AnimatePresence>
    </div>
  );
}
