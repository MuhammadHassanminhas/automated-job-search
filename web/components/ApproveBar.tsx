"use client";

import { useState } from "react";
import { api } from "@/lib/api";

interface Props {
  draftId: string;
  onApproved?: () => void;
  onRejected?: () => void;
}

export function ApproveBar({ draftId, onApproved, onRejected }: Props) {
  const [status, setStatus] = useState<"idle" | "approving" | "rejecting">("idle");

  async function handleApprove() {
    setStatus("approving");
    try {
      await api.drafts.approve(draftId);
      onApproved?.();
    } finally {
      setStatus("idle");
    }
  }

  async function handleReject() {
    setStatus("rejecting");
    try {
      await api.drafts.reject(draftId);
      onRejected?.();
    } finally {
      setStatus("idle");
    }
  }

  return (
    <div
      className="flex items-center gap-3 rounded-lg border border-gray-200 bg-white p-3 shadow-sm"
      data-testid="approve-bar"
    >
      <button
        onClick={handleApprove}
        disabled={status !== "idle"}
        aria-label="Approve application"
        className="rounded-md bg-green-600 px-5 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
      >
        {status === "approving" ? "Approving…" : "Approve"}
      </button>
      <button
        onClick={handleReject}
        disabled={status !== "idle"}
        aria-label="Reject application"
        className="rounded-md bg-red-500 px-5 py-2 text-sm font-medium text-white hover:bg-red-600 disabled:opacity-50"
      >
        {status === "rejecting" ? "Rejecting…" : "Reject"}
      </button>
    </div>
  );
}
