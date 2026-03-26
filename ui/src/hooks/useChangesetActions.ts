import { useCallback, useEffect, useRef, useState } from "react";
import {
  applyChangeset,
  convergeClawdy,
  fetchChangeset,
  fetchClawdyConfig,
  rejectChangeset,
  updateChangeContent,
  updateChangeStatus,
} from "../api/client";
import type { ProposedChange, SourceType } from "../types";
import { formatError } from "../utils";

export type ViewMode = "diff" | "preview" | "edit";

interface UseChangesetActionsInput {
  changesetId: string;
  initialChanges: ProposedChange[];
  sourceType: SourceType;
  onDone: () => void;
}

interface ApplyResult {
  applied: string[];
  failed: { id: string; error: string }[];
}

interface UseChangesetActionsReturn {
  changes: ProposedChange[];
  setChangeStatus: (
    changeId: string,
    status: "approved" | "rejected" | "pending",
  ) => void;
  setAllStatuses: (status: "approved" | "rejected") => void;
  toggleChange: (changeId: string) => void;
  handleApply: () => Promise<void>;
  handleReject: () => Promise<void>;
  handleEditChange: (changeId: string, content: string) => void;
  applying: boolean;
  statusError: string | null;
  result: ApplyResult | null;
  savingIds: Set<string>;
  editBuffers: Record<string, string>;
  viewModes: Record<string, ViewMode>;
  setViewMode: (changeId: string, mode: ViewMode) => void;
}

export function useChangesetActions({
  changesetId,
  initialChanges,
  sourceType,
  onDone,
}: UseChangesetActionsInput): UseChangesetActionsReturn {
  const [changes, setChanges] = useState(initialChanges);
  const [viewModes, setViewModes] = useState<Record<string, ViewMode>>({});
  const [editBuffers, setEditBuffers] = useState<Record<string, string>>({});
  const [applying, setApplying] = useState(false);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [result, setResult] = useState<ApplyResult | null>(null);
  const [savingIds, setSavingIds] = useState<Set<string>>(new Set());
  const debounceTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>(
    {},
  );
  const syncedIds = useRef<Set<string>>(new Set());

  useEffect(() => {
    setChanges(initialChanges);
  }, [initialChanges]);

  useEffect(() => {
    return () => {
      Object.values(debounceTimers.current).forEach((timer) =>
        clearTimeout(timer),
      );
    };
  }, []);

  const setChangeStatus = useCallback(
    (changeId: string, status: "approved" | "rejected" | "pending") => {
      setChanges((prev) =>
        prev.map((change) =>
          change.id === changeId ? { ...change, status } : change,
        ),
      );
      syncedIds.current.delete(changeId);
    },
    [],
  );

  const toggleChange = useCallback(
    (changeId: string) => {
      setChanges((prev) =>
        prev.map((change) => {
          if (change.id !== changeId) return change;
          const nextStatus =
            change.status === "approved" ? "rejected" : "approved";
          updateChangeStatus(changesetId, changeId, nextStatus).catch((error) =>
            setStatusError(formatError(error)),
          );
          return { ...change, status: nextStatus };
        }),
      );
    },
    [changesetId],
  );

  const setAllStatuses = useCallback((status: "approved" | "rejected") => {
    setChanges((prev) => prev.map((change) => ({ ...change, status })));
    syncedIds.current.clear();
  }, []);

  const handleEditChange = useCallback(
    (changeId: string, content: string) => {
      setEditBuffers((prev) => ({ ...prev, [changeId]: content }));
      setSavingIds((prev) => {
        const next = new Set(prev);
        next.add(changeId);
        return next;
      });

      if (debounceTimers.current[changeId]) {
        clearTimeout(debounceTimers.current[changeId]);
      }

      debounceTimers.current[changeId] = setTimeout(async () => {
        try {
          await updateChangeContent(changesetId, changeId, content);
          const changeset = await fetchChangeset(changesetId);
          setChanges((prev) =>
            prev.map((change) => {
              const updated = changeset.changes.find(
                (candidate) => candidate.id === change.id,
              );
              return updated ? { ...updated, status: change.status } : change;
            }),
          );
        } catch (error) {
          setStatusError(formatError(error));
        } finally {
          setSavingIds((prev) => {
            const next = new Set(prev);
            next.delete(changeId);
            return next;
          });
        }
      }, 500);
    },
    [changesetId],
  );

  const maybeConverge = useCallback(async () => {
    try {
      const config = await fetchClawdyConfig();
      if (!config.copy_vault_path) {
        return;
      }
      await convergeClawdy(changesetId);
    } catch (error) {
      if (sourceType === "clawdy") {
        throw error;
      }
    }
  }, [changesetId, sourceType]);

  const handleApply = useCallback(async () => {
    const approvedIds = changes
      .filter((change) => change.status === "approved")
      .map((change) => change.id);

    if (approvedIds.length === 0) {
      return;
    }

    setApplying(true);
    setStatusError(null);

    try {
      const unsynced = changes.filter(
        (change) =>
          !syncedIds.current.has(change.id) &&
          (change.status === "approved" || change.status === "rejected"),
      );

      for (let index = 0; index < unsynced.length; index += 10) {
        const batch = unsynced.slice(index, index + 10);
        await Promise.all(
          batch.map((change) =>
            updateChangeStatus(
              changesetId,
              change.id,
              change.status as "approved" | "rejected",
            ),
          ),
        );
        batch.forEach((change) => syncedIds.current.add(change.id));
      }

      const applyResult = await applyChangeset(changesetId, approvedIds);
      setResult(applyResult);

      try {
        await maybeConverge();
      } catch (error) {
        setStatusError(
          `Applied to vault but copy-vault sync failed: ${formatError(error)}`,
        );
      }
    } catch (error) {
      setResult({
        applied: [],
        failed: [{ id: "all", error: formatError(error) }],
      });
    } finally {
      setApplying(false);
    }
  }, [changes, changesetId, maybeConverge]);

  const handleReject = useCallback(async () => {
    try {
      await rejectChangeset(changesetId);
      await maybeConverge();
      onDone();
    } catch (error) {
      setStatusError(formatError(error));
    }
  }, [changesetId, maybeConverge, onDone]);

  const setViewMode = useCallback((changeId: string, mode: ViewMode) => {
    setViewModes((prev) => ({ ...prev, [changeId]: mode }));
  }, []);

  return {
    changes,
    setChangeStatus,
    setAllStatuses,
    toggleChange,
    handleApply,
    handleReject,
    handleEditChange,
    applying,
    statusError,
    result,
    savingIds,
    editBuffers,
    viewModes,
    setViewMode,
  };
}
