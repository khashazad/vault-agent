import { useState, useCallback } from "react";
import type { ChangesetSummary, Changeset, HighlightInput } from "../types";
import {
  fetchChangesets,
  fetchChangeset,
  applyChangeset,
  rejectChangeset,
  updateChangeStatus,
  previewHighlight,
  previewBatch,
  regenerateChangeset,
} from "../api/client";
import { formatError } from "../utils";

export function useChangesets() {
  const [changesets, setChangesets] = useState<ChangesetSummary[]>([]);
  const [selectedChangeset, setSelectedChangeset] = useState<Changeset | null>(
    null
  );
  const [loading, setLoading] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchChangesets();
      setChangesets(data);
    } catch (err) {
      setError(formatError(err));
    } finally {
      setLoading(false);
    }
  }, []);

  const select = useCallback(async (id: string) => {
    setError(null);
    try {
      const cs = await fetchChangeset(id);
      setSelectedChangeset(cs);
    } catch (err) {
      setError(formatError(err));
    }
  }, []);

  const clearSelection = useCallback(() => {
    setSelectedChangeset(null);
  }, []);

  const preview = useCallback(
    async (highlights: HighlightInput[]) => {
      setPreviewLoading(true);
      setError(null);
      try {
        const cs =
          highlights.length === 1
            ? await previewHighlight(highlights[0])
            : await previewBatch(highlights);
        setSelectedChangeset(cs);
        await refresh();
      } catch (err) {
        setError(formatError(err));
      } finally {
        setPreviewLoading(false);
      }
    },
    [refresh]
  );

  const regenerate = useCallback(
    async (changesetId: string, feedback: string) => {
      setPreviewLoading(true);
      setError(null);
      try {
        const cs = await regenerateChangeset(changesetId, feedback);
        setSelectedChangeset(cs);
        await refresh();
      } catch (err) {
        setError(formatError(err));
      } finally {
        setPreviewLoading(false);
      }
    },
    [refresh]
  );

  const apply = useCallback(
    async (changesetId: string, changeIds?: string[]) => {
      const result = await applyChangeset(changesetId, changeIds);
      await refresh();
      return result;
    },
    [refresh]
  );

  const reject = useCallback(
    async (changesetId: string) => {
      await rejectChangeset(changesetId);
      await refresh();
    },
    [refresh]
  );

  const toggleChange = useCallback(
    async (
      changesetId: string,
      changeId: string,
      status: "approved" | "rejected"
    ) => {
      await updateChangeStatus(changesetId, changeId, status);
    },
    []
  );

  return {
    changesets,
    selectedChangeset,
    loading,
    previewLoading,
    error,
    refresh,
    select,
    clearSelection,
    preview,
    regenerate,
    apply,
    reject,
    toggleChange,
  };
}
