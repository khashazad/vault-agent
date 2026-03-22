import { createBrowserRouter, Navigate, Outlet } from "react-router";
import { Layout } from "./components/Layout";
import { LibraryPage } from "./pages/LibraryPage";
import { AnnotationsPage } from "./pages/AnnotationsPage";
import { ChangesetsPage } from "./pages/ChangesetsPage";
import { ChangesetDetailPage } from "./pages/ChangesetDetailPage";
import { MigrationPage } from "./pages/MigrationPage";
import { ConnectVaultPage } from "./pages/ConnectVaultPage";
import { TaxonomyPage } from "./pages/TaxonomyPage";
import { ClawdyInboxPage } from "./pages/ClawdyInboxPage";

export const router = createBrowserRouter([
  {
    path: "/connect",
    element: <ConnectVaultPage />,
  },
  {
    path: "/",
    element: (
      <Layout>
        <Outlet />
      </Layout>
    ),
    children: [
      { index: true, element: <Navigate to="/library" replace /> },
      { path: "library", element: <LibraryPage /> },
      { path: "library/:paperKey", element: <AnnotationsPage /> },
      { path: "changesets", element: <ChangesetsPage /> },
      { path: "changesets/:changesetId", element: <ChangesetDetailPage /> },
      { path: "migration", element: <MigrationPage /> },
      { path: "taxonomy", element: <TaxonomyPage /> },
      { path: "clawdy", element: <ClawdyInboxPage /> },
    ],
  },
  { path: "*", element: <Navigate to="/connect" replace /> },
]);
