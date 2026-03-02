/**
 * Convex Schema Template — Deep Dive Tables
 *
 * Replace {prefix} with your collection prefix (camelCase).
 * Example: prefix = "climate" → climateTimeline, climateChapters, etc.
 *
 * All complex objects are stored as JSON strings (v.string()).
 * Parse on read with JSON.parse(). See reference/DATA_CONTRACT.md for field specs.
 *
 * To use: copy this file into your convex/ directory and replace all
 * occurrences of {prefix} with your actual prefix.
 */

import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

export default defineSchema({
  // =========================================================================
  // GLOBAL TABLES (shared across all collections)
  // =========================================================================

  /**
   * Core posts table — all posts from saved_posts.json
   * Imported once during base pipeline, shared by all deep dives.
   */
  posts: defineTable({
    postId: v.string(),
    text: v.optional(v.string()),
    author: v.optional(v.string()),          // @username
    collections: v.optional(v.string()),     // JSON: ["Climate", "Cooking"]
    createdAt: v.optional(v.string()),       // ISO datetime
    savedOn: v.optional(v.string()),         // ISO datetime
    finalExplainer: v.optional(v.string()),  // 100-400 word synthesis
    topicId: v.optional(v.number()),
    topicLabel: v.optional(v.string()),
    sentimentStars: v.optional(v.number()),  // 1-5
    dominantEmotion: v.optional(v.string()),
    emotions: v.optional(v.string()),        // JSON: {anger: 0.3, ...}
    mood: v.optional(v.string()),
    tone: v.optional(v.string()),
    categories: v.optional(v.string()),      // JSON: ["politics", "news"]
    tags: v.optional(v.string()),            // JSON: ["tag1", "tag2"]
    thumbnailStorageId: v.optional(v.id("_storage")),
    suppressed: v.optional(v.boolean()),
  })
    .index("by_postId", ["postId"])
    .index("by_author", ["author"])
    .index("by_topic", ["topicId"]),

  // =========================================================================
  // COLLECTION-SPECIFIC TABLES — Copy this block per collection
  // Replace {prefix} with your collection prefix
  // =========================================================================

  /**
   * Timeline events — bursts detected via z-score + PELT + Kleinberg.
   * Each event has an emotion signature and entity/topic fingerprint.
   */
  /* {prefix}Timeline */
  // {prefix}Timeline: defineTable({
  //   eventId: v.string(),
  //   date: v.string(),                     // ISO date
  //   postCount: v.number(),
  //   zScore: v.number(),
  //   burstType: v.optional(v.string()),    // point, sharp_spike, front_loaded, build_up, sustained
  //   chapterId: v.optional(v.string()),
  //   emotionSignature: v.optional(v.string()),  // JSON
  //   frameDistribution: v.optional(v.string()), // JSON
  //   topEntities: v.optional(v.string()),       // JSON
  //   topTopics: v.optional(v.string()),         // JSON
  //   topAccounts: v.optional(v.string()),       // JSON
  //   dominantEmotion: v.optional(v.string()),
  //   description: v.optional(v.string()),
  //   isChangepoint: v.optional(v.boolean()),
  // })
  //   .index("by_date", ["date"])
  //   .index("by_chapter", ["chapterId"]),

  /**
   * Narrative chapters — 4-6 chronological sections.
   */
  // {prefix}Chapters: defineTable({
  //   chapterId: v.string(),
  //   title: v.string(),
  //   subtitle: v.optional(v.string()),
  //   description: v.optional(v.string()),
  //   startDate: v.string(),
  //   endDate: v.string(),
  //   postCount: v.number(),
  //   eventCount: v.number(),
  //   emotionSignature: v.optional(v.string()),   // JSON
  //   frameDistribution: v.optional(v.string()),  // JSON
  //   topEntities: v.optional(v.string()),        // JSON
  //   sortOrder: v.number(),
  // })
  //   .index("by_sortOrder", ["sortOrder"])
  //   .index("by_chapterId", ["chapterId"]),

  /**
   * Account ecosystem — Instagram accounts classified by type.
   */
  // {prefix}Accounts: defineTable({
  //   username: v.string(),
  //   postCount: v.number(),
  //   accountType: v.string(),
  //   accountRole: v.optional(v.string()),   // original_source | amplifier
  //   community: v.optional(v.string()),
  //   degreeCentrality: v.optional(v.number()),
  //   betweennessCentrality: v.optional(v.number()),
  //   emotionProfile: v.optional(v.string()),    // JSON
  //   activeMonths: v.optional(v.string()),      // JSON
  //   topTopics: v.optional(v.string()),         // JSON
  // })
  //   .index("by_username", ["username"])
  //   .index("by_type", ["accountType"]),

  /**
   * Named entities — people, organizations, places, concepts.
   */
  // {prefix}Entities: defineTable({
  //   name: v.string(),
  //   entityType: v.string(),      // PERSON, ORG, GPE, LOC, EVENT, CONCEPT
  //   count: v.number(),
  //   firstSeen: v.string(),
  //   lastSeen: v.string(),
  //   monthlyCounts: v.optional(v.string()),       // JSON
  //   associatedEmotions: v.optional(v.string()),  // JSON
  //   coOccurrences: v.optional(v.string()),       // JSON
  //   lat: v.optional(v.number()),
  //   lon: v.optional(v.number()),
  // })
  //   .index("by_name", ["name"])
  //   .index("by_type", ["entityType"])
  //   .index("by_count", ["count"]),

  /**
   * Factual claims extracted from posts.
   */
  // {prefix}Claims: defineTable({
  //   claimText: v.string(),
  //   category: v.string(),
  //   checkWorthiness: v.number(),    // 1-5
  //   postId: v.string(),
  //   date: v.string(),
  //   source: v.optional(v.string()),
  //   confidence: v.optional(v.number()),
  // })
  //   .index("by_category", ["category"])
  //   .index("by_date", ["date"])
  //   .index("by_worthiness", ["checkWorthiness"]),

  /**
   * Pre-computed analysis blobs — keyed by string, data is JSON.
   */
  // {prefix}Analysis: defineTable({
  //   key: v.string(),    // daily_volume, hero_stats, emotion_arc, etc.
  //   data: v.string(),   // JSON blob
  // })
  //   .index("by_key", ["key"]),

  /**
   * Chronicle editorial prose — header, chapter intros, epilogue.
   */
  // {prefix}ChronicleContent: defineTable({
  //   contentId: v.string(),
  //   contentType: v.string(),     // header, chapter_intro, epilogue
  //   chapterId: v.optional(v.string()),
  //   title: v.optional(v.string()),
  //   body: v.string(),
  //   sortOrder: v.number(),
  // })
  //   .index("by_type", ["contentType"])
  //   .index("by_sortOrder", ["sortOrder"]),

  /**
   * Person profiles — named individuals mentioned across posts.
   */
  // {prefix}PersonProfiles: defineTable({
  //   canonical: v.string(),
  //   slug: v.string(),
  //   tier: v.string(),            // "full" | "chip"
  //   role: v.optional(v.string()),
  //   affiliation: v.optional(v.string()),
  //   bio: v.optional(v.string()),
  //   photoUrl: v.optional(v.string()),
  //   photoStorageId: v.optional(v.id("_storage")),
  //   postCount: v.number(),
  //   firstSeen: v.string(),
  //   lastSeen: v.string(),
  //   emotionProfile: v.optional(v.string()),   // JSON
  //   monthlyCounts: v.optional(v.string()),    // JSON
  //   topCoOccurrences: v.optional(v.string()), // JSON
  //   aliases: v.optional(v.string()),          // JSON
  // })
  //   .index("by_slug", ["slug"])
  //   .index("by_canonical", ["canonical"])
  //   .index("by_tier", ["tier"]),

  /**
   * Account profiles — creator profiles keyed by @username.
   */
  // {prefix}AccountProfiles: defineTable({
  //   username: v.string(),
  //   displayName: v.optional(v.string()),
  //   slug: v.string(),
  //   tier: v.string(),            // "full" | "chip"
  //   accountType: v.string(),
  //   bio: v.optional(v.string()),
  //   photoUrl: v.optional(v.string()),
  //   photoStorageId: v.optional(v.id("_storage")),
  //   postCount: v.number(),
  //   firstSeen: v.string(),
  //   lastSeen: v.string(),
  //   emotionProfile: v.optional(v.string()),   // JSON
  //   topTopics: v.optional(v.string()),        // JSON
  //   monthlyCounts: v.optional(v.string()),    // JSON
  //   crossCollectionFlags: v.optional(v.string()), // JSON
  // })
  //   .index("by_username", ["username"])
  //   .index("by_slug", ["slug"])
  //   .index("by_tier", ["tier"])
  //   .index("by_type", ["accountType"]),
});
