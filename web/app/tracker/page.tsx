"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api, type Application } from "@/lib/api";
import { KanbanColumn } from "@/components/KanbanColumn";

const COLUMNS = ["APPLIED", "SENT", "RESPONDED", "INTERVIEWING", "OFFERED", "REJECTED"] as const;

export default function TrackerPage() {
  const router = useRouter();
  const [applications, setApplications] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  // Use a ref so drag state is always current even within a single act() block
  const draggingIdRef = useRef<string | null>(null);

  useEffect(() => {
    api.auth
      .me()
      .then(() => api.applications.list())
      .then(setApplications)
      .catch(() => router.push("/login"))
      .finally(() => setLoading(false));
  }, [router]);

  function handleCardDragStart(id: string) {
    draggingIdRef.current = id;
  }

  async function handleDrop(cardId: string, newStatus: string) {
    draggingIdRef.current = null;

    const snapshot = applications.slice();

    setApplications((apps) =>
      apps.map((a) =>
        a.id === cardId ? { ...a, status: newStatus as Application["status"] } : a
      )
    );

    try {
      await api.applications.patch(cardId, { status: newStatus });
    } catch {
      setApplications(snapshot);
    }
  }

  function getDraggingId() {
    return draggingIdRef.current;
  }

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-gray-500">Loading…</p>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-gray-50 p-6">
      <div className="mx-auto max-w-6xl">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-xl font-semibold text-gray-900">Application Tracker</h1>
          <button
            onClick={() => api.auth.logout().then(() => router.push("/login"))}
            className="text-sm text-gray-500 hover:text-gray-700"
          >
            Sign out
          </button>
        </div>
        <div className="grid grid-cols-3 gap-4 xl:grid-cols-6">
          {COLUMNS.map((col) => (
            <KanbanColumn
              key={col}
              status={col}
              cards={applications.filter((a) => a.status === col)}
              onDrop={handleDrop}
              getDraggingId={getDraggingId}
              onCardDragStart={handleCardDragStart}
            />
          ))}
        </div>
      </div>
    </main>
  );
}
