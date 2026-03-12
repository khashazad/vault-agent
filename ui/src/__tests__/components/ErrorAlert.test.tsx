import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ErrorAlert } from "../../components/ErrorAlert";

describe("ErrorAlert", () => {
  it("renders the error message", () => {
    render(<ErrorAlert message="Something went wrong" />);
    expect(screen.getByText(/Something went wrong/)).toBeInTheDocument();
  });

  it("renders the Error label", () => {
    render(<ErrorAlert message="test" />);
    expect(screen.getByText("Error:")).toBeInTheDocument();
  });
});
