/**
 * TEMPLATE: Landing / Overview Page
 *
 * The entry point for a deep dive. Shows:
 * 1. Hero section with sparkline chart (monthly save volume)
 * 2. Metric grid (6-8 key numbers)
 * 3. Chapter overview cards
 * 4. Page grid (links to all analytical pages)
 * 5. About section
 *
 * Data: Queries {prefix}Analysis (hero_stats, daily_volume),
 *       {prefix}Chapters (chapter cards)
 *
 * Design notes:
 * - Background: #fafaf8 (warm paper)
 * - Cards: white, 1px border, 3px radius
 * - Metrics: font-data (IBM Plex Mono) for numbers
 * - Headings: font-heading (DM Serif Display)
 */

"use client";

import React from "react";
// import { useQuery } from "convex/react";
// import { api } from "@/convex/_generated/api";

/**
 * MetricCard — Displays a single statistic.
 *
 * Design:
 * - Label: uppercase, font-mono, text-xs, text-secondary
 * - Value: font-heading, text-3xl
 * - Optional delta: green for positive, red for negative
 */
function MetricCard({
  label,
  value,
  delta,
}: {
  label: string;
  value: string | number;
  delta?: string;
}) {
  return (
    <div
      className="bg-white p-4"
      style={{ border: "1px solid #e5e5e5", borderRadius: "3px" }}
    >
      <div className="font-mono text-xs uppercase tracking-wider text-[#6b7280]">
        {label}
      </div>
      <div className="font-heading text-3xl mt-1">{value}</div>
      {delta && (
        <div className="text-sm mt-1 text-[#6b7280]">{delta}</div>
      )}
    </div>
  );
}

/**
 * ChapterCard — Overview of a narrative chapter.
 *
 * Shows: title, date range, post count, dominant emotion.
 * Links to: /your-collection/chronicle#chapter-{id}
 */
function ChapterCard({
  chapter,
}: {
  chapter: {
    chapterId: string;
    title: string;
    startDate: string;
    endDate: string;
    postCount: number;
    eventCount: number;
    emotionSignature: Record<string, number>;
  };
}) {
  const dominantEmotion = Object.entries(chapter.emotionSignature || {})
    .sort(([, a], [, b]) => b - a)[0]?.[0] || "neutral";

  return (
    <div
      className="bg-white p-4 transition-colors"
      style={{
        border: "1px solid #e5e5e5",
        borderRadius: "3px",
      }}
      // Hover: border-color transition only (no shadow, no scale)
      onMouseEnter={(e) => (e.currentTarget.style.borderColor = "#d1d5db")}
      onMouseLeave={(e) => (e.currentTarget.style.borderColor = "#e5e5e5")}
    >
      <div className="font-heading text-lg">{chapter.title}</div>
      <div className="font-mono text-xs text-[#6b7280] mt-1">
        {chapter.startDate} → {chapter.endDate}
      </div>
      <div className="flex gap-4 mt-2 text-sm text-[#6b7280]">
        <span className="font-mono">{chapter.postCount.toLocaleString()} posts</span>
        <span className="font-mono">{chapter.eventCount} events</span>
        <span>{dominantEmotion}</span>
      </div>
    </div>
  );
}

/**
 * PageCard — Link to an analytical page.
 *
 * Each deep dive has custom pages. Build the list based on
 * what your collection's data reveals (discovery step 4-5).
 */
function PageCard({
  href,
  title,
  description,
}: {
  href: string;
  title: string;
  description: string;
}) {
  return (
    <a
      href={href}
      className="block bg-white p-4 transition-colors no-underline"
      style={{ border: "1px solid #e5e5e5", borderRadius: "3px" }}
      onMouseEnter={(e) => (e.currentTarget.style.borderColor = "#d1d5db")}
      onMouseLeave={(e) => (e.currentTarget.style.borderColor = "#e5e5e5")}
    >
      <div className="font-heading text-lg text-[#1a1a1a]">{title}</div>
      <div className="text-sm text-[#6b7280] mt-1">{description}</div>
    </a>
  );
}

/**
 * Landing page component.
 *
 * Query pattern:
 *   const heroStats = useQuery(api.yourModule.getAnalysis, { key: "hero_stats" });
 *   const chapters = useQuery(api.yourModule.listChapters);
 */
export default function LandingPage() {
  // const heroStats = useQuery(api.{prefix}.get{Prefix}Analysis, { key: "hero_stats" });
  // const chapters = useQuery(api.{prefix}.list{Prefix}Chapters);

  return (
    <div className="max-w-[1200px] mx-auto px-4 py-8" style={{ background: "#fafaf8" }}>
      {/* Hero */}
      <section className="mb-12">
        <h1 className="font-heading text-4xl">YourCollection</h1>
        <p className="text-lg text-[#6b7280] mt-2 max-w-[600px]">
          A brief description of what this collection archive contains and why it matters.
        </p>
        {/* Sparkline chart here — monthly volume using Recharts AreaChart */}
      </section>

      {/* Metrics Grid */}
      <section className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-12">
        <MetricCard label="Total Posts" value="1,234" />
        <MetricCard label="Accounts" value="156" />
        <MetricCard label="Events" value="42" />
        <MetricCard label="Date Range" value="2023–2026" />
        {/* Add collection-specific metrics */}
      </section>

      {/* Section break */}
      <div className="text-center text-[#9ca3af] my-8">· · ·</div>

      {/* Chapters */}
      <section className="mb-12">
        <h2 className="font-heading text-2xl mb-4">Chapters</h2>
        <div className="grid gap-3">
          {/* {chapters?.map((ch) => <ChapterCard key={ch.chapterId} chapter={ch} />)} */}
        </div>
      </section>

      {/* Page Grid */}
      <section className="mb-12">
        <h2 className="font-heading text-2xl mb-4">Explore</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <PageCard
            href="/your-collection/chronicle"
            title="Chronicle"
            description="Scroll through every post, organized by chapter and week."
          />
          <PageCard
            href="/your-collection/people"
            title="People"
            description="Creators and mentioned figures in this collection."
          />
          {/* Add collection-specific pages */}
        </div>
      </section>

      {/* About */}
      <section className="max-w-[600px]">
        <h2 className="font-heading text-xl mb-2">About This Archive</h2>
        <p className="text-sm text-[#6b7280] leading-relaxed">
          Brief context about the collection — what it represents, how it was curated,
          and what the analysis reveals.
        </p>
      </section>
    </div>
  );
}
