"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, type Job } from "@/lib/api";
import { JobCard } from "@/components/JobCard";

export default function InboxPage() {
  const router = useRouter();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.auth
      .me()
      .then(() => api.jobs.list())
      .then(setJobs)
      .catch(() => router.push("/login"))
      .finally(() => setLoading(false));
  }, [router]);

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-gray-500">Loading jobs…</p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-2xl p-6">
      <h1 className="mb-6 text-2xl font-bold">Inbox</h1>
      {jobs.length === 0 ? (
        <p className="text-sm text-gray-500">No jobs found. Run `discover` then `rank`.</p>
      ) : (
        <ul role="list" className="flex flex-col gap-3" aria-label="job list">
          {jobs.map((job) => (
            <li key={job.id}>
              <JobCard job={job} />
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
