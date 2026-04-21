"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { api, type Draft, type Job } from "@/lib/api";
import { DraftEditor } from "@/components/DraftEditor";
import { ApproveBar } from "@/components/ApproveBar";

export default function DraftPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const draftId = params.id;

  const [draft, setDraft] = useState<Draft | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [loading, setLoading] = useState(true);
  const [approved, setApproved] = useState(false);

  useEffect(() => {
    api.auth
      .me()
      .then(async () => {
        const d = await api.drafts.get(draftId);
        setDraft(d);
        const jobs = await api.jobs.list(50);
        // find job by application — fall back to first if not matched
        setJob(jobs[0] ?? null);
      })
      .catch(() => router.push("/login"))
      .finally(() => setLoading(false));
  }, [draftId, router]);

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-gray-500">Loading draft…</p>
      </main>
    );
  }

  if (!draft) return null;

  return (
    <main className="mx-auto max-w-6xl p-6">
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* left — job description */}
        <section aria-label="Job description" className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
          {job ? (
            <>
              <h2 className="mb-1 text-xl font-bold">{job.title}</h2>
              <p className="mb-4 text-sm text-gray-600">{job.company}</p>
              <a
                href={job.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-indigo-600 underline"
              >
                View original posting ↗
              </a>
            </>
          ) : (
            <p className="text-sm text-gray-500">Job details unavailable.</p>
          )}
        </section>

        {/* right — draft editor with 3 tabs */}
        <section aria-label="Draft editor" className="flex flex-col gap-4">
          {approved ? (
            <div className="rounded-xl border border-green-200 bg-green-50 p-6 text-center text-green-700 font-medium">
              Application approved ✓
            </div>
          ) : (
            <>
              <DraftEditor draft={draft} onSave={setDraft} />
              <ApproveBar
                draftId={draft.id}
                onApproved={() => setApproved(true)}
                onRejected={() => router.push("/inbox")}
              />
            </>
          )}
        </section>
      </div>
    </main>
  );
}
