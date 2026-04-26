import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock next/navigation
const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
  useParams: () => ({}),
}));

// Mock fetch globally for PATCH calls
const fetchMock = vi.fn();
vi.stubGlobal("fetch", fetchMock);

// Mock @/lib/api
vi.mock("@/lib/api", () => ({
  api: {
    auth: { me: vi.fn() },
    applications: {
      list: vi.fn(),
      patch: vi.fn(),
    },
  },
}));

import { api } from "@/lib/api";
import TrackerPage from "@/app/tracker/page";

// ---------------------------------------------------------------------------
// Mock data: 2 applications — one SENT, one APPLIED
// ---------------------------------------------------------------------------

const MOCK_APPLICATIONS = [
  {
    id: "app-1",
    status: "SENT",
    job: {
      id: "job-1",
      title: "ML Engineer Intern",
      company: "AlphaCorp",
      location: "Remote",
    },
    created_at: "2025-01-01T00:00:00Z",
    updated_at: "2025-01-02T00:00:00Z",
  },
  {
    id: "app-2",
    status: "APPLIED",
    job: {
      id: "job-2",
      title: "Data Science Intern",
      company: "BetaCorp",
      location: "Lahore, PK",
    },
    created_at: "2025-01-01T00:00:00Z",
    updated_at: "2025-01-02T00:00:00Z",
  },
];

// ---------------------------------------------------------------------------
// Shared setup
// ---------------------------------------------------------------------------

