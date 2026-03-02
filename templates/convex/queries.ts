/**
 * Convex Query Patterns — Standard queries for deep dive tables.
 *
 * Replace {prefix} with your collection prefix.
 * Replace {Prefix} with PascalCase version (e.g., "climate" → "Climate").
 *
 * Pattern: every query parses JSON string fields before returning.
 * All complex fields are stored as JSON strings in Convex.
 */

import { query } from "./_generated/server";
import { v } from "convex/values";

// =========================================================================
// HELPER: Safe JSON parse
// =========================================================================

function parseJSON(str: string | undefined | null, fallback: any = null) {
  if (!str) return fallback;
  try {
    return JSON.parse(str);
  } catch {
    return fallback;
  }
}

// =========================================================================
// ANALYSIS — Pre-computed data blobs
// =========================================================================

/**
 * Get a pre-computed analysis blob by key.
 * Keys: "daily_volume", "hero_stats", "daily_emotions", "frame_distribution"
 */
// export const get{Prefix}Analysis = query({
//   args: { key: v.string() },
//   handler: async (ctx, { key }) => {
//     const doc = await ctx.db
//       .query("{prefix}Analysis")
//       .withIndex("by_key", (q) => q.eq("key", key))
//       .first();
//     if (!doc) return null;
//     return parseJSON(doc.data);
//   },
// });

// =========================================================================
// CHAPTERS
// =========================================================================

/**
 * List all chapters, sorted by sortOrder.
 * Parses JSON fields: emotionSignature, frameDistribution, topEntities.
 */
// export const list{Prefix}Chapters = query({
//   handler: async (ctx) => {
//     const chapters = await ctx.db
//       .query("{prefix}Chapters")
//       .withIndex("by_sortOrder")
//       .collect();
//     return chapters.map((ch) => ({
//       ...ch,
//       emotionSignature: parseJSON(ch.emotionSignature, {}),
//       frameDistribution: parseJSON(ch.frameDistribution, {}),
//       topEntities: parseJSON(ch.topEntities, []),
//     }));
//   },
// });

// =========================================================================
// TIMELINE / EVENTS
// =========================================================================

/**
 * List events, optionally filtered by chapter.
 */
// export const list{Prefix}Events = query({
//   args: { chapterId: v.optional(v.string()) },
//   handler: async (ctx, { chapterId }) => {
//     let q = ctx.db.query("{prefix}Timeline");
//     if (chapterId) {
//       q = q.withIndex("by_chapter", (q) => q.eq("chapterId", chapterId));
//     } else {
//       q = q.withIndex("by_date");
//     }
//     const events = await q.collect();
//     return events.map((e) => ({
//       ...e,
//       emotionSignature: parseJSON(e.emotionSignature, {}),
//       topEntities: parseJSON(e.topEntities, []),
//       topTopics: parseJSON(e.topTopics, []),
//       topAccounts: parseJSON(e.topAccounts, []),
//     }));
//   },
// });

// =========================================================================
// PERSON PROFILES
// =========================================================================

/**
 * List all person profiles, sorted by postCount descending.
 */
// export const list{Prefix}PersonProfiles = query({
//   handler: async (ctx) => {
//     const profiles = await ctx.db.query("{prefix}PersonProfiles").collect();
//     return profiles
//       .map((p) => ({
//         ...p,
//         emotionProfile: parseJSON(p.emotionProfile, {}),
//         monthlyCounts: parseJSON(p.monthlyCounts, {}),
//         aliases: parseJSON(p.aliases, []),
//         // Resolve photo from storage if available
//         // photoUrl: p.photoStorageId ? await ctx.storage.getUrl(p.photoStorageId) : p.photoUrl,
//       }))
//       .sort((a, b) => b.postCount - a.postCount);
//   },
// });

/**
 * Get a single person profile by slug.
 */
// export const get{Prefix}PersonProfile = query({
//   args: { slug: v.string() },
//   handler: async (ctx, { slug }) => {
//     const profile = await ctx.db
//       .query("{prefix}PersonProfiles")
//       .withIndex("by_slug", (q) => q.eq("slug", slug))
//       .first();
//     if (!profile) return null;
//     return {
//       ...profile,
//       emotionProfile: parseJSON(profile.emotionProfile, {}),
//       monthlyCounts: parseJSON(profile.monthlyCounts, {}),
//       aliases: parseJSON(profile.aliases, []),
//     };
//   },
// });

// =========================================================================
// ACCOUNT PROFILES
// =========================================================================

/**
 * List all account profiles.
 */
// export const list{Prefix}AccountProfiles = query({
//   handler: async (ctx) => {
//     const profiles = await ctx.db.query("{prefix}AccountProfiles").collect();
//     return profiles
//       .map((p) => ({
//         ...p,
//         emotionProfile: parseJSON(p.emotionProfile, {}),
//         topTopics: parseJSON(p.topTopics, []),
//         monthlyCounts: parseJSON(p.monthlyCounts, {}),
//       }))
//       .sort((a, b) => b.postCount - a.postCount);
//   },
// });

// =========================================================================
// CHRONICLE CONTENT
// =========================================================================

/**
 * Get all chronicle content (header, chapter intros, epilogue).
 */
// export const list{Prefix}ChronicleContent = query({
//   handler: async (ctx) => {
//     return await ctx.db
//       .query("{prefix}ChronicleContent")
//       .withIndex("by_sortOrder")
//       .collect();
//   },
// });

// =========================================================================
// CLAIMS
// =========================================================================

/**
 * List claims, optionally filtered by category.
 */
// export const list{Prefix}Claims = query({
//   args: { category: v.optional(v.string()) },
//   handler: async (ctx, { category }) => {
//     let q = ctx.db.query("{prefix}Claims");
//     if (category) {
//       q = q.withIndex("by_category", (q) => q.eq("category", category));
//     }
//     return await q.collect();
//   },
// });

// =========================================================================
// CROSS-QUERY: Events for a person
// =========================================================================

/**
 * Find timeline events that mention a specific person.
 * Scans topEntities JSON for the canonical name.
 */
// export const get{Prefix}EventsForPerson = query({
//   args: { canonical: v.string() },
//   handler: async (ctx, { canonical }) => {
//     const events = await ctx.db.query("{prefix}Timeline").collect();
//     return events
//       .filter((e) => {
//         const entities = parseJSON(e.topEntities, []);
//         return entities.some(
//           (ent: any) => ent.name === canonical || ent.name?.includes(canonical)
//         );
//       })
//       .map((e) => ({
//         ...e,
//         emotionSignature: parseJSON(e.emotionSignature, {}),
//         topEntities: parseJSON(e.topEntities, []),
//       }));
//   },
// });
