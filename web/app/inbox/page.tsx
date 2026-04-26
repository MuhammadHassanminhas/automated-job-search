"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, type Job } from "@/lib/api";
import { logout } from "@/lib/auth";
import { JobCard } from "@/components/JobCard";

export default function InboxPage() {
  const router = useRouter();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState<string | null>(null);
  const [generateError, setGenerateError] = useState<string | null>(null);

  useEffect(() => {
    api.auth
      .me()
      .then(() => api.jobs.list())
      .then(setJobs)
      .catch(() => router.push("/login"))
      .finally(() => setLoading(false));
  }, [router]);

  async function handleGenerate(jobId: string) {
    setGenerating(jobId);
    setGenerateError(null);
    try {
      const draft = await api.drafts.generate(jobId);
      router.push(`/draft/${draft.id}`);
    } catch (err) {
      setGenerateError(err instanceof Error ? err.message : "Failed to generate draft");
      setGenerating(null);
    }
  }

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-gray-500">Loading jobs…</p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-2xl p-6">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Inbox</h1>
        <button
          onClick={() => logout(router)}
          className="rounded-md border border-gray-200 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-50"
        >
          Sign out
        </button>
      </div>
      {generating && (
        <p className="mb-4 text-sm text-indigo-600">Generating draft… (this may take 10–20 s)</p>
      )}
      {generateError && (
        <p className="mb-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{generateError}</p>
      )}
      {jobs.length === 0 ? (
        <p className="text-sm text-gray-500">No jobs found. Run `discover` then `rank`.</p>
      ) : (
        <ul role="list" className="flex flex-col gap-3" aria-label="job list">
          {jobs.map((job) => (
            <li key={job.id}>
              <JobCard
                job={job}
                onClick={generating ? undefined : () => handleGenerate(job.id)}
              />
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
