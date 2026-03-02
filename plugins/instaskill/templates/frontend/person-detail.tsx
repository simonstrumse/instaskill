/**
 * TEMPLATE: Person Detail Page
 *
 * Shows a single person's profile with:
 * - Header: photo, name, role, affiliation, bio, key stats
 * - Monthly timeline chart (Recharts BarChart)
 * - Emotion breakdown (horizontal bars)
 * - Post grid (all posts mentioning this person)
 * - Timeline appearances (events where this person is mentioned)
 *
 * Route: /your-collection/person/[slug]
 *
 * Data:
 * - {prefix}PersonProfiles → getPersonProfile(slug)
 * - {prefix}Timeline → getEventsForPerson(canonical)
 * - posts → getPostsByIds(postIds)
 */

"use client";

import React from "react";
// import { useQuery } from "convex/react";
// import { api } from "@/convex/_generated/api";
// import { useParams } from "next/navigation";

// =========================================================================
// PERSON HEADER
// =========================================================================

/**
 * Profile header with photo, name, stats.
 *
 * Design:
 * - Photo: 80x80, 3px radius (not rounded-full)
 * - Name: font-heading, text-3xl
 * - Role badge: font-mono, text-xs, outline pill
 * - Stats row: font-mono, text-sm
 */
function PersonHeader({
  profile,
}: {
  profile: {
    canonical: string;
    photoUrl?: string;
    role?: string;
    affiliation?: string;
    bio?: string;
    postCount: number;
    firstSeen: string;
    lastSeen: string;
    tier: string;
  };
}) {
  return (
    <div className="flex gap-6 mb-8">
      {/* Photo */}
      {profile.photoUrl ? (
        <img
          src={profile.photoUrl}
          alt={profile.canonical}
          className="w-20 h-20 object-cover shrink-0"
          style={{ borderRadius: "3px" }}
        />
      ) : (
        <div
          className="w-20 h-20 flex items-center justify-center bg-[#f5f5f5] font-heading text-2xl text-[#6b7280] shrink-0"
          style={{ borderRadius: "3px" }}
        >
          {profile.canonical.charAt(0)}
        </div>
      )}

      {/* Info */}
      <div>
        <h1 className="font-heading text-3xl">{profile.canonical}</h1>
        <div className="flex items-center gap-2 mt-1">
          {profile.role && (
            <span
              className="font-mono text-xs px-2 py-0.5 text-[#6b7280]"
              style={{ border: "1px solid #e5e5e5", borderRadius: "3px" }}
            >
              {profile.role}
            </span>
          )}
          {profile.affiliation && (
            <span className="text-sm text-[#6b7280]">{profile.affiliation}</span>
          )}
        </div>
        {profile.bio && (
          <p className="text-sm text-[#1a1a1a] mt-2 max-w-[500px] leading-relaxed">
            {profile.bio}
          </p>
        )}
        <div className="flex gap-4 mt-3 font-mono text-sm text-[#6b7280]">
          <span>{profile.postCount} mentions</span>
          <span>{profile.firstSeen} → {profile.lastSeen}</span>
        </div>
      </div>
    </div>
  );
}

// =========================================================================
// EMOTION BARS
// =========================================================================

/**
 * Horizontal emotion bars — shows the emotional context of mentions.
 *
 * Design:
 * - Bar height: 20px, 3px radius
 * - Label: font-mono, text-xs
 * - Colors from design system semantic palette
 */
function EmotionBars({
  emotionProfile,
}: {
  emotionProfile: Record<string, number>;
}) {
  const EMOTION_COLORS: Record<string, string> = {
    anger: "#dc2626",
    joy: "#f59e0b",
    sadness: "#3b82f6",
    fear: "#8b5cf6",
    surprise: "#10b981",
    disgust: "#6b7280",
    neutral: "#9ca3af",
  };

  const sorted = Object.entries(emotionProfile)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 7);

  const maxValue = Math.max(...sorted.map(([, v]) => v), 0.01);

  return (
    <div className="space-y-2">
      {sorted.map(([emotion, value]) => (
        <div key={emotion} className="flex items-center gap-3">
          <span className="font-mono text-xs text-[#6b7280] w-16 text-right shrink-0">
            {emotion}
          </span>
          <div className="flex-1 h-5 bg-[#f5f5f5]" style={{ borderRadius: "3px" }}>
            <div
              className="h-full"
              style={{
                width: `${(value / maxValue) * 100}%`,
                backgroundColor: EMOTION_COLORS[emotion] || "#9ca3af",
                borderRadius: "3px",
              }}
            />
          </div>
          <span className="font-mono text-xs text-[#6b7280] w-10 shrink-0">
            {(value * 100).toFixed(0)}%
          </span>
        </div>
      ))}
    </div>
  );
}

// =========================================================================
// MONTHLY TIMELINE
// =========================================================================

