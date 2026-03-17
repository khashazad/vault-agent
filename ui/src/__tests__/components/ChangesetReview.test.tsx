import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ChangesetReview } from "../../components/ChangesetReview";
import { makeProposedChange } from "../factories";

describe("ChangesetReview", () => {
  const baseProps = {
    changesetId: "cs-1",
    onDone: vi.fn(),
  };

  it("hides Diff tab for create_note changes", () => {
    const change = makeProposedChange({ tool_name: "create_note" });
    render(<ChangesetReview {...baseProps} initialChanges={[change]} />);

    expect(screen.queryByRole("button", { name: "Diff" })).toBeNull();
    expect(screen.getByRole("button", { name: "Preview" })).toBeDefined();
  });

  it("shows Diff tab for update_note changes", () => {
    const change = makeProposedChange({
      tool_name: "update_note",
      original_content: "# Existing\n\nOld content.",
      diff: "--- a/Papers/Test.md\n+++ b/Papers/Test.md\n@@ -1,3 +1,3 @@\n # Existing\n \n-Old content.\n+New content.\n",
    });
    render(<ChangesetReview {...baseProps} initialChanges={[change]} />);

    expect(screen.getByRole("button", { name: "Diff" })).toBeDefined();
    expect(screen.getByRole("button", { name: "Preview" })).toBeDefined();
  });

  it("defaults create_note to preview mode", () => {
    const change = makeProposedChange({
      tool_name: "create_note",
      proposed_content: "# Test\n\nUnique preview content here.",
    });
    render(<ChangesetReview {...baseProps} initialChanges={[change]} />);

    // Preview content should be rendered (via MarkdownPreview)
    expect(screen.getByText("Unique preview content here.")).toBeDefined();
  });
});