describe("TrackerPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    pushMock.mockReset();

    (api.auth.me as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: "u1",
      email: "test@example.com",
    });
    (api.applications.list as ReturnType<typeof vi.fn>).mockResolvedValue(
      MOCK_APPLICATIONS
    );
    (api.applications.patch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ...MOCK_APPLICATIONS[0],
      status: "RESPONDED",
    });

    // Default fetch mock: successful PATCH
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ ...MOCK_APPLICATIONS[0], status: "RESPONDED" }),
      text: async () => JSON.stringify({ ...MOCK_APPLICATIONS[0], status: "RESPONDED" }),
    });
  });

  // -------------------------------------------------------------------------
  // Rendering
  // -------------------------------------------------------------------------

  it("renders the tracker page with application cards", async () => {
    render(<TrackerPage />);
    await waitFor(() => {
      expect(screen.getByText("ML Engineer Intern")).toBeInTheDocument();
      expect(screen.getByText("Data Science Intern")).toBeInTheDocument();
    });
  });

  it("renders SENT and APPLIED columns", async () => {
    render(<TrackerPage />);
    await waitFor(() => {
      // Column headings must be visible
      expect(screen.getByTestId("column-SENT")).toBeInTheDocument();
      expect(screen.getByTestId("column-APPLIED")).toBeInTheDocument();
    });
  });

  it("renders app-1 in SENT column", async () => {
    render(<TrackerPage />);
    await waitFor(() => {
      const sentColumn = screen.getByTestId("column-SENT");
      expect(sentColumn).toBeInTheDocument();
      // The SENT application card must be within the SENT column
      expect(sentColumn).toContainElement(
        screen.getByTestId("app-card-app-1")
      );
    });
  });

  it("renders app-2 in APPLIED column", async () => {
    render(<TrackerPage />);
    await waitFor(() => {
      const appliedColumn = screen.getByTestId("column-APPLIED");
      expect(appliedColumn).toContainElement(
        screen.getByTestId("app-card-app-2")
      );
    });
  });

  it("redirects to /login when auth fails", async () => {
    (api.auth.me as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error("401")
    );
    render(<TrackerPage />);
    await waitFor(() => {
      expect(pushMock).toHaveBeenCalledWith("/login");
    });
  });

  // -------------------------------------------------------------------------
  // Drag-drop: move SENT → RESPONDED fires PATCH
  // -------------------------------------------------------------------------

  it("drag from SENT column to RESPONDED column fires PATCH with correct status", async () => {
    render(<TrackerPage />);

    await waitFor(() => {
      expect(screen.getByTestId("app-card-app-1")).toBeInTheDocument();
    });

    const card = screen.getByTestId("app-card-app-1");
    const respondedColumn = screen.getByTestId("column-RESPONDED");

    // Simulate HTML5 drag-drop sequence
    await act(async () => {
      // dragstart on the card
      card.dispatchEvent(
        new DragEvent("dragstart", {
          bubbles: true,
          cancelable: true,
          dataTransfer: new DataTransfer(),
        })
      );
    });

    await act(async () => {
      // dragover on the RESPONDED column drop zone
      respondedColumn.dispatchEvent(
        new DragEvent("dragover", {
          bubbles: true,
          cancelable: true,
        })
      );
    });

    await act(async () => {
      // drop on the RESPONDED column
      respondedColumn.dispatchEvent(
        new DragEvent("drop", {
          bubbles: true,
          cancelable: true,
        })
      );
    });

    await waitFor(() => {
      expect(api.applications.patch).toHaveBeenCalledWith("app-1", {
        status: "RESPONDED",
      });
    });
  });

  it("PATCH fires with { status: 'RESPONDED' } after drag to RESPONDED column", async () => {
    render(<TrackerPage />);

    await waitFor(() =>
      expect(screen.getByTestId("app-card-app-1")).toBeInTheDocument()
    );

    const card = screen.getByTestId("app-card-app-1");
    const respondedColumn = screen.getByTestId("column-RESPONDED");

    await act(async () => {
      card.dispatchEvent(
        new DragEvent("dragstart", { bubbles: true, cancelable: true })
      );
      respondedColumn.dispatchEvent(
        new DragEvent("dragover", { bubbles: true, cancelable: true })
      );
      respondedColumn.dispatchEvent(
        new DragEvent("drop", { bubbles: true, cancelable: true })
      );
    });

    await waitFor(() => {
      const patchCalls = (api.applications.patch as ReturnType<typeof vi.fn>)
        .mock.calls;
      expect(patchCalls.length).toBeGreaterThanOrEqual(1);
      const lastCall = patchCalls[patchCalls.length - 1];
      expect(lastCall[0]).toBe("app-1");
      expect(lastCall[1]).toEqual({ status: "RESPONDED" });
    });
  });

  // -------------------------------------------------------------------------
  // Optimistic rollback: 409 → card reverts to original column
  // -------------------------------------------------------------------------

  it("reverts card to original column when PATCH returns 409", async () => {
    // Mock PATCH to return 409 conflict
    (api.applications.patch as ReturnType<typeof vi.fn>).mockRejectedValue(
      Object.assign(new Error("409: Conflict"), { status: 409 })
    );

    render(<TrackerPage />);

    await waitFor(() =>
      expect(screen.getByTestId("app-card-app-1")).toBeInTheDocument()
    );

    const card = screen.getByTestId("app-card-app-1");
    const respondedColumn = screen.getByTestId("column-RESPONDED");

    await act(async () => {
      card.dispatchEvent(
        new DragEvent("dragstart", { bubbles: true, cancelable: true })
      );
      respondedColumn.dispatchEvent(
        new DragEvent("dragover", { bubbles: true, cancelable: true })
      );
      respondedColumn.dispatchEvent(
        new DragEvent("drop", { bubbles: true, cancelable: true })
      );
    });

    // After PATCH fails, card must revert to SENT column
    await waitFor(() => {
      const sentColumn = screen.getByTestId("column-SENT");
      expect(sentColumn).toContainElement(screen.getByTestId("app-card-app-1"));
    });
  });

  it("does not move card to new column when PATCH returns 409", async () => {
    (api.applications.patch as ReturnType<typeof vi.fn>).mockRejectedValue(
      Object.assign(new Error("409: Conflict"), { status: 409 })
    );

    render(<TrackerPage />);

    await waitFor(() =>
      expect(screen.getByTestId("app-card-app-1")).toBeInTheDocument()
    );

    const card = screen.getByTestId("app-card-app-1");
    const respondedColumn = screen.getByTestId("column-RESPONDED");

    await act(async () => {
      card.dispatchEvent(
        new DragEvent("dragstart", { bubbles: true, cancelable: true })
      );
      respondedColumn.dispatchEvent(
        new DragEvent("dragover", { bubbles: true, cancelable: true })
      );
      respondedColumn.dispatchEvent(
        new DragEvent("drop", { bubbles: true, cancelable: true })
      );
    });

    // Card must NOT appear in the RESPONDED column after rollback
    await waitFor(async () => {
      // Give the optimistic update + rollback time to settle
      await new Promise((r) => setTimeout(r, 50));
      const respondedCol = screen.getByTestId("column-RESPONDED");
      const appCard = screen.queryByTestId("app-card-app-1");
      if (appCard) {
        expect(respondedCol).not.toContainElement(appCard);
      }
    });
  });

  // -------------------------------------------------------------------------
  // Column rendering: all status columns present
  // -------------------------------------------------------------------------

  it("renders all expected status columns", async () => {
    render(<TrackerPage />);
    await waitFor(() => {
      const expectedColumns = [
        "APPLIED",
        "SENT",
        "RESPONDED",
        "INTERVIEWING",
        "OFFERED",
        "REJECTED",
      ];
      for (const col of expectedColumns) {
        expect(screen.getByTestId(`column-${col}`)).toBeInTheDocument();
      }
    });
  });
});
