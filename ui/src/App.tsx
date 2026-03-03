import { useState, useCallback } from "react";
import { Layout } from "./components/Layout";
import { HighlightForm } from "./components/HighlightForm";
import { AgentStream } from "./components/AgentStream";
import { ChangesetReview } from "./components/ChangesetReview";
import { ChangesetHistory } from "./components/ChangesetHistory";
import { useAgentStream } from "./hooks/useAgentStream";
import { useChangesets } from "./hooks/useChangesets";
import type { HighlightInput } from "./types";

export default function App() {
  const [view, setView] = useState("new");
  const agent = useAgentStream();
  const changesets = useChangesets();

  const handleSubmit = useCallback(
    (highlight: HighlightInput) => {
      agent.start(highlight);
    },
    [agent.start]
  );

  const handleDone = useCallback(() => {
    agent.reset();
    changesets.refresh();
  }, [agent.reset, changesets.refresh]);

  return (
    <Layout activeView={view} onViewChange={setView}>
      {view === "new" && (
        <div className="new-highlight-view">
          <HighlightForm
            onSubmit={handleSubmit}
            disabled={agent.status === "streaming"}
          />

          {agent.error && (
            <div className="error-banner">
              <strong>Error:</strong> {agent.error}
            </div>
          )}

          <AgentStream
            reasoning={agent.reasoning}
            toolCalls={agent.toolCalls}
            isStreaming={agent.status === "streaming"}
          />

          {agent.status === "complete" &&
            agent.changesetId &&
            agent.proposedChanges.length > 0 && (
              <ChangesetReview
                changesetId={agent.changesetId}
                initialChanges={agent.proposedChanges}
                onDone={handleDone}
              />
            )}

          {agent.status === "complete" &&
            agent.proposedChanges.length === 0 && (
              <div className="no-changes">
                <p>
                  The agent completed without proposing any changes to the vault.
                </p>
                <button onClick={handleDone}>Start New</button>
              </div>
            )}
        </div>
      )}

      {view === "history" && (
        <ChangesetHistory
          changesets={changesets.changesets}
          loading={changesets.loading}
          onRefresh={changesets.refresh}
        />
      )}
    </Layout>
  );
}
