import { useState, useCallback } from "react";
import { Layout } from "./components/Layout";
import { ChangesetHistory } from "./components/ChangesetHistory";
import { VaultSearch } from "./components/VaultSearch";
import { HighlightPreview } from "./components/HighlightPreview";
import { ZoteroSync } from "./components/ZoteroSync";
import { useChangesets } from "./hooks/useChangesets";

export default function App() {
  const [view, setView] = useState("preview");
  const changesets = useChangesets();

  const handleDone = useCallback(() => {
    changesets.clearSelection();
    changesets.refresh();
  }, [changesets.clearSelection, changesets.refresh]);

  return (
    <Layout activeView={view} onViewChange={setView}>
      {view === "preview" && (
        <HighlightPreview
          changesets={changesets.changesets}
          selectedChangeset={changesets.selectedChangeset}
          loading={changesets.loading}
          previewLoading={changesets.previewLoading}
          error={changesets.error}
          onRefresh={changesets.refresh}
          onSelect={changesets.select}
          onBack={changesets.clearSelection}
          onPreview={changesets.preview}
          onRegenerate={changesets.regenerate}
          onDone={handleDone}
        />
      )}

      {view === "search" && <VaultSearch />}

      {view === "history" && (
        <ChangesetHistory
          changesets={changesets.changesets}
          loading={changesets.loading}
          onRefresh={changesets.refresh}
        />
      )}

      {view === "zotero" && <ZoteroSync onViewChange={setView} />}
    </Layout>
  );
}
