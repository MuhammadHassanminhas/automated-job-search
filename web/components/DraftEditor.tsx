"use client";

import { useState } from "react";
import type { Draft } from "@/lib/api";
import { api } from "@/lib/api";

interface Props {
  draft: Draft;
  onSave?: (updated: Draft) => void;
}

type Tab = "resume" | "cover_letter" | "email";

export function DraftEditor({ draft, onSave }: Props) {
  const [activeTab, setActiveTab] = useState<Tab>("resume");
  const [values, setValues] = useState({
    resume_md: draft.resume_md ?? "",
    cover_letter_md: draft.cover_letter_md ?? "",
    email_body: draft.email_body ?? "",
    email_subject: draft.email_subject ?? "",
  });
  const [saving, setSaving] = useState(false);

  const tabs: { id: Tab; label: string }[] = [
    { id: "resume", label: "Resume" },
    { id: "cover_letter", label: "Cover Letter" },
    { id: "email", label: "Email" },
  ];

  async function handleSave() {
    setSaving(true);
    try {
      const updated = await api.drafts.patch(draft.id, {
        resume_md: values.resume_md,
        cover_letter_md: values.cover_letter_md,
        email_body: values.email_body,
        email_subject: values.email_subject,
      });
      onSave?.(updated);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex flex-col gap-4" data-testid="draft-editor">
      <div role="tablist" className="flex gap-2 border-b border-gray-200">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            role="tab"
            aria-selected={activeTab === tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === tab.id
                ? "border-b-2 border-indigo-600 text-indigo-600"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="flex-1">
        {activeTab === "resume" && (
          <textarea
            aria-label="Resume content"
            className="h-96 w-full rounded border border-gray-200 p-3 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            value={values.resume_md}
            onChange={(e) => setValues((v) => ({ ...v, resume_md: e.target.value }))}
          />
        )}
        {activeTab === "cover_letter" && (
          <textarea
            aria-label="Cover letter content"
            className="h-96 w-full rounded border border-gray-200 p-3 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            value={values.cover_letter_md}
            onChange={(e) => setValues((v) => ({ ...v, cover_letter_md: e.target.value }))}
          />
        )}
        {activeTab === "email" && (
          <div className="flex flex-col gap-2">
            <input
              aria-label="Email subject"
              className="rounded border border-gray-200 p-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              value={values.email_subject}
              onChange={(e) => setValues((v) => ({ ...v, email_subject: e.target.value }))}
            />
            <textarea
              aria-label="Email body"
              className="h-80 w-full rounded border border-gray-200 p-3 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              value={values.email_body}
              onChange={(e) => setValues((v) => ({ ...v, email_body: e.target.value }))}
            />
          </div>
        )}
      </div>

      <button
        onClick={handleSave}
        disabled={saving}
        className="self-end rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
      >
        {saving ? "Saving…" : "Save"}
      </button>
    </div>
  );
}
