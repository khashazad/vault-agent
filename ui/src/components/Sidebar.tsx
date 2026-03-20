import { NavLink } from "react-router";

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
  return (
    <aside className="w-[248px] h-screen flex flex-col bg-surface border-r border-border shrink-0">
      {/* Branding */}
      <div className="px-5 pt-5 pb-4">
        <NavLink
          to="/connect"
          className="flex items-center gap-2.5 no-underline"
        >
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#cba6f7] to-[#89b4fa] flex items-center justify-center">
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="#11111b"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4" />
              <polyline points="10 17 15 12 10 7" />
              <line x1="15" x2="3" y1="12" y2="12" />
            </svg>
          </div>
          <span className="text-sm font-semibold text-text">Vault Agent</span>
        </NavLink>
      </div>

      {/* User section */}
      <div className="px-5 pb-4 flex items-center gap-2.5">
        <div className="w-7 h-7 rounded-full bg-elevated flex items-center justify-center text-[10px] font-medium text-muted">
          VA
        </div>
        <div className="flex flex-col">
          <span className="text-xs font-medium text-text leading-tight">
            Archivist Main
          </span>
          <span className="text-[10px] text-muted leading-tight">
            Source Vault
          </span>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 flex flex-col gap-0.5">
        {NAV_ITEMS.map(({ to, label, icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-2.5 px-3 h-10 rounded-lg text-sm no-underline transition-colors ${
                isActive
                  ? "bg-accent/15 text-accent font-medium border-l-2 border-accent -ml-0.5 pl-[10px]"
                  : "text-muted hover:text-text hover:bg-elevated/50"
              }`
            }
          >
            {icon}
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-border">
        <span className="text-[10px] text-muted uppercase tracking-wide">
          Vault
        </span>
        <span className="block text-xs text-text font-mono truncate mt-0.5">
          ~/vault
        </span>
      </div>
    </aside>
  );
}
