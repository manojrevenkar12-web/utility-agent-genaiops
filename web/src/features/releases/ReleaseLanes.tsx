import { motion as m } from "framer-motion";
import { motion, words } from "../../app/theme";
import type { Console, Step } from "../../shared/types";
import { Empty } from "../../shared/ui";
import "./releases.css";

function Cell({ step }: { step: Step }) {
  const shipped = step.decision === "shipped";
  const hurt = shipped && step.truly_worse;
  return (
    <div className={`lane-cell ${shipped ? "is-shipped" : "is-blocked"}${hurt ? " is-hurt" : ""}`}>
      <strong>{shipped ? words.shipped : words.blocked}</strong>
      {!shipped && step.why && <span className="lane-why">{step.why}</span>}
      {hurt && <span className="lane-why">A regression reached customers.</span>}
      {!shipped && step.truly_worse && <span className="lane-verdict">Stopped a real regression.</span>}
      {!shipped && !step.truly_worse && <span className="lane-verdict">Held back an improvement.</span>}
    </div>
  );
}

export function ReleaseLanes({ releases }: { releases: Console["releases"] }) {
  const demo = releases.demo.steps.slice(1);
  const gate = releases.gate.steps.slice(1);
  if (!demo.length) return <Empty>No candidate releases in this run.</Empty>;
  return (
    <div className="lanes">
      <div className="lanes-head" aria-hidden>
        <span>Candidate</span>
        <span>Ship if the 10 demo chats look right</span>
        <span>Ship through the gate on the golden set</span>
      </div>
      <ol className="lanes-rows">
        {demo.map((d, i) => (
          <m.li key={d.release} className="lane-row" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
            transition={{ duration: motion.duration, delay: i * motion.laneStagger, ease: motion.ease }}>
            <div className="lane-name"><span>{d.release}</span></div>
            <Cell step={d} />
            <Cell step={gate[i]} />
          </m.li>
        ))}
      </ol>
      <div className="figures lanes-totals">
        <div className="figure"><b>{releases.demo.regressions_shipped} vs {releases.gate.regressions_shipped}</b>
          <span>regressions shipped, demo vs gate</span></div>
        <div className="figure"><b>{releases.demo.harmful_actions_over_releases} vs {releases.gate.harmful_actions_over_releases}</b>
          <span>harmful actions customers met over the releases</span></div>
      </div>
    </div>
  );
}
