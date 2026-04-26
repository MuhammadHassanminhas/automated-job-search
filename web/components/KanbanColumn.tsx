"use client";
import { ApplicationCard } from "./ApplicationCard";
import type { Application } from "@/lib/api";

const COLUMN_COLORS: Record<string, string> = {
  APPLIED:      "bg-blue-50 border-blue-200",
  SENT:         "bg-yellow-50 border-yellow-200",
  RESPONDED:    "bg-green-50 border-green-200",
  INTERVIEWING: "bg-purple-50 border-purple-200",
  OFFERED:      "bg-emerald-50 border-emerald-200",
  REJECTED:     "bg-red-50 border-red-200",
};

interface Props {
  status: string;
  cards: Application[];
  onDrop: (cardId: string, newStatus: string) => void;
  getDraggingId: () => string | null;
  onCardDragStart: (id: string) => void;
}

export function KanbanColumn({ status, cards, onDrop, getDraggingId, onCardDragStart }: Props) {
  function handleDragOver(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    if (e.dataTransfer) {
      e.dataTransfer.dropEffect = "move";
    }
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    // Try dataTransfer first; fall back to the ref (for tests without dataTransfer)
    const cardId =
      (e.dataTransfer ? e.dataTransfer.getData("text/plain") : "") ||
      getDraggingId();
    if (cardId) {
      onDrop(cardId, status);
    }
  }

  return (
    <div
      onDragOver={handleDragOver}
      onDrop={handleDrop}
      data-testid={`column-${status}`}
      className={`min-h-48 rounded-lg border p-3 transition-colors ${COLUMN_COLORS[status] ?? "bg-gray-50 border-gray-200"}`}
    >
      <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-500">{status}</h3>
      <div className="space-y-2">
        {cards.map((app) => (
          <ApplicationCard key={app.id} application={app} onDragStart={onCardDragStart} />
        ))}
      </div>
    </div>
  );
}
