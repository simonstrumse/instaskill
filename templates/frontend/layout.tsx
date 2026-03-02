/**
 * TEMPLATE: Route Group Layout
 *
 * Each deep dive gets its own route group in Next.js: (your-collection)/
 * This layout provides navigation and wraps all pages in the collection.
 *
 * Pattern:
 * - Fixed top navigation with collection name + page links
 * - Main content area with padding-top to clear the fixed nav
 * - Navigation highlights the current page
 *
 * Replace:
 * - "YourCollection" with your collection name
 * - "/your-collection" with your route prefix
 * - Page links with your actual pages
 */

// "use client"; // Uncomment if navigation uses hooks

import React from "react";
// import Link from "next/link";
// import { usePathname } from "next/navigation";

/**
 * Navigation component — fixed top bar with page links.
 *
 * Design system:
 * - Background: white, bottom border only (no shadow)
 * - Font: var(--font-body) for links, var(--font-heading) for collection name
 * - Top accent: 3px red line (var(--color-accent) = #b5121b)
 * - Active page: text-primary + bottom border indicator
 */
// function CollectionNavigation() {
//   const pathname = usePathname();
//
//   const pages = [
//     { href: "/your-collection", label: "Overview" },
//     { href: "/your-collection/chronicle", label: "Chronicle" },
//     { href: "/your-collection/people", label: "People" },
//     { href: "/your-collection/timeline", label: "Timeline" },
//     // Add collection-specific pages here
//   ];
//
//   return (
//     <nav
//       className="fixed top-0 left-0 right-0 z-50 bg-white"
//       style={{ borderTop: "3px solid #b5121b", borderBottom: "1px solid #e5e5e5" }}
//     >
//       <div className="max-w-[1200px] mx-auto px-4 flex items-center h-[50px] gap-6">
//         <Link
//           href="/your-collection"
//           className="font-heading text-lg text-primary shrink-0"
//         >
//           YourCollection
//         </Link>
//         <div className="flex gap-4 overflow-x-auto">
//           {pages.map((page) => {
//             const isActive =
//               pathname === page.href ||
//               (page.href !== "/your-collection" && pathname?.startsWith(page.href));
//             return (
//               <Link
//                 key={page.href}
//                 href={page.href}
//                 className={`text-sm whitespace-nowrap py-1 border-b-2 transition-colors ${
//                   isActive
//                     ? "border-[#b5121b] text-[#1a1a1a]"
//                     : "border-transparent text-[#6b7280] hover:text-[#1a1a1a]"
//                 }`}
//               >
//                 {page.label}
//               </Link>
//             );
//           })}
//         </div>
//       </div>
//     </nav>
//   );
// }

/**
 * Layout wrapper — applies navigation + main content area.
 *
 * Key: pt-[53px] accounts for the fixed nav height (50px + 3px top border).
 * IMPORTANT: Never use dynamic positioning (scrollY) with fixed elements.
 */
export default function CollectionLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div>
      {/* <CollectionNavigation /> */}
      <main id="main-content" className="pt-[53px]">
        {children}
      </main>
    </div>
  );
}