/**
 * Monthly bar chart showing mention frequency over time.
 * Use Recharts BarChart with font-mono axis labels.
 */
function MonthlyTimeline({
  monthlyCounts,
}: {
  monthlyCounts: Record<string, number>;
}) {
  const data = Object.entries(monthlyCounts)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([month, count]) => ({ month, count }));

  if (data.length === 0) return null;

  // Simplified — in practice, use Recharts BarChart
  return (
    <div>
      <h3 className="font-heading text-lg mb-3">Activity Over Time</h3>
      <div className="flex items-end gap-1 h-[120px]">
        {data.map(({ month, count }) => {
          const maxCount = Math.max(...data.map((d) => d.count));
          const height = (count / maxCount) * 100;
          return (
            <div key={month} className="flex-1 flex flex-col items-center justify-end">
              <div
                className="w-full bg-[#1a1a1a]"
                style={{ height: `${height}%`, borderRadius: "2px 2px 0 0", minHeight: count > 0 ? "2px" : "0" }}
              />
            </div>
          );
        })}
      </div>
      <div className="flex gap-1 mt-1">
        {data.map(({ month }) => (
          <div key={month} className="flex-1 text-center">
            <span className="font-mono text-[8px] text-[#9ca3af]">
              {month.slice(5)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// =========================================================================
// EVENT APPEARANCES
// =========================================================================

/**
 * Timeline events where this person is mentioned.
 */
function EventAppearances({
  events,
}: {
  events: {
    eventId: string;
    date: string;
    postCount: number;
    dominantEmotion?: string;
  }[];
}) {
  if (!events || events.length === 0) return null;

  return (
    <div>
      <h3 className="font-heading text-lg mb-3">Timeline Appearances</h3>
      <div className="space-y-2">
        {events.map((event) => (
          <div
            key={event.eventId}
            className="flex items-center gap-3 p-2 bg-white"
            style={{ border: "1px solid #e5e5e5", borderRadius: "3px" }}
          >
            <span className="font-mono text-xs text-[#6b7280] w-24 shrink-0">
              {event.date}
            </span>
            <span className="text-sm flex-1">
              {event.postCount} posts
            </span>
            {event.dominantEmotion && (
              <span className="text-xs text-[#6b7280]">{event.dominantEmotion}</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// =========================================================================
// MAIN PAGE
// =========================================================================

/**
 * Person detail page.
 *
 * Query pattern:
 *   const { slug } = useParams();
 *   const profile = useQuery(api.{prefix}.get{Prefix}PersonProfile, { slug });
 *   const events = useQuery(api.{prefix}.get{Prefix}EventsForPerson,
 *     profile ? { canonical: profile.canonical } : "skip"
 *   );
 */
export default function PersonDetailPage() {
  // const { slug } = useParams<{ slug: string }>();
  // const profile = useQuery(api.{prefix}.get{Prefix}PersonProfile, { slug });
  // const events = useQuery(api.{prefix}.get{Prefix}EventsForPerson,
  //   profile ? { canonical: profile.canonical } : "skip"
  // );

  // Placeholder data for template illustration
  const profile = {
    canonical: "Example Person",
    slug: "example-person",
    tier: "full" as const,
    role: "journalist",
    affiliation: "Example Org",
    bio: "A journalist covering the topic area relevant to this collection.",
    photoUrl: undefined,
    postCount: 45,
    firstSeen: "2024-01-15",
    lastSeen: "2025-12-20",
    emotionProfile: { anger: 0.3, sadness: 0.25, fear: 0.15, disgust: 0.1, joy: 0.1, surprise: 0.05, neutral: 0.05 },
    monthlyCounts: { "2024-03": 5, "2024-06": 8, "2024-09": 12, "2024-12": 10, "2025-03": 6, "2025-06": 4 },
  };

  return (
    <div className="max-w-[1200px] mx-auto px-4 py-8" style={{ background: "#fafaf8" }}>
      {/* Back link */}
      <a
        href="/your-collection/people"
        className="text-sm text-[#6b7280] hover:text-[#1a1a1a] no-underline mb-6 inline-block"
      >
        ← Back to People
      </a>

      {/* Header */}
      <PersonHeader profile={profile} />

      {/* Two-column: timeline + emotions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-12">
        <MonthlyTimeline monthlyCounts={profile.monthlyCounts} />
        <div>
          <h3 className="font-heading text-lg mb-3">Emotional Context</h3>
          <EmotionBars emotionProfile={profile.emotionProfile} />
        </div>
      </div>

      {/* Section break */}
      <div className="text-center text-[#9ca3af] my-8">· · ·</div>

      {/* Event appearances */}
      {/* <EventAppearances events={events ?? []} /> */}

      {/* Post grid — all posts mentioning this person */}
      <section className="mt-8">
        <h3 className="font-heading text-lg mb-3">Posts</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
          {/* Post cards here — use native loading="lazy" on images */}
        </div>
      </section>
    </div>
  );
}
