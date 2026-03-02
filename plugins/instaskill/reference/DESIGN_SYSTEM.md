# Design System

Editorial data journalism aesthetic. Not SaaS dashboards, not vintage newspaper.

**North stars:** ProPublica, The Pudding, Bloomberg Businessweek.

---

## Typography

### Fonts
| Role | Font | CSS Variable | Usage |
|------|------|-------------|-------|
| Headings | DM Serif Display | `--font-heading` | Page titles, chapter headings, section headers |
| Body | IBM Plex Sans | `--font-body` | Paragraphs, descriptions, UI labels |
| Data | IBM Plex Mono | `--font-mono` / `.font-data` | Numbers, dates, statistics, code |

### Scale
```css
--text-xs: 0.75rem;    /* 12px — captions, labels */
--text-sm: 0.875rem;   /* 14px — secondary text */
--text-base: 1rem;     /* 16px — body text */
--text-lg: 1.125rem;   /* 18px — lead paragraphs */
--text-xl: 1.25rem;    /* 20px — section headers */
--text-2xl: 1.5rem;    /* 24px — page subtitles */
--text-3xl: 1.875rem;  /* 30px — page titles */
--text-4xl: 2.25rem;   /* 36px — hero numbers */
```

---

## Colors

### Core Palette
| Token | Value | Usage |
|-------|-------|-------|
| Background | `#fafaf8` | Warm paper — NOT pure white |
| Surface | `#ffffff` | Cards, panels |
| Accent | `#b5121b` | Structural red — sidebar borders, pull quote marks, InsightPanel |
| Text primary | `#1a1a1a` | Headings, body |
| Text secondary | `#6b7280` | Captions, metadata |
| Text tertiary | `#9ca3af` | Disabled, placeholder |
| Border | `#e5e5e5` | Card borders, dividers |
| Border hover | `#d1d5db` | Hover state borders |

### Semantic Colors
Use sparingly. These are for data visualization, not decoration:
```css
--color-anger: #dc2626;
--color-joy: #f59e0b;
--color-sadness: #3b82f6;
--color-fear: #8b5cf6;
--color-surprise: #10b981;
--color-disgust: #6b7280;
--color-neutral: #9ca3af;
```

---

## Spacing & Layout

### Corners
**3px everywhere.** No exceptions.
```css
border-radius: 3px;
/* Set via .app-card class or inline rounded-[3px] */
```

Never use `rounded-lg`, `rounded-xl`, `rounded-2xl`, or `rounded-full` on content cards.

### Shadows
**None.** Use borders only:
```css
/* WRONG */
box-shadow: 0 1px 3px rgba(0,0,0,0.1);

/* RIGHT */
border: 1px solid #e5e5e5;
```

### Hover States
Border color transition only. No bounce, no scale, no blur:
```css
.card {
  border: 1px solid #e5e5e5;
  transition: border-color 150ms ease;
}
.card:hover {
  border-color: #d1d5db;
}
```

### Section Breaks
```css
/* Centered dots */
.section-break::after {
  content: "· · ·";
  display: block;
  text-align: center;
  color: #9ca3af;
  margin: 2rem 0;
}

/* Accent rule — 3px red line */
.accent-rule {
  width: 48px;
  height: 3px;
  background: #b5121b;
}
```

---

## Components

### MetricCard
```
┌─────────────────────┐
│ LABEL          font-data │
│ 1,234              │
│ +12% vs prev       │
└─────────────────────┘
```
- 3px border radius, 1px border
- Label in caps, `font-mono`, text-xs, text-secondary
- Value in `font-heading`, text-3xl
- Delta in text-sm, green/red for positive/negative

### InsightPanel
```
┌──┬──────────────────┐
│▌ │ Insight title     │
│▌ │ Body text here... │
│▌ │                   │
└──┴──────────────────┘
```
- 3px left border in accent red (`#b5121b`)
- Background: surface white
- Title in `font-heading`, body in `font-body`

### EntityChip
```
┌──────────────┐
│ Person Name  │
└──────────────┘
```
- Inline pill, 3px radius
- Background: `#f5f5f5`, border: `#e5e5e5`
- Clickable: navigates to person profile page
- Same navigation pattern for both EntityChip and AccountChip

### PageCard
```
┌─────────────────────┐
│ 📊  Page Title      │
│ Short description   │
│ of what this page   │
│ shows.              │
└─────────────────────┘
```
- Icon + title in `font-heading`
- Description in `font-body`, text-sm, text-secondary
- Click → navigates to page
- Grid layout: 2 columns on desktop, 1 on mobile

---

## Charts

### Library
Recharts for standard charts (bar, line, area). Plotly for UMAP galaxy views (3D scatter).

### Chart Style
```typescript
// Recharts defaults
const chartConfig = {
  strokeWidth: 1.5,
  dot: false,                    // No dots on line charts
  animationDuration: 300,
  grid: { strokeDasharray: "3 3", stroke: "#e5e5e5" },
  axis: { fontSize: 12, fontFamily: "var(--font-mono)" },
};
```

- No gradient fills — use solid colors at 20% opacity for area charts
- Axis labels in `font-mono`
- Tooltips: white background, 1px border, 3px radius (no shadow)

---

## Page Structure

### Landing Page
```
Hero (sparkline + headline)
─────────────────────────
Metric grid (6-8 cards)
─────────────────────────
Chapter overview cards
─────────────────────────
Page grid (links to all pages)
─────────────────────────
About section
```

### Analytical Page
```
Page header (title + description)
─────────────────────────
Filter bar (optional)
─────────────────────────
Primary visualization
─────────────────────────
· · · (section break)
─────────────────────────
Secondary content
─────────────────────────
Insights panel (if applicable)
```

### Chronicle Page
```
Chronicle header + prose
─────────────────────────
Sticky sidebar (chapters)
─────────────────────────
Chapter sections
  └─ Week groups
      └─ Post cards (lazy loaded)
```

---

## Responsive

- **Desktop:** Max-width 1200px, centered
- **Tablet:** Single column, full width with padding
- **Mobile:** Stack everything, reduce font scale by 1 step

Navigation collapses to hamburger on mobile. Chronicle sidebar becomes a top date bar.

---

## Anti-Patterns

Do NOT:
- Add shadows to cards
- Use rounded corners > 3px
- Add hover animations (scale, bounce, blur)
- Use gradient backgrounds
- Put emoji in headings (unless the user requests it)
- Use SaaS-style progress bars or gauges
- Add decorative illustrations
- Use loading skeletons with shimmer animations — use simple gray placeholders
