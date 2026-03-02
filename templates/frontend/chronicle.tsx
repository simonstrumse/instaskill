/**
 * TEMPLATE: Chronicle Page — Three-Level Lazy Loading
 *
 * The chronicle is the core reading experience: editorial prose + all posts
 * organized by chapter → week → post. For large collections (1000+ posts),
 * lazy loading is essential or the browser will crash.
 *
 * Three loading levels:
 * 1. Chapters: First 1-2 eager, rest lazy (600px rootMargin)
 * 2. Weeks within chapters: Each lazy (400px rootMargin)
 * 3. Posts within weeks: Native loading="lazy" on images
 *
 * Data:
 * - Chapters + events from {prefix}Chapters
 * - Chronicle index from {prefix}Analysis (key: "chronicle_index")
 * - Chronicle prose from {prefix}ChronicleContent
 * - Posts loaded per-week via dedicated query
 */

"use client";

import React, { useEffect, useRef, useState, useMemo } from "react";
// import { useQuery } from "convex/react";
// import { api } from "@/convex/_generated/api";

// =========================================================================
// LAZY LOADING HOOK
// =========================================================================

/**
 * Hook: triggers loading when element scrolls into view.
 * Used at both chapter and week level.
 *
 * rootMargin: how far BEFORE the element is visible to start loading.
 * - 600px for chapters (gives time for heavy data)
 * - 400px for weeks (lighter, can load faster)
 */
function useLazyLoad(rootMargin = "400px") {
  const [visible, setVisible] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin: `0px 0px ${rootMargin} 0px` }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [rootMargin]);

  return { ref, visible };
}

// =========================================================================
// CHRONICLE HEADER
// =========================================================================

/**
 * Header prose — the opening lede written by Claude subagent.
 *
 * Design:
 * - font-heading for title
 * - font-body for prose, max-w-[700px] for readability
 * - Accent rule (3px red line) above
 */
function ChronicleHeader({ content }: { content: { body: string } | null }) {
  if (!content) return null;

  return (
    <div className="max-w-[700px] mx-auto mb-12">
      {/* Accent rule */}
      <div className="w-12 h-[3px] bg-[#b5121b] mb-6" />
      <div
        className="font-body text-lg leading-relaxed text-[#1a1a1a]"
        // Prose is markdown — render with dangerouslySetInnerHTML or a markdown renderer
        dangerouslySetInnerHTML={{ __html: content.body.replace(/\n/g, "<br/>") }}
      />
    </div>
  );
}

// =========================================================================
// CHAPTER SECTION
// =========================================================================

/**
 * A single chapter with its intro prose + week groups.
 * Eager for first 1-2 chapters, lazy for the rest.
 */
function ChapterSection({
  chapter,
  intro,
  weeks,
  isEager,
}: {
  chapter: { chapterId: string; title: string; startDate: string; endDate: string };
  intro: { body: string } | null;
  weeks: { week: string; postIds: string[] }[];
  isEager: boolean;
}) {
  const { ref, visible } = useLazyLoad("600px");
  const shouldRender = isEager || visible;

  return (
    <section ref={ref} id={`chapter-${chapter.chapterId}`} className="mb-16">
      {/* Chapter heading */}
      <div className="mb-6">
        <h2 className="font-heading text-2xl">{chapter.title}</h2>
        <div className="font-mono text-xs text-[#6b7280] mt-1">
          {chapter.startDate} → {chapter.endDate}
        </div>
      </div>

      {/* Chapter intro prose */}
      {shouldRender && intro && (
        <div className="max-w-[700px] mb-8">
          <div
            className="font-body text-base leading-relaxed text-[#1a1a1a]"
            dangerouslySetInnerHTML={{ __html: intro.body.replace(/\n/g, "<br/>") }}
          />
        </div>
      )}

      {/* Week groups */}
      {shouldRender && (
        <div className="space-y-8">
          {weeks.map((week) => (
            <WeekGroup key={week.week} week={week.week} postIds={week.postIds} />
          ))}
        </div>
      )}

      {/* Loading placeholder */}
      {!shouldRender && (
        <div className="h-[200px] bg-[#f5f5f5]" style={{ borderRadius: "3px" }} />
      )}
    </section>
  );
}

// =========================================================================
// WEEK GROUP
// =========================================================================

/**
 * A week within a chapter. Lazy-loaded with 400px rootMargin.
 * Shows the week label + post cards.
 */
