/**
 * TEMPLATE: People Page — Creators + Mentioned Figures
 *
 * Combines both profile systems on one page:
 * 1. Top section: Creator cards (account profiles) with type filters
 * 2. Section break
 * 3. Bottom section: Mentioned figures (person profiles) with role filters
 *
 * Data:
 * - {prefix}AccountProfiles → creators
 * - {prefix}PersonProfiles → mentioned figures
 *
 * Navigation:
 * - Creator cards → /your-collection/creator/[username]
 * - Person cards → /your-collection/person/[slug]
 * - BOTH must use the same navigation pattern (consistency)
 */

"use client";

import React, { useMemo, useState } from "react";
// import { useQuery } from "convex/react";
// import { api } from "@/convex/_generated/api";

// =========================================================================
// FILTER PILLS
// =========================================================================

/**
 * Filter pills — horizontal row of clickable type/role filters.
 * Active pill gets a filled background, others are outline only.
 */
function FilterPills({
  options,
  selected,
  onSelect,
}: {
  options: string[];
  selected: string | null;
  onSelect: (value: string | null) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2 mb-4">
      <button
        onClick={() => onSelect(null)}
        className={`text-xs px-3 py-1 font-mono transition-colors ${
          selected === null
            ? "bg-[#1a1a1a] text-white"
            : "bg-transparent text-[#6b7280] hover:text-[#1a1a1a]"
        }`}
        style={{ border: "1px solid #e5e5e5", borderRadius: "3px" }}
      >
        All
      </button>
      {options.map((opt) => (
        <button
          key={opt}
          onClick={() => onSelect(opt === selected ? null : opt)}
          className={`text-xs px-3 py-1 font-mono transition-colors ${
            selected === opt
              ? "bg-[#1a1a1a] text-white"
              : "bg-transparent text-[#6b7280] hover:text-[#1a1a1a]"
          }`}
          style={{ border: "1px solid #e5e5e5", borderRadius: "3px" }}
        >
          {opt}
        </button>
      ))}
    </div>
  );
}

// =========================================================================
// SEARCH BAR
// =========================================================================

function SearchBar({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
}) {
  return (
    <input
      type="text"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className="w-full max-w-[400px] px-3 py-2 text-sm font-body bg-white"
      style={{ border: "1px solid #e5e5e5", borderRadius: "3px", outline: "none" }}
    />
  );
}

// =========================================================================
// PROFILE CARDS
// =========================================================================

/**
 * Creator card — links to /your-collection/creator/[username]
 */
function CreatorCard({
  profile,
}: {
  profile: {
    username: string;
    displayName?: string;
    accountType: string;
    tier: string;
    postCount: number;
    emotionProfile: Record<string, number>;
  };
}) {
  const dominantEmotion = Object.entries(profile.emotionProfile || {})
    .sort(([, a], [, b]) => b - a)[0]?.[0] || "neutral";

  return (
    <a
      href={`/your-collection/creator/${profile.username}`}
      className="block bg-white p-4 no-underline transition-colors"
      style={{ border: "1px solid #e5e5e5", borderRadius: "3px" }}
      onMouseEnter={(e) => (e.currentTarget.style.borderColor = "#d1d5db")}
      onMouseLeave={(e) => (e.currentTarget.style.borderColor = "#e5e5e5")}
    >
      <div className="flex items-center gap-3">
        {/* Initials avatar */}
        <div
          className="w-10 h-10 flex items-center justify-center bg-[#f5f5f5] font-mono text-sm text-[#6b7280]"
          style={{ borderRadius: "3px" }}
        >
          {(profile.displayName || profile.username).charAt(0).toUpperCase()}
        </div>
        <div className="min-w-0">
          <div className="font-heading text-base truncate">
            {profile.displayName || `@${profile.username}`}
          </div>
          <div className="text-xs text-[#6b7280]">
            @{profile.username}
          </div>
        </div>
      </div>
      <div className="flex gap-3 mt-3 text-xs text-[#6b7280] font-mono">
        <span>{profile.postCount} posts</span>
        <span>{profile.accountType}</span>
        <span>{dominantEmotion}</span>
      </div>
    </a>
  );
}

/**
 * Person card — links to /your-collection/person/[slug]
 *
 * IMPORTANT: Filter topEntities to PERSON type only when showing "Dominant voices".
 */
