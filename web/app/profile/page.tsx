"use client";
import { useEffect, useState } from "react";

interface SourceRate {
  source: string;
  sent_count: number;
  responded_count: number;
  response_rate: number | null;
}

interface PromptRate {
  prompt_version: string | null;
  sent_count: number;
  responded_count: number;
  response_rate: number | null;
}

function formatRate(rate: number | null): string {
  if (rate === null) return "—";
  return `${(rate * 100).toFixed(1)}%`;
}

export default function ProfilePage() {
  const [sourceRates, setSourceRates] = useState<SourceRate[]>([]);
  const [promptRates, setPromptRates] = useState<PromptRate[]>([]);
  const [loadingSource, setLoadingSource] = useState(true);
  const [loadingPrompt, setLoadingPrompt] = useState(true);
  const [errorSource, setErrorSource] = useState(false);
  const [errorPrompt, setErrorPrompt] = useState(false);

  useEffect(() => {
    fetch("/api/analytics/source-rates", { credentials: "include" })
      .then((res) => {
        if (!res.ok) throw new Error(`${res.status}`);
        return res.json() as Promise<SourceRate[]>;
      })
      .then(setSourceRates)
      .catch(() => setErrorSource(true))
      .finally(() => setLoadingSource(false));
  }, []);

  useEffect(() => {
    fetch("/api/analytics/prompt-rates", { credentials: "include" })
      .then((res) => {
        if (!res.ok) throw new Error(`${res.status}`);
        return res.json() as Promise<PromptRate[]>;
      })
      .then(setPromptRates)
      .catch(() => setErrorPrompt(true))
      .finally(() => setLoadingPrompt(false));
  }, []);

  return (
    <main className="min-h-screen bg-gray-50">
      <div className="mx-auto max-w-3xl px-4 py-8">
        <h1 className="mb-8 text-xl font-semibold text-gray-900">
          Profile &amp; Analytics
        </h1>

        {/* Source Performance */}
        <section className="mb-10">
          <h2 className="mb-3 text-base font-medium text-gray-700">
            Source Performance
          </h2>
          {loadingSource ? (
            <p className="text-sm text-gray-500">Loading...</p>
          ) : errorSource ? (
            <p className="text-sm text-red-500">Failed to load.</p>
          ) : sourceRates.length === 0 ? (
            <p className="text-sm text-gray-400">No data yet.</p>
          ) : (
            <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 text-left text-xs font-medium uppercase tracking-wide text-gray-500">
                  <tr>
                    <th className="px-4 py-3">Source</th>
                    <th className="px-4 py-3 text-right">Sent</th>
                    <th className="px-4 py-3 text-right">Responded</th>
                    <th className="px-4 py-3 text-right">Response Rate</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {sourceRates.map((row) => (
                    <tr key={row.source} className="hover:bg-gray-50">
                      <td className="px-4 py-3 font-medium text-gray-900">
                        {row.source}
                      </td>
                      <td className="px-4 py-3 text-right text-gray-600">
                        {row.sent_count}
                      </td>
                      <td className="px-4 py-3 text-right text-gray-600">
                        {row.responded_count}
                      </td>
                      <td className="px-4 py-3 text-right text-gray-600">
                        {formatRate(row.response_rate)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* Template Performance */}
        <section>
          <h2 className="mb-3 text-base font-medium text-gray-700">
            Template Performance
          </h2>
          {loadingPrompt ? (
            <p className="text-sm text-gray-500">Loading...</p>
          ) : errorPrompt ? (
            <p className="text-sm text-red-500">Failed to load.</p>
          ) : promptRates.length === 0 ? (
            <p className="text-sm text-gray-400">No data yet.</p>
          ) : (
            <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 text-left text-xs font-medium uppercase tracking-wide text-gray-500">
                  <tr>
                    <th className="px-4 py-3">Template Version</th>
                    <th className="px-4 py-3 text-right">Sent</th>
                    <th className="px-4 py-3 text-right">Responded</th>
                    <th className="px-4 py-3 text-right">Response Rate</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {promptRates.map((row) => (
                    <tr
                      key={row.prompt_version ?? "__unversioned__"}
                      className="hover:bg-gray-50"
                    >
                      <td className="px-4 py-3 font-medium text-gray-900">
                        {row.prompt_version ?? "(unversioned)"}
                      </td>
                      <td className="px-4 py-3 text-right text-gray-600">
                        {row.sent_count}
                      </td>
                      <td className="px-4 py-3 text-right text-gray-600">
                        {row.responded_count}
                      </td>
                      <td className="px-4 py-3 text-right text-gray-600">
                        {formatRate(row.response_rate)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
