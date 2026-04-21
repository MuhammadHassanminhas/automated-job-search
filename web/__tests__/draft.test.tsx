import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";

const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
  useParams: () => ({ id: "draft-abc" }),
}));

vi.mock("@/lib/api", () => ({
  api: {
    auth: { me: vi.fn() },
    drafts: {
      get: vi.fn(),
      patch: vi.fn(),
      approve: vi.fn(),
      reject: vi.fn(),
    },
    jobs: { list: vi.fn() },
  },
}));

import { api } from "@/lib/api";
import DraftPage from "@/app/draft/[id]/page";

const MOCK_DRAFT = {
  id: "draft-abc",
  application_id: "app-123",
  resume_md: "# My Resume",
  cover_letter_md: "Dear Hiring Team,",
  email_subject: "Internship Inquiry",
  email_body: "Hello, I am interested.",
  model_used: "mixtral",
  prompt_version: "v1",
};

const MOCK_JOB = {
  id: "job-1",
  title: "ML Engineer Intern",
  company: "AlphaCorp",
  location: "Remote",
  remote_allowed: true,
  url: "https://example.com/job/1",
  keyword_score: 0.8,
  embedding_score: 0.95,
  posted_at: null,
};

describe("DraftPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (api.auth.me as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: "u1",
      email: "test@example.com",
    });
    (api.drafts.get as ReturnType<typeof vi.fn>).mockResolvedValue(MOCK_DRAFT);
    (api.jobs.list as ReturnType<typeof vi.fn>).mockResolvedValue([MOCK_JOB]);
    (api.drafts.patch as ReturnType<typeof vi.fn>).mockResolvedValue(MOCK_DRAFT);
    (api.drafts.approve as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: "app-123",
      status: "APPROVED",
    });
    (api.drafts.reject as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: "app-123",
      status: "WITHDRAWN",
    });
  });

  it("shows job description on the left", async () => {
    render(<DraftPage />);
    await waitFor(() => {
      expect(screen.getByText("ML Engineer Intern")).toBeInTheDocument();
      expect(screen.getByText("AlphaCorp")).toBeInTheDocument();
    });
  });

  it("renders draft editor with 3 tabs on the right", async () => {
    render(<DraftPage />);
    await waitFor(() => {
      expect(screen.getByRole("tab", { name: /resume/i })).toBeInTheDocument();
      expect(screen.getByRole("tab", { name: /cover letter/i })).toBeInTheDocument();
      expect(screen.getByRole("tab", { name: /email/i })).toBeInTheDocument();
    });
  });

  it("Approve button calls api.drafts.approve", async () => {
    const user = userEvent.setup();
    render(<DraftPage />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /approve/i })).toBeInTheDocument()
    );
    await user.click(screen.getByRole("button", { name: /approve application/i }));
    await waitFor(() => {
      expect(api.drafts.approve).toHaveBeenCalledWith("draft-abc");
    });
  });

  it("Reject button calls api.drafts.reject and redirects to inbox", async () => {
    const user = userEvent.setup();
    render(<DraftPage />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /reject application/i })).toBeInTheDocument()
    );
    await user.click(screen.getByRole("button", { name: /reject application/i }));
    await waitFor(() => {
      expect(api.drafts.reject).toHaveBeenCalledWith("draft-abc");
      expect(pushMock).toHaveBeenCalledWith("/inbox");
    });
  });

  it("shows approved state after approve", async () => {
    const user = userEvent.setup();
    render(<DraftPage />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /approve application/i })).toBeInTheDocument()
    );
    await user.click(screen.getByRole("button", { name: /approve application/i }));
    await waitFor(() => {
      expect(screen.getByText(/application approved/i)).toBeInTheDocument();
    });
  });
});
