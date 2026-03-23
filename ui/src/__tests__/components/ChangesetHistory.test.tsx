import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { server } from "../handlers";
import { makeChangesetSummary, makeChangeset } from "../factories";
import { ChangesetHistory } from "../../components/ChangesetHistory";

describe("ChangesetHistory", () => {
  beforeEach(() => {
    // Default list response
    server.use(
      http.get("/changesets", () =>
        HttpResponse.json({
          changesets: [
            makeChangesetSummary({ id: "cs-1", status: "pending" }),
            makeChangesetSummary({
              id: "cs-2",
              status: "applied",
              created_at: "2024-01-02T00:00:00Z",
            }),
          ],
          total: 2,
        }),
      ),
    );
  });

  it("renders changeset list", async () => {
    render(<ChangesetHistory />);
    await waitFor(() => {
      expect(screen.getByText("Changeset History")).toBeDefined();
    });
    await waitFor(() => {
      expect(screen.getByTestId("delete-cs-1")).toBeDefined();
      expect(screen.getByTestId("delete-cs-2")).toBeDefined();
    });
  });

  it("shows status filter tabs", async () => {
    render(<ChangesetHistory />);
    await waitFor(() => {
      expect(screen.getByText("All")).toBeDefined();
      expect(screen.getByText("Pending")).toBeDefined();
      expect(screen.getByText("Applied")).toBeDefined();
      expect(screen.getByText("Rejected")).toBeDefined();
      expect(screen.getByText("Revision Requested")).toBeDefined();
    });
  });

  it("clicking a card opens detail view", async () => {
    server.use(
      http.get("/changesets/:id", () =>
        HttpResponse.json(makeChangeset({ id: "cs-1" })),
      ),
    );

    render(<ChangesetHistory />);

    await waitFor(() => {
      expect(screen.getByTestId("delete-cs-1")).toBeDefined();
    });

    // Click the first card
    const card = screen.getByTestId("delete-cs-1").closest("[role='button']");
    if (card) fireEvent.click(card);

    await waitFor(() => {
      expect(screen.getByText("Changeset Detail")).toBeDefined();
    });
  });

  it("shows empty state", async () => {
    server.use(
      http.get("/changesets", () =>
        HttpResponse.json({ changesets: [], total: 0 }),
      ),
    );

    render(<ChangesetHistory />);
    await waitFor(() => {
      expect(screen.getByText("No changesets found.")).toBeDefined();
    });
  });

  it("detail view shows annotation feedback for pending changesets", async () => {
    server.use(
      http.get("/changesets/:id", () =>
        HttpResponse.json(makeChangeset({ id: "cs-1", status: "pending" })),
      ),
    );

    render(<ChangesetHistory />);
    await waitFor(() => {
      expect(screen.getByTestId("delete-cs-1")).toBeDefined();
    });

    const card = screen.getByTestId("delete-cs-1").closest("[role='button']");
    if (card) fireEvent.click(card);

    await waitFor(() => {
      expect(screen.getByText("Annotate Selection")).toBeDefined();
    });
  });

  it("delete button triggers confirm popover and API call", async () => {
    let deleteCalled = false;
    server.use(
      http.delete("/changesets/:id", () => {
        deleteCalled = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );

    render(<ChangesetHistory />);
    await waitFor(() => {
      expect(screen.getByTestId("delete-cs-1")).toBeDefined();
    });

    fireEvent.click(screen.getByTestId("delete-cs-1"));
    expect(screen.getByTestId("delete-confirm-popover")).toBeDefined();

    fireEvent.click(screen.getByTestId("confirm-delete-btn"));
    await waitFor(() => {
      expect(deleteCalled).toBe(true);
    });
  });

  it("cancelled confirm does not call delete API", async () => {
    let deleteCalled = false;
    server.use(
      http.delete("/changesets/:id", () => {
        deleteCalled = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );

    render(<ChangesetHistory />);
    await waitFor(() => {
      expect(screen.getByTestId("delete-cs-1")).toBeDefined();
    });

    fireEvent.click(screen.getByTestId("delete-cs-1"));
    expect(screen.getByTestId("delete-confirm-popover")).toBeDefined();

    fireEvent.click(screen.getByText("Cancel"));
    expect(screen.queryByTestId("delete-confirm-popover")).toBeNull();
    expect(deleteCalled).toBe(false);
  });

  it("filter tabs change displayed results", async () => {
    let lastUrl = "";
    server.use(
      http.get("/changesets", ({ request }) => {
        lastUrl = request.url;
        const url = new URL(request.url);
        const status = url.searchParams.get("status");
        if (status === "applied") {
          return HttpResponse.json({
            changesets: [
              makeChangesetSummary({ id: "cs-applied", status: "applied" }),
            ],
            total: 1,
          });
        }
        return HttpResponse.json({
          changesets: [makeChangesetSummary()],
          total: 1,
        });
      }),
    );

    render(<ChangesetHistory />);
    await waitFor(() => {
      expect(screen.getByText("All")).toBeDefined();
    });

    fireEvent.click(screen.getByText("Applied"));
    await waitFor(() => {
      expect(lastUrl).toContain("status=applied");
    });
  });
});
