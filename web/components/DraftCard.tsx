"use client";
import type { DraftWithJob } from "@/lib/api";

interface Props {
  draft: DraftWithJob;
  onApprove: () => void;
  approving: boolean;
}

export function DraftCard({ draft, onApprove, approving }: Props) {
  return (
    <li
      data-testid="draft-card"
      className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h3 className="truncate font-medium text-gray-900">{draft.job_title}</h3>
          <p className="text-sm text-gray-500">{draft.company}</p>
          {draft.email_subject && (
            <p className="mt-1 truncate text-xs text-gray-400">{draft.email_subject}</p>
          )}
        </div>
        <button
          onClick={onApprove}
          disabled={approving}
          className="shrink-0 rounded bg-green-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
        >
          {approving ? "Approving…" : "Approve"}
        </button>
      </div>
    </li>
  );
}
