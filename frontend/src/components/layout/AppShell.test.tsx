import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AppShell } from "./AppShell";

vi.mock("../../features/query-run/api", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("../../features/query-run/api")>();
  return {
    ...actual,
    listQueryRuns: vi.fn(async () => ({
      items: [],
      total: 0,
      limit: 20,
      offset: 0,
    })),
    getMetrics: vi.fn(async () => []),
  };
});

describe("AppShell", () => {
  it("renders the foundation workspace and opens history on demand", () => {
    render(<AppShell />);
    expect(screen.getByText("Intelligent Data Agent")).toBeInTheDocument();
    expect(screen.getByText("数据分析工作区")).toBeInTheDocument();
    expect(screen.getByRole("textbox")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /历史/ }));
    expect(screen.getByRole("complementary", { name: "查询历史" })).toBeInTheDocument();
  });
});
