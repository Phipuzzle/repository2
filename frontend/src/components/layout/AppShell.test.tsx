import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AppShell } from "./AppShell";

describe("AppShell", () => {
  it("renders the foundation workspace", () => {
    render(<AppShell />);
    expect(screen.getByText("Intelligent Data Agent")).toBeInTheDocument();
    expect(screen.getByText("查询历史")).toBeInTheDocument();
    expect(screen.getByText("数据分析工作区")).toBeInTheDocument();
    expect(screen.getByRole("textbox")).toBeInTheDocument();
  });
});
