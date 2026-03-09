import { useEffect, useState } from "react";
import type {
  ChangesetSummary,
  Changeset,
  HighlightInput,
  RoutingInfo,
} from "../types";
import { confidenceClass, routingActionClass } from "../utils";
import { HighlightForm } from "./HighlightForm";
import { ChangesetReview } from "./ChangesetReview";
import { StatusBadge } from "./StatusBadge";
import { ErrorAlert } from "./ErrorAlert";

function RoutingSection({ routing }: { routing: RoutingInfo }) {
  return (
    <div>
      <h4 className="text-[13px] text-muted uppercase tracking-wide mb-2">
        Routing Decision
      </h4>
      <div className="flex flex-col gap-2">
        <div className="flex items-start gap-3">
          <span className="text-xs text-muted min-w-[120px] shrink-0">
            Action
          </span>
          <span
            className={`text-[11px] font-semibold py-0.5 px-2 rounded-[3px] uppercase ${routingActionClass(routing.action)}`}
          >
            {routing.action}
          </span>
        </div>
        {routing.target_path && (
          <div className="flex items-start gap-3">
            <span className="text-xs text-muted min-w-[120px] shrink-0">
              Target
            </span>
            <span className="font-mono text-[13px] text-accent">
              {routing.target_path}
            </span>
          </div>
        )}
        {routing.action === "skip" &&
          routing.duplicate_notes &&
          routing.duplicate_notes.length > 0 && (
            <div className="flex items-start gap-3">
              <span className="text-xs text-muted min-w-[120px] shrink-0">
                Already In
              </span>
              <div className="flex flex-col gap-1">
                {routing.duplicate_notes.map((path) => (
                  <span
                    key={path}
                    className="font-mono text-[13px] text-accent"
                  >
                    {path}
                  </span>
                ))}
              </div>
            </div>
          )}
        <div className="flex items-start gap-3">
          <span className="text-xs text-muted min-w-[120px] shrink-0">
            Confidence
          </span>
          <span
            className={`font-mono text-xs font-semibold ${confidenceClass(routing.confidence)}`}
          >
            {(routing.confidence * 100).toFixed(0)}%
          </span>
        </div>
        <div className="flex items-start gap-3">
          <span className="text-xs text-muted min-w-[120px] shrink-0">
            Reasoning
          </span>
          <span className="text-[13px] leading-normal">
            {routing.reasoning}
          </span>
        </div>
        {routing.search_results_used > 0 && (
          <div className="flex items-start gap-3">
            <span className="text-xs text-muted min-w-[120px] shrink-0">
              Search Results
            </span>
            <span>{routing.search_results_used} matches</span>
          </div>
        )}
      </div>
    </div>
  );
}

function ChangesetCard({
  cs,
  onSelect,
}: {
  cs: ChangesetSummary;
  onSelect: (id: string) => void;
}) {
  return (
    <div
      className="bg-surface border border-border rounded p-3 cursor-pointer transition-colors duration-150 hover:border-accent"
      onClick={() => onSelect(cs.id)}
    >
      <div className="flex items-center gap-2 mb-1.5">
        <StatusBadge status={cs.status} />
        {cs.routing_action && (
          <span
            className={`text-[11px] font-semibold py-0.5 px-2 rounded-[3px] uppercase ${routingActionClass(cs.routing_action)}`}
          >
            {cs.routing_action}
          </span>
        )}
        {cs.routing_confidence != null && (
          <span
            className={`font-mono text-xs font-semibold ml-auto ${confidenceClass(cs.routing_confidence)}`}
          >
            {(cs.routing_confidence * 100).toFixed(0)}%
          </span>
        )}
      </div>
      {cs.routing_target && (
        <div className="mb-1">
          <span className="font-mono text-[13px] text-accent">
            {cs.routing_target}
          </span>
        </div>
      )}
      <div className="flex items-center gap-2 text-[13px] text-muted mb-0.5">
        <span>{cs.source}</span>
        <span className="text-xs">
          {cs.highlight_count > 1 && `${cs.highlight_count} snippets · `}
          {cs.routing_action === "skip"
            ? "skipped (duplicate)"
            : `${cs.change_count} change${cs.change_count !== 1 ? "s" : ""}`}
        </span>
      </div>
      <div className="text-xs text-muted">
        {new Date(cs.created_at).toLocaleString()}
      </div>
    </div>
  );
}