function PersonCard({
  profile,
}: {
  profile: {
    canonical: string;
    slug: string;
    role?: string;
    tier: string;
    postCount: number;
    photoUrl?: string;
  };
}) {
  return (
    <a
      href={`/your-collection/person/${profile.slug}`}
      className="block bg-white p-4 no-underline transition-colors"
      style={{ border: "1px solid #e5e5e5", borderRadius: "3px" }}
      onMouseEnter={(e) => (e.currentTarget.style.borderColor = "#d1d5db")}
      onMouseLeave={(e) => (e.currentTarget.style.borderColor = "#e5e5e5")}
    >
      <div className="flex items-center gap-3">
        {profile.photoUrl ? (
          <img
            src={profile.photoUrl}
            alt={profile.canonical}
            className="w-10 h-10 object-cover"
            style={{ borderRadius: "3px" }}
          />
        ) : (
          <div
            className="w-10 h-10 flex items-center justify-center bg-[#f5f5f5] font-mono text-sm"
            style={{ borderRadius: "3px" }}
          >
            {profile.canonical.charAt(0)}
          </div>
        )}
        <div>
          <div className="font-heading text-base">{profile.canonical}</div>
          {profile.role && (
            <div className="text-xs text-[#6b7280]">{profile.role}</div>
          )}
        </div>
      </div>
      <div className="font-mono text-xs text-[#6b7280] mt-2">
        {profile.postCount} mentions · {profile.tier}
      </div>
    </a>
  );
}

// =========================================================================
// MAIN PAGE
// =========================================================================

export default function PeoplePage() {
  const [search, setSearch] = useState("");
  const [accountTypeFilter, setAccountTypeFilter] = useState<string | null>(null);
  const [roleFilter, setRoleFilter] = useState<string | null>(null);

  // const accountProfiles = useQuery(api.{prefix}.list{Prefix}AccountProfiles);
  // const personProfiles = useQuery(api.{prefix}.list{Prefix}PersonProfiles);

  // Derive filter options from data
  // const accountTypes = useMemo(
  //   () => [...new Set(accountProfiles?.map((p) => p.accountType))],
  //   [accountProfiles]
  // );
  // const roles = useMemo(
  //   () => [...new Set(personProfiles?.filter((p) => p.role).map((p) => p.role!))],
  //   [personProfiles]
  // );

  // Filter + search
  // const filteredCreators = useMemo(() => {
  //   return (accountProfiles ?? [])
  //     .filter((p) => !accountTypeFilter || p.accountType === accountTypeFilter)
  //     .filter(
  //       (p) =>
  //         !search ||
  //         p.username.toLowerCase().includes(search.toLowerCase()) ||
  //         p.displayName?.toLowerCase().includes(search.toLowerCase())
  //     );
  // }, [accountProfiles, accountTypeFilter, search]);

  return (
    <div className="max-w-[1200px] mx-auto px-4 py-8" style={{ background: "#fafaf8" }}>
      {/* Creators section */}
      <section className="mb-12">
        <h1 className="font-heading text-3xl mb-2">Creators</h1>
        <p className="text-sm text-[#6b7280] mb-4">
          Instagram accounts that posted content in this collection.
        </p>

        <SearchBar
          value={search}
          onChange={setSearch}
          placeholder="Search creators..."
        />
        {/* <FilterPills options={accountTypes} selected={accountTypeFilter} onSelect={setAccountTypeFilter} /> */}

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 mt-4">
          {/* {filteredCreators.map((p) => <CreatorCard key={p.username} profile={p} />)} */}
        </div>
      </section>

      {/* Section break */}
      <div className="text-center text-[#9ca3af] my-8">· · ·</div>

      {/* Mentioned Figures section */}
      <section>
        <h2 className="font-heading text-2xl mb-2">Mentioned Figures</h2>
        <p className="text-sm text-[#6b7280] mb-4">
          People mentioned across posts in this collection.
        </p>
        {/* <FilterPills options={roles} selected={roleFilter} onSelect={setRoleFilter} /> */}

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {/* {personProfiles?.map((p) => <PersonCard key={p.slug} profile={p} />)} */}
        </div>
      </section>
    </div>
  );
}
