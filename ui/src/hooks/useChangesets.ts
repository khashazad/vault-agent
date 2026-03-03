import { useState, useCallback } from "react";
import type { ChangesetSummary } from "../types";
import {
  fetchChangesets,
  applyChangeset,
  rejectChangeset,
  updateChangeStatus,
} from "../api/client";

export function useChangesets() {
  const [changesets, setChangesets] = useState<ChangesetSummary[]>([]);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchChangesets();
      setChangesets(data);
    } finally {
      setLoading(false);
    }
  }, []);

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

  return { changesets, loading, refresh, apply, reject, toggleChange };
}