function WeekGroup({ week, postIds }: { week: string; postIds: string[] }) {
  const { ref, visible } = useLazyLoad("400px");

  // Query posts for this week only when visible
  // const posts = useQuery(
  //   api.posts.getPostsByIds,
  //   visible ? { postIds } : "skip"
  // );

  return (
    <div ref={ref}>
      <div className="font-mono text-xs text-[#9ca3af] mb-2">{week}</div>
      {visible ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
          {/* {posts?.map((post) => <PostCard key={post.postId} post={post} />)} */}
          {/* Placeholder for post cards */}
          {postIds.slice(0, 8).map((id) => (
            <div
              key={id}
              className="aspect-square bg-[#f5f5f5]"
              style={{ borderRadius: "3px" }}
            />
          ))}
        </div>
      ) : (
        <div
          className="h-[100px] bg-[#f5f5f5]"
          style={{ borderRadius: "3px" }}
        />
      )}
    </div>
  );
}

// =========================================================================
// SIDEBAR
// =========================================================================

/**
 * Sticky sidebar — chapter navigation.
 * Desktop: left sidebar, sticky. Mobile: top date bar, horizontal scroll.
 */
function ChronicleSidebar({
  chapters,
  activeChapter,
}: {
  chapters: { chapterId: string; title: string }[];
  activeChapter: string | null;
}) {
  return (
    <nav className="sticky top-[60px] hidden md:block w-[200px] shrink-0">
      <div className="space-y-1">
        {chapters.map((ch) => (
          <a
            key={ch.chapterId}
            href={`#chapter-${ch.chapterId}`}
            className={`block text-sm py-1 px-2 rounded-[3px] no-underline transition-colors ${
              activeChapter === ch.chapterId
                ? "bg-[#f5f5f5] text-[#1a1a1a]"
                : "text-[#6b7280] hover:text-[#1a1a1a]"
            }`}
          >
            {ch.title}
          </a>
        ))}
      </div>
    </nav>
  );
}

// =========================================================================
// MAIN PAGE
// =========================================================================

/**
 * Chronicle page — full scrollable timeline.
 *
 * Query pattern:
 *   const chapters = useQuery(api.{prefix}.list{Prefix}Chapters);
 *   const chronicleContent = useQuery(api.{prefix}.list{Prefix}ChronicleContent);
 *   const chronicleIndex = useQuery(api.{prefix}.get{Prefix}Analysis, { key: "chronicle_index" });
 */
export default function ChroniclePage() {
  // const chapters = useQuery(api.{prefix}.list{Prefix}Chapters);
  // const content = useQuery(api.{prefix}.list{Prefix}ChronicleContent);
  // const index = useQuery(api.{prefix}.get{Prefix}Analysis, { key: "chronicle_index" });

  // const header = content?.find((c) => c.contentType === "header");
  // const epilogue = content?.find((c) => c.contentType === "epilogue");
  // const chapterIntros = Object.fromEntries(
  //   (content ?? [])
  //     .filter((c) => c.contentType === "chapter_intro")
  //     .map((c) => [c.chapterId, c])
  // );

  return (
    <div className="max-w-[1200px] mx-auto px-4 py-8" style={{ background: "#fafaf8" }}>
      {/* Header prose */}
      {/* <ChronicleHeader content={header} /> */}

      {/* Two-column: sidebar + content */}
      <div className="flex gap-8">
        {/* Sidebar */}
        {/* <ChronicleSidebar chapters={chapters ?? []} activeChapter={null} /> */}

        {/* Main content */}
        <div className="flex-1 min-w-0">
          {/* Chapter sections — first 2 eager, rest lazy */}
          {/* {chapters?.map((ch, i) => (
            <ChapterSection
              key={ch.chapterId}
              chapter={ch}
              intro={chapterIntros[ch.chapterId]}
              weeks={index?.chapters?.[i]?.weeks ?? []}
              isEager={i < 2}
            />
          ))} */}
        </div>
      </div>

      {/* Epilogue */}
      {/* {epilogue && (
        <div className="max-w-[700px] mx-auto mt-16">
          <div className="text-center text-[#9ca3af] my-8">· · ·</div>
          <div
            className="font-body text-lg leading-relaxed text-[#1a1a1a]"
            dangerouslySetInnerHTML={{ __html: epilogue.body.replace(/\n/g, "<br/>") }}
          />
        </div>
      )} */}
    </div>
  );
}
