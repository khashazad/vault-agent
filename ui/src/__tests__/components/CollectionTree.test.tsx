import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CollectionTree } from "../../components/CollectionTree";
import { makeCollection } from "../factories";

describe("CollectionTree", () => {
  const collections = [
    makeCollection({ key: "ROOT1", name: "Physics", parent_collection: null, num_items: 10 }),
    makeCollection({ key: "CHILD1", name: "Quantum", parent_collection: "ROOT1", num_items: 3 }),
    makeCollection({ key: "ROOT2", name: "Biology", parent_collection: null, num_items: 7 }),
  ];

  it("renders My Library root", () => {
    render(
      <CollectionTree collections={collections} selectedKey={null} onSelect={() => {}} />
    );
    expect(screen.getByText("My Library")).toBeInTheDocument();
  });

  it("renders top-level collections", () => {
    render(
      <CollectionTree collections={collections} selectedKey={null} onSelect={() => {}} />
    );
    expect(screen.getByText("Physics")).toBeInTheDocument();
    expect(screen.getByText("Biology")).toBeInTheDocument();
  });

  it("hides children by default", () => {
    render(
      <CollectionTree collections={collections} selectedKey={null} onSelect={() => {}} />
    );
    // Quantum is a child of Physics, should be hidden initially
    expect(screen.queryByText("Quantum")).not.toBeInTheDocument();
  });

  it("calls onSelect with null when My Library clicked", async () => {
    const onSelect = vi.fn();
    render(
      <CollectionTree collections={collections} selectedKey="ROOT1" onSelect={onSelect} />
    );
    await userEvent.click(screen.getByText("My Library"));
    expect(onSelect).toHaveBeenCalledWith(null);
  });

  it("calls onSelect with collection key when clicked", async () => {
    const onSelect = vi.fn();
    render(
      <CollectionTree collections={collections} selectedKey={null} onSelect={onSelect} />
    );
    await userEvent.click(screen.getByText("Biology"));
    expect(onSelect).toHaveBeenCalledWith("ROOT2");
  });
});
