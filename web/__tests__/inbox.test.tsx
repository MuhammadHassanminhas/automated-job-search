import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock next/navigation
const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
  useParams: () => ({}),
}));

// Mock api
vi.mock("@/lib/api", () => ({
  api: {
    auth: { me: vi.fn() },
    jobs: { list: vi.fn() },
  },
}));

import { api } from "@/lib/api";
import InboxPage from "@/app/inbox/page";

const MOCK_JOBS = [
  {
    id: "job-1",
    title: "ML Engineer Intern",
    company: "AlphaCorp",
    location: "Remote",
    remote_allowed: true,
    url: "https://example.com/job/1",
    keyword_score: 0.8,
    embedding_score: 0.95,
    posted_at: null,
  },
  {
    id: "job-2",
    title: "Data Science Intern",
    company: "BetaCorp",
    location: "Lahore, PK",
    remote_allowed: false,
    url: "https://example.com/job/2",
    keyword_score: 0.6,
    embedding_score: 0.72,
    posted_at: null,
  },
];

describe("InboxPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (api.auth.me as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: "u1",
      email: "test@example.com",
    });
    (api.jobs.list as ReturnType<typeof vi.fn>).mockResolvedValue(MOCK_JOBS);
  });

  it("renders job list from mocked API", async () => {
    render(<InboxPage />);
    await waitFor(() => {
      expect(screen.getByText("ML Engineer Intern")).toBeInTheDocument();
      expect(screen.getByText("Data Science Intern")).toBeInTheDocument();
    });
    expect(screen.getAllByTestId("job-card")).toHaveLength(2);
  });

  it("renders company names for each job", async () => {
    render(<InboxPage />);
    await waitFor(() => {
      expect(screen.getByText("AlphaCorp")).toBeInTheDocument();
      expect(screen.getByText("BetaCorp")).toBeInTheDocument();
    });
  });

  it("redirects to /login when auth fails", async () => {
    (api.auth.me as ReturnType<typeof vi.fn>).mockRejectedValue(new Error("401"));
    render(<InboxPage />);
    await waitFor(() => {
      expect(pushMock).toHaveBeenCalledWith("/login");
    });
  });

  it("shows empty state when no jobs returned", async () => {
    (api.jobs.list as ReturnType<typeof vi.fn>).mockResolvedValue([]);
    render(<InboxPage />);
    await waitFor(() => {
      expect(screen.getByText(/no jobs found/i)).toBeInTheDocument();
    });
  });

  it("renders the inbox heading", async () => {
    render(<InboxPage />);
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /inbox/i })).toBeInTheDocument();
    });
  });
});
