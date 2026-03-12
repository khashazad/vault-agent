import { useState } from "react";
import { Layout, type Tab } from "./components/Layout";
import { ZoteroSync } from "./components/ZoteroSync";
import { ChangesetHistory } from "./components/ChangesetHistory";

export default function App() {
  const [tab, setTab] = useState<Tab>("sync");

  return (
    <Layout currentTab={tab} onTabChange={setTab}>
      {tab === "sync" ? <ZoteroSync /> : <ChangesetHistory />}
    </Layout>
  );
}
