import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Internship Intel",
  description: "AI-powered internship discovery and application pipeline",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50 text-gray-900 antialiased">
        <nav className="flex gap-4 p-4 border-b bg-white">
          <Link href="/" className="text-sm font-medium hover:underline">Jobs</Link>
          <Link href="/tracker" className="text-sm font-medium hover:underline">Tracker</Link>
          <Link href="/outbox" className="text-sm font-medium hover:underline">Outbox</Link>
          <Link href="/profile" className="text-sm font-medium hover:underline">Profile</Link>
        </nav>
        {children}
      </body>
    </html>
  );
}
