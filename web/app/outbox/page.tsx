"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, type DraftWithJob } from "@/lib/api";
import { DraftCard } from "@/components/DraftCard";

export default function OutboxPage() {
  const router = useRouter();
  const [drafts, setDrafts] = useState<DraftWithJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [approving, setApproving] = useState<string | null>(null);

  useEffect(() => {
    api.auth
      .me()
      .then(() => api.drafts.list("PENDING"))
      .then(setDrafts)
      .catch(() => router.push("/login"))
      .finally(() => setLoading(false));
  }, [router]);

  async function handleApprove(draftId: string) {
    const index = drafts.findIndex((d) => d.id === draftId);
    if (index === -1) return;
    setApproving(draftId);
    const snapshot = [...drafts];
    setDrafts((ds) => ds.filter((d) => d.id !== draftId));
    try {
      await api.drafts.approve(draftId);
    } catch {
      setDrafts(snapshot);
    } finally {
      setApproving(null);
    }
  }

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-gray-500">Loading…</p>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-gray-50">
      <div className="mx-auto max-w-3xl px-4 py-8">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-xl font-semibold text-gray-900">Outbox</h1>
          <button
            onClick={() => api.auth.logout().then(() => router.push("/login"))}
            className="text-sm text-gray-500 hover:text-gray-700"
          >
            Sign out
          </button>
        </div>
        {drafts.length === 0 ? (
          <p className="text-center text-sm text-gray-400">No pending drafts.</p>
        ) : (
          <ul className="space-y-3" aria-label="draft list">
            {drafts.map((draft) => (
              <DraftCard
                key={draft.id}
                draft={draft}
                onApprove={() => handleApprove(draft.id)}
                approving={approving === draft.id}
              />
            ))}
          </ul>
        )}
      </div>
    </main>
  );
}