function ChangesetDetail({
  changeset,
  previewLoading,
  onBack,
  onRegenerate,
  onDone,
}: {
  changeset: Changeset;
  previewLoading: boolean;
  onBack: () => void;
  onRegenerate: (changesetId: string, feedback: string) => void;
  onDone: () => void;
}) {
  const [showRegenerate, setShowRegenerate] = useState(false);
  const [feedback, setFeedback] = useState("");

  const handleRegenerate = () => {
    if (!feedback.trim()) return;
    onRegenerate(changeset.id, feedback.trim());
    setShowRegenerate(false);
    setFeedback("");
  };

  return (
    <div className="bg-surface border border-border rounded p-5 flex flex-col gap-5">
      <button
        className="bg-elevated text-text border border-border py-1 px-3 rounded text-xs self-start"
        onClick={onBack}
      >
        &larr; Back to list
      </button>

      <div>
        <h4 className="text-[13px] text-muted uppercase tracking-wide mb-2">
          {changeset.highlights.length > 1
            ? `Snippets (${changeset.highlights.length})`
            : "Snippet"}
        </h4>
        {changeset.highlights.map((h, i) => (
          <div key={i} className="mb-3">
            <blockquote className="bg-bg border-l-[3px] border-l-accent py-3 px-4 rounded-r text-sm leading-relaxed mb-1">
              {h.text}
            </blockquote>
            <div className="flex flex-col gap-0.5 text-[13px] text-muted pl-4">
              <span>Source: {h.source}</span>
              {h.annotation && <span>Note: {h.annotation}</span>}
            </div>
          </div>
        ))}
      </div>

      {changeset.routing && <RoutingSection routing={changeset.routing} />}

      {changeset.feedback && (
        <div className="bg-bg rounded p-3">
          <h4 className="text-[13px] text-muted uppercase tracking-wide mb-2">
            Regeneration Feedback
          </h4>
          <p className="text-[13px] text-muted italic">{changeset.feedback}</p>
        </div>
      )}

      {changeset.status === "skipped" && (
        <div className="bg-bg rounded p-4 flex flex-col gap-3">
          <p className="text-sm text-muted">
            This snippet was skipped — the information is already in the vault.
          </p>
          {changeset.routing?.duplicate_notes &&
            changeset.routing.duplicate_notes.length > 0 && (
              <div className="flex flex-col gap-1">
                <span className="text-xs text-muted uppercase tracking-wide">
                  Duplicate Notes
                </span>
                {changeset.routing.duplicate_notes.map((path) => (
                  <span
                    key={path}
                    className="font-mono text-[13px] text-accent"
                  >
                    {path}
                  </span>
                ))}
              </div>
            )}
          {changeset.routing?.reasoning && (
            <div className="flex flex-col gap-1">
              <span className="text-xs text-muted uppercase tracking-wide">
                Reasoning
              </span>
              <span className="text-[13px] leading-normal">
                {changeset.routing.reasoning}
              </span>
            </div>
          )}
          {showRegenerate ? (
            <div className="bg-surface rounded p-3">
              <h4 className="text-[13px] text-muted uppercase tracking-wide mb-2">
                Regenerate with Feedback
              </h4>
              <textarea
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                placeholder='e.g. "This is not a duplicate — please add it to..."'
                rows={3}
                className="w-full bg-bg border border-border rounded text-text py-2 px-3 text-sm font-sans resize-y mb-2 focus:outline-none focus:border-accent"
              />
              <div className="flex gap-2">
                <button
                  className="bg-accent text-crust border-none py-2 px-5 rounded text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                  onClick={handleRegenerate}
                  disabled={!feedback.trim() || previewLoading}
                >
                  {previewLoading ? "Regenerating..." : "Regenerate"}
                </button>
                <button
                  className="bg-elevated text-text border border-border py-1 px-3 rounded text-xs"
                  onClick={() => {
                    setShowRegenerate(false);
                    setFeedback("");
                  }}
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <button
              className="bg-transparent text-accent border border-accent py-2 px-5 rounded text-sm self-start"
              onClick={() => setShowRegenerate(true)}
            >
              Regenerate with Feedback
            </button>
          )}
        </div>
      )}

      {changeset.status === "pending" && (
        <>
          <ChangesetReview
            changesetId={changeset.id}
            initialChanges={changeset.changes}
            onDone={onDone}
          />

          {showRegenerate ? (
            <div className="bg-bg rounded p-3">
              <h4 className="text-[13px] text-muted uppercase tracking-wide mb-2">
                Regenerate with Feedback
              </h4>
              <textarea
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                placeholder="Tell the agent what to do differently..."
                rows={3}
                className="w-full bg-surface border border-border rounded text-text py-2 px-3 text-sm font-sans resize-y mb-2 focus:outline-none focus:border-accent"
              />
              <div className="flex gap-2">
                <button
                  className="bg-accent text-crust border-none py-2 px-5 rounded text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                  onClick={handleRegenerate}
                  disabled={!feedback.trim() || previewLoading}
                >
                  {previewLoading ? "Regenerating..." : "Regenerate"}
                </button>
                <button
                  className="bg-elevated text-text border border-border py-1 px-3 rounded text-xs"
                  onClick={() => {
                    setShowRegenerate(false);
                    setFeedback("");
                  }}
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <button
              className="bg-transparent text-accent border border-accent py-2 px-5 rounded text-sm self-start"
              onClick={() => setShowRegenerate(true)}
            >
              Regenerate with Feedback
            </button>
          )}
        </>
      )}

      {changeset.status !== "pending" && changeset.status !== "skipped" && (
        <div className="text-center py-4">
          <StatusBadge status={changeset.status} />
        </div>
      )}
    </div>
  );
}

