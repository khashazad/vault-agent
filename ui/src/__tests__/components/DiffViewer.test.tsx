import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DiffViewer } from "../../components/DiffViewer";

describe("DiffViewer", () => {
  it("renders NEW FILE badge for new files", () => {
    render(
      <DiffViewer
        diff=""
        filePath="Papers/Test.md"
        isNew={true}
        proposedContent="# Test\n\nContent."
      />,
    );
    expect(screen.getByText("NEW FILE")).toBeInTheDocument();
  });

  it("renders MODIFY badge for existing files", () => {
    render(
      <DiffViewer
        diff=""
        filePath="Papers/Test.md"
        isNew={false}
        originalContent="# Old"
        proposedContent="# New"
      />,
    );
    expect(screen.getByText("MODIFY")).toBeInTheDocument();
  });

  it("renders file path", () => {
    render(
      <DiffViewer
        diff=""
        filePath="Papers/Test.md"
        isNew={true}
        proposedContent="# Test"
      />,
    );
    expect(screen.getByText("Papers/Test.md")).toBeInTheDocument();
  });

  it("shows No changes when content is empty", () => {
    render(<DiffViewer diff="" filePath="test.md" isNew={false} />);
    expect(screen.getByText("No changes")).toBeInTheDocument();
  });

  it("shows addition count for new files", () => {
    render(
      <DiffViewer
        diff=""
        filePath="test.md"
        isNew={true}
        proposedContent="Line 1\nLine 2\nLine 3"
      />,
    );
    // React renders "+" and count as separate text nodes
    const spans = document.querySelectorAll(".text-green");
    const text = Array.from(spans)
      .map((s) => s.textContent)
      .join("");
    expect(text).toContain("+");
  });
});
