"use client";

import { useRouter } from "next/navigation";
import type { Job } from "@/lib/api";

interface Props {
  job: Job;
  draftId?: string;
}

export function JobCard({ job, draftId }: Props) {
  const router = useRouter();

  const score =
    job.embedding_score !== null
      ? (job.embedding_score * 100).toFixed(0) + "%"
      : "—";

  function handleClick() {
    if (draftId) {
      router.push(`/draft/${draftId}`);
    }
  }

  return (
    <div
      role="listitem"
      onClick={handleClick}
      className="cursor-pointer rounded-lg border border-gray-200 bg-white p-4 shadow-sm hover:shadow-md transition-shadow"
      data-testid="job-card"
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="font-semibold text-gray-900">{job.title}</h3>
          <p className="text-sm text-gray-600">{job.company}</p>
          {job.location && (
            <p className="text-xs text-gray-400 mt-1">
              {job.location} {job.remote_allowed && "· Remote"}
            </p>
          )}
        </div>
        <span className="shrink-0 rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-medium text-indigo-700">
          {score}
        </span>
      </div>
    </div>
  );
}
