import { Designs } from "../features/designs/Designs";
import { Inspector } from "../features/inspector/Inspector";
import { ReleaseLanes } from "../features/releases/ReleaseLanes";
import { useConsole } from "../shared/api";
import { ErrorState, Section, Skeleton } from "../shared/ui";

export function App() {
  const { data, isPending, error, refetch } = useConsole();
  return (
    <main className="page">
      <header className="masthead">
        <h1>Every release of the service agent earns its way to customers.</h1>
        <p>
          An energy supplier's customer-service agent, and the eight changes the team wanted to ship. Each change was
          judged by a demo and by a gate on labelled messages; the console shows which reached customers and what
          that cost them.
        </p>
      </header>
      {isPending ? (
        <Skeleton rows={8} />
      ) : error ? (
        <ErrorState message={error.message} onRetry={() => refetch()} />
      ) : (
        <>
          <ReleaseLanes releases={data.releases} />
          <Section id="inspector" title="One message, three views"
            lede="Personal data leaves before the model reads; the model reads, code decides, and the reply is written from the decision.">
            <Inspector examples={data.examples} />
          </Section>
          <Section id="designs" title="Model decides, or code decides"
            lede={`The same model and release, ${Math.round(100 * data.german_share)} % of messages in German, counted against the simulated world's truth.`}>
            <Designs designs={data.designs} business={data.business_case} traffic={data.counts.traffic} />
          </Section>
          {data.heldout && (
            <Section id="heldout" title="On held-out customers"
              lede={`Run once with the release the gate ended on: ${data.heldout.guarded.right}% handled right and ${data.heldout.guarded.harmful_per_1k} harmful actions per 1,000 (model decides: ${data.heldout.prompt_only.harmful_per_1k}). The demo shipped ${data.heldout.demo_regressions} regressions, the gate ${data.heldout.gate_regressions}.`}>
              <></>
            </Section>
          )}
          <p className="muted">Generated from {data.generated_from}.</p>
        </>
      )}
    </main>
  );
}
