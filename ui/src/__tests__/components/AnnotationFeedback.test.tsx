import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { AnnotationFeedback, formatAnnotations } from "../../components/AnnotationFeedback";
import { makePassageAnnotation } from "../factories";

describe("AnnotationFeedback", () => {
  const defaultProps = {
    annotations: [],
    onAdd: vi.fn(),
    onRemove: vi.fn(),
    onSubmit: vi.fn(),
    submitting: false,
  };

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders empty state with annotate button", () => {
    render(<AnnotationFeedback {...defaultProps} />);
    expect(screen.getByText("Annotate Selection")).toBeDefined();
    expect(screen.getByRole("button", { name: /Request Changes/ })).toBeDefined();
  });

  it("shows hint when clicking annotate with no selection", () => {
    vi.spyOn(window, "getSelection").mockReturnValue({
      toString: () => "",
    } as Selection);

    render(<AnnotationFeedback {...defaultProps} />);
    fireEvent.click(screen.getByText("Annotate Selection"));
    expect(screen.getByText("Select text in the preview first")).toBeDefined();
  });

  it("captures selection and shows comment input", () => {
    vi.spyOn(window, "getSelection").mockReturnValue({
      toString: () => "some selected text",
    } as Selection);

    render(<AnnotationFeedback {...defaultProps} />);
    fireEvent.click(screen.getByText("Annotate Selection"));

    expect(screen.getByText(/some selected text/)).toBeDefined();
    expect(screen.getByPlaceholderText("What should change?")).toBeDefined();
  });

  it("calls onAdd when clicking Add with comment", () => {
    const onAdd = vi.fn();
    vi.spyOn(window, "getSelection").mockReturnValue({
      toString: () => "passage text",
    } as Selection);

    // Mock crypto.randomUUID
    vi.spyOn(crypto, "randomUUID").mockReturnValue("test-uuid" as `${string}-${string}-${string}-${string}-${string}`);

    render(<AnnotationFeedback {...defaultProps} onAdd={onAdd} />);
    fireEvent.click(screen.getByText("Annotate Selection"));
    fireEvent.change(screen.getByPlaceholderText("What should change?"), {
      target: { value: "fix this" },
    });
    fireEvent.click(screen.getByText("Add"));

    expect(onAdd).toHaveBeenCalledWith({
      id: "test-uuid",
      selectedText: "passage text",
      comment: "fix this",
    });
  });

  it("renders annotations with remove buttons", () => {
    const onRemove = vi.fn();
    const annotations = [
      makePassageAnnotation({ id: "a1", selectedText: "first passage", comment: "fix A" }),
      makePassageAnnotation({ id: "a2", selectedText: "second passage", comment: "fix B" }),
    ];

    render(
      <AnnotationFeedback {...defaultProps} annotations={annotations} onRemove={onRemove} />,
    );

    expect(screen.getByText(/first passage/)).toBeDefined();
    expect(screen.getByText("fix A")).toBeDefined();
    expect(screen.getByText(/second passage/)).toBeDefined();
    expect(screen.getByText("fix B")).toBeDefined();

    // Remove buttons
    const removeButtons = screen.getAllByTitle("Remove");
    expect(removeButtons).toHaveLength(2);
    fireEvent.click(removeButtons[0]);
    expect(onRemove).toHaveBeenCalledWith("a1");
  });

  it("submit button shows annotation count", () => {
    const annotations = [makePassageAnnotation(), makePassageAnnotation({ id: "a2" })];
    render(<AnnotationFeedback {...defaultProps} annotations={annotations} />);
    expect(screen.getByText("Request Changes (2)")).toBeDefined();
  });

  it("submit button is disabled when no annotations", () => {
    render(<AnnotationFeedback {...defaultProps} />);
    const btn = screen.getByRole("button", { name: /Request Changes/ });
    expect(btn.hasAttribute("disabled")).toBe(true);
  });

  it("submit button is disabled when submitting", () => {
    render(
      <AnnotationFeedback
        {...defaultProps}
        annotations={[makePassageAnnotation()]}
        submitting={true}
      />,
    );
    expect(screen.getByText("Submitting...")).toBeDefined();
  });

  it("calls onSubmit when clicking request changes", () => {
    const onSubmit = vi.fn();
    render(
      <AnnotationFeedback
        {...defaultProps}
        annotations={[makePassageAnnotation()]}
        onSubmit={onSubmit}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Request Changes/ }));
    expect(onSubmit).toHaveBeenCalledOnce();
  });
});

describe("formatAnnotations", () => {
  it("formats single annotation", () => {
    const result = formatAnnotations([
      makePassageAnnotation({ selectedText: "hello world", comment: "change this" }),
    ]);
    expect(result).toBe('[Passage: "hello world"]\nFeedback: change this');
  });

  it("formats multiple annotations", () => {
    const result = formatAnnotations([
      makePassageAnnotation({ selectedText: "first", comment: "fix A" }),
      makePassageAnnotation({ selectedText: "second", comment: "fix B" }),
    ]);
    expect(result).toBe(
      '[Passage: "first"]\nFeedback: fix A\n\n[Passage: "second"]\nFeedback: fix B',
    );
  });

  it("returns empty string for no annotations", () => {
    expect(formatAnnotations([])).toBe("");
  });
});
