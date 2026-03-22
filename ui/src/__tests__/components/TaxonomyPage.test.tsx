import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { describe, it, expect } from "vitest";
import { TaxonomyPage } from "../../pages/TaxonomyPage";
import { server } from "../handlers";
import { http, HttpResponse } from "msw";

function renderPage() {
  return render(
    <MemoryRouter>
      <TaxonomyPage />
    </MemoryRouter>,
  );
}

describe("TaxonomyPage", () => {
  it("shows loading then renders taxonomy data", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/142/)).toBeInTheDocument();
    });
  });

  it("renders tag hierarchy on default tab", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("research")).toBeInTheDocument();
      expect(screen.getByText("daily")).toBeInTheDocument();
      expect(screen.getByText("paper")).toBeInTheDocument();
    });
  });

  it("switches to folders tab", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("research")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /folders/i }));
    await waitFor(() => {
      expect(screen.getByText("Papers")).toBeInTheDocument();
      expect(screen.getByText("Topics")).toBeInTheDocument();
    });
  });

  it("switches to link targets tab", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("research")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /link targets/i }));
    await waitFor(() => {
      expect(screen.getByText("Machine Learning")).toBeInTheDocument();
    });
  });

  it("shows error on API failure", async () => {
    server.use(
      http.get("/vault/taxonomy", () =>
        HttpResponse.json({ detail: "No vault configured" }, { status: 400 }),
      ),
    );
    renderPage();
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
  });

  it("filters tags by search", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("research")).toBeInTheDocument();
    });

    const search = screen.getByPlaceholderText(/filter/i);
    await user.type(search, "daily");
    expect(screen.getByText("daily")).toBeInTheDocument();
    expect(screen.queryByText("research")).not.toBeInTheDocument();
  });

  it("shows vault stats in sidebar card", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("142")).toBeInTheDocument();
      expect(screen.getByText("5")).toBeInTheDocument();
      expect(screen.getByText("4")).toBeInTheDocument();
      expect(screen.getByText("2")).toBeInTheDocument();
    });
  });

  it("shows context menu on right-click of tag", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("research")).toBeInTheDocument();
    });

    const tagEl = screen.getByText("research");
    fireEvent.contextMenu(tagEl);
    await waitFor(() => {
      expect(screen.getByText("Rename Tag")).toBeInTheDocument();
      expect(screen.getByText("Merge Tags")).toBeInTheDocument();
      expect(screen.getByText("Delete Tag")).toBeInTheDocument();
    });
  });
});
