import { useState, useEffect, useCallback } from "react";
import { NavLink, useLocation, useSearchParams } from "react-router";
import { useVault } from "../context/VaultContext";
import { fetchZoteroCollections } from "../api/client";
import {
  CollectionTree,
  CollectionTreeSkeleton,
} from "../components/CollectionTree";
import type { ZoteroCollection } from "../types";

const NAV_ITEMS = [
  {
    to: "/library",
    label: "Library",
    icon: (
      <svg
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H19a1 1 0 0 1 1 1v18a1 1 0 0 1-1 1H6.5a1 1 0 0 1 0-5H20" />
      </svg>
    ),
  },
  {
    to: "/changesets",
    label: "Changesets",
    icon: (
      <svg
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M16 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V8Z" />
        <path d="M15 3v4a2 2 0 0 0 2 2h4" />
      </svg>
    ),
  },
  {
    to: "/migration",
    label: "Migration",
    icon: (
      <svg
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M3 7V5a2 2 0 0 1 2-2h2" />
        <path d="M17 3h2a2 2 0 0 1 2 2v2" />
        <path d="M21 17v2a2 2 0 0 1-2 2h-2" />
        <path d="M7 21H5a2 2 0 0 1-2-2v-2" />
        <rect width="7" height="5" x="7" y="7" rx="1" />
        <rect width="7" height="5" x="10" y="12" rx="1" />
      </svg>
    ),
  },
  {
    to: "/taxonomy",
    label: "Taxonomy",
    icon: (
      <svg
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M12 2L2 7l10 5 10-5-10-5Z" />
        <path d="m2 17 10 5 10-5" />
        <path d="m2 12 10 5 10-5" />
      </svg>
    ),
  },
  {
    to: "/preview",
    label: "Preview",
    icon: (
      <svg
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z" />
        <circle cx="12" cy="12" r="3" />
      </svg>
    ),
  },
];

export function Sidebar() {
  const { vaultName, vaultPath } = useVault();
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const isLibraryRoute = location.pathname.startsWith("/library");

  const [collections, setCollections] = useState<ZoteroCollection[]>([]);
  const [collectionsLoading, setCollectionsLoading] = useState(false);
  const [collectionsExpanded, setCollectionsExpanded] = useState(true);

  const selectedCollectionKey = searchParams.get("collection");

  const loadCollections = useCallback(async () => {
    setCollectionsLoading(true);
    try {
      const res = await fetchZoteroCollections();
      setCollections(res.collections);
    } catch {
      // Non-fatal
    } finally {
      setCollectionsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isLibraryRoute) loadCollections();
  }, [isLibraryRoute, loadCollections]);

  function handleSelectCollection(key: string | null) {
    if (key) {
      setSearchParams({ collection: key });
    } else {
      setSearchParams({});
    }
  }

  return (
    <aside className="w-[248px] h-screen flex flex-col bg-surface shrink-0">
      {/* Branding */}
      <div className="px-5 pt-5 pb-4">
        <NavLink
          to="/connect"
          className="flex items-center gap-2.5 no-underline"
        >
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#cba6f7] to-[#89b4fa] flex items-center justify-center text-[#11111b] text-xs font-bold">
            VA
          </div>
          <span className="text-sm font-bold text-text font-display">
            Vault Agent
          </span>
        </NavLink>
      </div>

      {/* Nav */}
      <nav className="px-3 flex flex-col gap-0.5">
        {NAV_ITEMS.map(({ to, label, icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-2.5 px-3 h-10 rounded-lg text-sm no-underline transition-colors ${
                isActive
                  ? "bg-purple/10 text-purple font-medium border-l-2 border-purple -ml-0.5 pl-[10px]"
                  : "text-muted hover:text-text hover:bg-elevated/50"
              }`
            }
          >
            {icon}
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Collections section — only on /library* routes */}
      {isLibraryRoute && (
        <div className="flex-1 flex flex-col min-h-0 mt-4">
          <button
            onClick={() => setCollectionsExpanded(!collectionsExpanded)}
            className="mx-5 mb-1 flex items-center justify-between bg-transparent border-none cursor-pointer p-0"
          >
            <span className="text-[10px] text-muted uppercase tracking-wide font-semibold">
              Collections
            </span>
            <svg
              width="10"
              height="10"
              viewBox="0 0 10 10"
              fill="currentColor"
              className={`text-muted transition-transform ${collectionsExpanded ? "rotate-90" : ""}`}
            >
              <path d="M3 1l5 4-5 4V1z" />
            </svg>
          </button>

          {collectionsExpanded && (
            <div className="flex-1 overflow-y-auto px-3 pb-2">
              {collectionsLoading ? (
                <CollectionTreeSkeleton />
              ) : collections.length > 0 ? (
                <CollectionTree
                  collections={collections}
                  selectedKey={selectedCollectionKey}
                  onSelect={handleSelectCollection}
                />
              ) : null}
            </div>
          )}
        </div>
      )}

      {/* Spacer when not on library route */}
      {!isLibraryRoute && <div className="flex-1" />}

      {/* Footer */}
      <div className="px-5 py-4 border-t border-border/30">
        <span className="text-[10px] text-muted uppercase tracking-wide">
          Vault
        </span>
        <span className="block text-xs text-text font-mono truncate mt-0.5">
          {vaultName || vaultPath || "Not connected"}
        </span>
      </div>
    </aside>
  );
}
