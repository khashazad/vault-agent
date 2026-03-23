# Settings Page Design Spec

## Overview

Obsidian-style settings page accessible via a gear icon in the sidebar footer. Initially contains only Clawdy Inbox settings (copy vault path, polling toggle, interval). Replaces the inline config controls on ClawdyInboxPage.

## Routing & Navigation

- Route: `/settings` → `SettingsPage`
- Gear icon in sidebar footer (above vault name display), navigates to `/settings`
- Route added to Layout children in `router.tsx`

## SettingsPage Layout

Two-panel layout rendered inside the page content area:

**Left panel (~200px fixed):**
- Section list with active item highlight (purple left border, matching app sidebar style)
- Initially one section: "Clawdy Inbox"
- Extensible — adding sections later requires only a new entry and component

**Right panel (flex-1, scrollable):**
- Renders the active section's settings
- Section heading at top
- Settings listed vertically with label, optional description, and control

## Clawdy Inbox Settings Section

Three settings, each saves immediately on change (no Save button).

**Loading state:** On mount, fetch `fetchClawdyConfig()`. Show a skeleton in the right panel while loading. On error, show `ErrorAlert` at the top of the right panel. Each auto-save call shows an inline `ErrorAlert` on failure (same pattern as ClawdyInboxPage).

### Copy Vault Path
- Label: "Copy Vault Path"
- Display: monospace path string, or "Not configured" when null
- Control: "Browse" button
- Action: `openVaultPicker()` → on success, `updateClawdyConfig({ copy_vault_path: path })`. Do NOT call `setVault()` — that sets the main vault, not the copy vault.
- Validation: backend `PUT /clawdy/config` validates directory exists + is git repo

### Enable Polling
- Label: "Enable polling"
- Description: "Periodically check the copy vault for changes"
- Control: toggle switch
- Action: `updateClawdyConfig({ enabled: !current })`

### Poll Interval
- Label: "Poll interval"
- Description: "How often to check for changes"
- Control: `<select>` dropdown with options: 1 min (60), 5 min (300), 15 min (900), 30 min (1800)
- Action: `updateClawdyConfig({ interval: value })`

## ClawdyInboxPage Changes

Remove the config/status bar (ConfigSkeleton, toggle, interval dropdown, `INTERVAL_OPTIONS`). Replace with a single horizontal row status line (`flex items-center gap-4`):

- Enabled/disabled text indicator
- Last poll timestamp (if available)
- Pending changeset count badge
- "Check Now" button (action stays here, not in settings)
- Error display (last_error from status)

The changeset list and pagination remain unchanged. The `INTERVAL_OPTIONS` constant moves to `SettingsPage.tsx` (only used there).

## Sidebar Changes

Add gear icon as its own row above the existing footer vault-name block, inside a new `<div>` with `px-5 py-2` that sits between the spacer and the vault footer. The gear icon is a `NavLink` to `/settings` — NOT added to the `NAV_ITEMS` array. Styled with muted color, purple on active/hover matching nav items.

```
{/* Gear icon — above vault footer */}
<div className="px-5 py-2">
  <NavLink to="/settings">
    <svg gear icon />
  </NavLink>
</div>

{/* Vault footer (existing) */}
<div className="px-5 py-4 border-t border-border/30">
  ...
</div>
```

## Backend Changes

None required. Existing endpoints cover all needs:
- `POST /vault/picker` — native file dialog
- `PUT /clawdy/config` — save config with validation
- `GET /clawdy/config` — read config
- `GET /clawdy/status` — read status

## Files Modified/Created

- Create: `ui/src/pages/SettingsPage.tsx`
- Modify: `ui/src/router.tsx` — add `/settings` route
- Modify: `ui/src/components/Sidebar.tsx` — add gear icon in footer
- Modify: `ui/src/pages/ClawdyInboxPage.tsx` — replace config bar with status line

## Out of Scope

- General settings section (vault path management)
- Zotero/Anthropic key configuration
- Settings search
- Settings persistence beyond what SettingsStore already provides
