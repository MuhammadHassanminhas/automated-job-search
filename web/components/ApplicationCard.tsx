"use client";
import type { Application } from "@/lib/api";

interface Props {
  application: Application;
  onDragStart?: (id: string) => void;
}

export function ApplicationCard({ application, onDragStart }: Props) {
  const title = application.job?.title ?? application.job_title;
  const company = application.job?.company ?? application.company;

  function handleDragStart(e: React.DragEvent<HTMLDivElement>) {
    if (e.dataTransfer) {
      e.dataTransfer.setData("text/plain", application.id);
      e.dataTransfer.effectAllowed = "move";
    }
    onDragStart?.(application.id);
  }

  return (
    <div
      draggable
      onDragStart={handleDragStart}
      data-testid={`app-card-${application.id}`}
      className="rounded-lg border border-gray-200 bg-white p-3 shadow-sm cursor-grab active:cursor-grabbing"
    >
      <p className="font-medium text-sm text-gray-900">{title}</p>
      <p className="text-xs text-gray-500">{company}</p>
    </div>
  );
}
