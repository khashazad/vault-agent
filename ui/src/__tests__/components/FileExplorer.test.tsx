import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { FileExplorer } from "../../components/FileExplorer";
import { makeProposedChange } from "../factories";

describe("FileExplorer", () => {
  const changes = [
    makeProposedChange({
      id: "c1",
      tool_name: "replace_note",
      input: { path: "notes/papers/file1.md", content: "# file1" },
      status: "pending",
    }),
    makeProposedChange({
      id: "c2",
      tool_name: "create_note",
      input: { path: "notes/papers/file2.md", content: "# file2" },
      status: "approved",
    }),
    makeProposedChange({
      id: "c3",
      tool_name: "delete_note",
      input: { path: "notes/daily/log.md" },
      proposed_content: "",
      status: "rejected",
    }),
  ];

  it("renders nested folders and files", () => {
    render(
      <FileExplorer changes={changes} selectedId={null} onSelect={vi.fn()} />,
    );

    expect(screen.getByText("notes")).toBeInTheDocument();
    expect(screen.getByText("papers")).toBeInTheDocument();
    expect(screen.getByText("daily")).toBeInTheDocument();
    expect(screen.getByText("file1.md")).toBeInTheDocument();
  });

  it("shows change badges", () => {
    render(
      <FileExplorer changes={changes} selectedId={null} onSelect={vi.fn()} />,
    );

    expect(screen.getByText("MOD")).toBeInTheDocument();
    expect(screen.getByText("NEW")).toBeInTheDocument();
    expect(screen.getByText("DEL")).toBeInTheDocument();
  });

  it("calls onSelect with the change id", () => {
    const onSelect = vi.fn();
    render(
      <FileExplorer changes={changes} selectedId={null} onSelect={onSelect} />,
    );

    fireEvent.click(screen.getByText("file1.md"));

    expect(onSelect).toHaveBeenCalledWith("c1");
  });

  it("highlights the selected row", () => {
    render(
      <FileExplorer changes={changes} selectedId="c1" onSelect={vi.fn()} />,
    );

    expect(screen.getByTestId("file-row-c1")).toHaveClass("border-accent");
  });

  it("shows review counts in the header", () => {
    render(
      <FileExplorer changes={changes} selectedId={null} onSelect={vi.fn()} />,
    );

    expect(screen.getByText(/1 to review \/ 2 reviewed/)).toBeInTheDocument();
  });

  it("collapses folders", () => {
    render(
      <FileExplorer changes={changes} selectedId={null} onSelect={vi.fn()} />,
    );

    fireEvent.click(screen.getByText("papers"));

    expect(screen.queryByText("file1.md")).not.toBeInTheDocument();
  });

  it("shows review icons on reviewed files", () => {
    render(
      <FileExplorer changes={changes} selectedId={null} onSelect={vi.fn()} />,
    );

    expect(screen.getByTestId("file-row-c2").textContent).toContain("✓");
    expect(screen.getByTestId("file-row-c3").textContent).toContain("✗");
  });
});