interface Props {
  changesets: ChangesetSummary[];
  selectedChangeset: Changeset | null;
  loading: boolean;
  previewLoading: boolean;
  error: string | null;
  onRefresh: () => void;
  onSelect: (id: string) => void;
  onBack: () => void;
  onPreview: (highlights: HighlightInput[]) => void;
  onRegenerate: (changesetId: string, feedback: string) => void;
  onDone: () => void;
}

export function HighlightPreview({
  changesets,
  selectedChangeset,
  loading,
  previewLoading,
  error,
  onRefresh,
  onSelect,
  onBack,
  onPreview,
  onRegenerate,
  onDone,
}: Props) {
  useEffect(() => {
    onRefresh();
  }, [onRefresh]);

  if (selectedChangeset) {
    return (
      <div className="flex flex-col gap-4 max-w-[1080px]">
        {error && <ErrorAlert message={error} />}
        <ChangesetDetail
          changeset={selectedChangeset}
          previewLoading={previewLoading}
          onBack={onBack}
          onRegenerate={onRegenerate}
          onDone={onDone}
        />
      </div>
    );
  }

  const pendingChangesets = changesets.filter((cs) => cs.status === "pending");
  const otherChangesets = changesets.filter((cs) => cs.status !== "pending");

  return (
    <div className="flex flex-col gap-4 lg:grid lg:grid-cols-[minmax(360px,1fr)_minmax(400px,2fr)] lg:gap-6 lg:items-start">
      <div className="lg:sticky lg:top-0">
        <HighlightForm onSubmit={onPreview} disabled={previewLoading} />
      </div>

      <div className="flex flex-col gap-4">
        <div className="flex justify-between items-center">
          <h3 className="text-sm flex items-center gap-2">
            Pending Review
            {pendingChangesets.length > 0 && (
              <span className="text-xs font-normal text-yellow bg-yellow-bg py-0.5 px-2 rounded-[10px]">
                {pendingChangesets.length} pending
              </span>
            )}
          </h3>
          <button
            onClick={onRefresh}
            disabled={loading}
            className="bg-elevated text-text border border-border py-1 px-3 rounded text-xs"
          >
            {loading ? "..." : "Refresh"}
          </button>
        </div>

        {error && <ErrorAlert message={error} />}

        {changesets.length === 0 ? (
          <p className="text-muted text-center py-8">
            No pending reviews yet. Submit a snippet to get started.
          </p>
        ) : (
          <>
            {pendingChangesets.length > 0 && (
              <div className="flex flex-col gap-2">
                {pendingChangesets.map((cs) => (
                  <ChangesetCard key={cs.id} cs={cs} onSelect={onSelect} />
                ))}
              </div>
            )}
            {otherChangesets.length > 0 && (
              <div className="flex flex-col gap-2">
                <h4 className="text-xs text-muted uppercase tracking-wide">
                  Resolved
                </h4>
                <div className="flex flex-col gap-2">
                  {otherChangesets.map((cs) => (
                    <ChangesetCard key={cs.id} cs={cs} onSelect={onSelect} />
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
