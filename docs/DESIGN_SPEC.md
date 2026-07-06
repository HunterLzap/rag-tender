# RAG-Tender Assistant — Lightweight Visual Specification (v1)

Scope: this is not a rebrand. It keeps your existing purple identity and MUI v5 stack, and fixes the three concrete problems from the review: inconsistent card/table treatment across pages, an overloaded tag system, and low scannability on dense tables. Every token below maps directly to `theme.ts`.

---

## 1. Color System

### 1.1 Primary (brand)
| Token | Hex | Usage |
|---|---|---|
| `primary.main` | `#7C5CFC` | Primary buttons, active nav item, links, focus ring |
| `primary.light` | `#9B81FF` | Hover states, selected row tint (at 8% opacity) |
| `primary.dark` | `#5B3FD1` | Pressed states |

> Assumption: sampled from your existing header/nav purple. Swap the hex if your actual brand token differs — everything else derives from this one value.

### 1.2 Status colors (semantic, data state only)
| Token | Hex (text) | Hex (bg, 8%) | Meaning | Do NOT use for |
|---|---|---|---|---|
| `success` | `#1B8A5A` | `#E7F6EE` | 已完成 / 通过 / 符合 | mandatory level, category |
| `info` | `#2E6ADE` | `#E9F0FD` | 已解析 / 进行中 / 匹配中 | action reminders |
| `error` | `#C4362E` | `#FBEAE9` | 不通过 / 失败 / 不符合 | warnings that aren't failures yet |
| `neutral` | `#5B5F6B` | `#EEEFF2` | 待处理 / 未开始 / 草稿 | — |

### 1.3 Warning vs. Mandatory — the fix for your biggest tag conflict
These were both "orange" before, which is why they read as the same signal. They now get **different colors entirely**:

| Token | Hex | Meaning | Used only by |
|---|---|---|---|
| `warning` (action reminder) | `#B5750A` on `#FDF1DD` | "A human needs to do something now" — 需确认 / 需复核 / 待办 | Action Reminder Tag |
| `mandatory` | `#1F2430` on `#E7E8EC` | "This is a rule attribute, not a task" — 硬性 / 严格 | Mandatory Level Tag |

Mandatory is dark neutral, not orange — it describes the *nature* of a requirement, it never means "act now." Only the amber warning color means "act now." This single split resolves the ambiguity flagged in your original message.

### 1.4 Disabled & structure
| Token | Hex | Usage |
|---|---|---|
| `disabled.text` | `#9CA0AB` | Disabled text/icons, placeholder text |
| `disabled.bg` | `#F2F3F5` | Disabled field/button background |
| `divider` | `#E4E5EA` | Table borders, card borders, section rules |
| `background.default` | `#F5F5F7` | Page canvas |
| `background.paper` | `#FFFFFF` | Cards, table surface |
| `surfaceAlt` | `#FAFAFB` | Zebra stripe (see §5) |

---

## 2. Typography Scale

One scale, used identically on every page — this is what makes the dashboard and the dense table pages feel like the same product.

| Token | Size / Weight | Usage |
|---|---|---|
| `h1` | 28 / 700 | Reserved — not currently needed (no page needs two titles) |
| `h2` | 22 / 700 | Page title only (one per page: "标书解析与需求确认", "规则库"...) |
| `h3` | 17 / 600 | Card/section titles, drawer titles |
| `subtitle1` | 14 / 600 | Table column headers, stat card labels |
| `body1` | 14 / 400 | Default body text, table cell primary content |
| `body2` | 13 / 400 | Table cell secondary content, dense contexts |
| `caption` | 12 / 400, color `text.secondary` | Timestamps, IDs, helper text, hash/filename subtext |
| `button` | 14 / 600, no uppercase | All buttons |

Rule: **one page title (`h2`) per screen.** Currently the dashboard hero and every other page's plain title are visually unrelated — under this scale they become the same `h2`, just without the gradient banner (see §4).

---

## 3. Spacing System

Base unit stays MUI's default `theme.spacing(1) = 8px` — no need to reconfigure, just use it consistently instead of ad hoc padding values.

| Token | Value | Usage |
|---|---|---|
| `spacing(0.5)` | 4px | Icon-to-label gap inside a chip/button |
| `spacing(1)` | 8px | Compact table cell vertical padding, tight stacks |
| `spacing(1.5)` | 12px | Table cell horizontal padding |
| `spacing(2)` | 16px | Card inner padding, gap between filter controls |
| `spacing(3)` | 24px | Gap between major sections on a page |
| `spacing(4)` | 32px | Page-level top margin below header |
| `spacing(6)` | 48px | Empty-state vertical padding |

Rule: never hand-write `px` in `sx`. Always `theme.spacing(n)` so a future global density change is a one-line edit.

---

## 4. Component Styles

### Cards
- Border: `1px solid divider`, **no box-shadow** (shadow + border together is what makes the current dashboard cards and matching-detail cards look like two different systems — pick border-only).
- Radius: `10px`.
- Padding: `spacing(2.5)`.
- Stat cards: label in `subtitle1` + `text.secondary`, value uses `h2`'s *visual* size/weight but must render as `<Typography variant="h2" component="p">` (or another non-heading element) — never a literal second `<h2>` tag. A page must have exactly one real `<h2>` in the DOM: the page title. Value color is semantic only if the number itself is a status (e.g., 待处理 count in warning color); otherwise it stays `text.primary`.

### Tables
See §5 for density and §7 for row-level rules. Header row: `surfaceAlt` background, `subtitle1` weight, no bold-black — headers should be quieter than data.

### Tags — see §6, full redesign.

### Buttons
- Primary action per page: 1 filled `primary` button, top-right, e.g. "按新分类重新解析", "自动填写".
- Secondary actions: `outlined`, never more than 2 per toolbar.
- Row-level actions: `IconButton size="small"`, always wrapped in `Tooltip` (see §7.6), never bare.
- Destructive row action (delete): visually separated from edit/confirm by an 8px gap plus a subtle `divider`-colored vertical rule, and colored `text.secondary` at rest — it only turns `error.main` on hover. This directly fixes the "delete sits right next to edit" mis-click risk flagged earlier.

---

## 5. Table Density Specification

Two densities, used consistently by content type — not by page:

| Density | Row height | Cell padding | Font | Use on |
|---|---|---|---|---|
| **Compact** | 40px | `6px 12px` | `body2` (13px) | High-row-count tables: 标书解析需求列表 (22+ rows), 规则库, 资质库 file list |
| **Comfortable** | 52px | `12px 16px` | `body1` (14px) | Low-row-count summary tables: 匹配结果汇总, 最近标书 |

Implementation: `<Table size="small">` for compact, default `<Table>` for comfortable — don't hand-tune row height per page.

---

## 6. Tag System Redesign

This is the core structural fix. Four tag families, each with a dedicated shape/color/purpose so no two meanings ever look alike.

| Family | Component | Shape | Color rule | Example labels |
|---|---|---|---|---|
| **Document Category** | `<CategoryTag>` | Outlined, rounded 6px | One fixed hue per category (see table below), always outlined never filled | 提交件 / 资质 / 业绩 / 财务 / 人员 / 产品参数 / 其他 |
| **Status** | `<StatusTag>` | Filled, rounded 6px, small leading dot/icon | success / info / error / neutral only — never warning amber | 已完成 / 已解析 / 待确认(未开始) / 不通过 |
| **Mandatory Level** | `<MandatoryTag>` | Filled square-ish (2px radius), bookmark icon, dark neutral | Always `#1F2430` on `#E7E8EC` — one fixed look, it's an attribute not a state | 硬性 / 软性 |
| **Action Reminder** | `<ActionTag>` | Filled pill, warning icon, amber | Always `#B5750A` on `#FDF1DD` — the *only* tag family allowed to use amber | 需确认 / 需复核 / 待办 |

### 6.1 Category → color map (fixed, used everywhere)
| Category | Hex |
|---|---|
| 提交件 | `#5B4FE9` |
| 资质 | `#2E6ADE` |
| 业绩 | `#1B8A5A` |
| 财务 | `#795548` *(originally spec'd as `#B5750A`, identical to the warning amber — corrected, since §6.3 requires amber to be exclusive to Action Reminder tags)* |
| 人员 | `#C4362E` |
| 产品参数 | `#0E8C8C` |
| 其他 | `#5B5F6B` |

### 6.2 Before → After mapping
| Old usage | Old look | New component | Why it's clearer |
|---|---|---|---|
| 类别 pill (提交件/其他/财务, two-line "提交件 / 提交材料") | small purple/gray pill, 2 lines | `<CategoryTag>`, 1 line, category only | Sub-category folded into the requirement text itself, not a second tag |
| 硬性 pill next to requirement | orange outline pill, same visual weight as status | `<MandatoryTag>` | Dark, square, never confused with "needs action" |
| 需确认 (row status) | orange pill | `<ActionTag>` if it's a to-do; `<StatusTag neutral>` if it's just "not yet reviewed" | Splits "nothing's wrong, just pending" from "you need to act" |
| 已完成 / 已解析 | green pill | `<StatusTag success>` / `<StatusTag info>` | Same family, consistent shape |
| API 配置 provider labels (通义千问, DeepSeek) | pill, same style as everything else | Plain `Chip variant="outlined" color="default"` — explicitly **not** part of the 4-family system | Config labels aren't data state; don't borrow status/category color language |

### 6.3 Hard rules
1. Amber (`#B5750A`) appears **only** on Action Reminder tags. If you're tempted to use it elsewhere, that's a signal the thing you're tagging is actually an action reminder.
2. A single cell shows **at most one tag per family**. If a row is both "硬性" and "需确认," that's two tags side by side (Mandatory + Action), never stacked as 3 lines of text like the current matching-detail panel.
3. Category color is fixed per category, everywhere in the app — the same 财务 chip color on the requirement table, the qualification library, and settings.

---

## 7. Table Optimization Rules

**7.1 Zebra striping — yes, on compact tables only.**
Compact tables (≥15 rows) get `surfaceAlt` (`#FAFAFB`) on odd rows via `MuiTableRow` theme override — this is what actually lets the eye track a row across 8 columns, more than borders alone. Comfortable tables (≤10 rows, e.g. 匹配结果汇总) skip zebra striping — at low row counts it adds noise without aiding scanning.

**7.2 Long text collapse.**
Any cell holding a sentence-length value (requirement description, 规则说明, 命中动作) uses a 2-line `-webkit-line-clamp` with `text-overflow: ellipsis`, wrapped in a `Tooltip` showing the full text on hover. Full text is never lost — it's one hover or one click (drawer) away, never forced into the row height.

**7.3 Keyword tags inside a cell.**
Never let a cell's height vary with how many keyword chips exist. Show the first 3 `CategoryTag`-style chips, then a single `+N` overflow chip. Clicking `+N` opens a small `Popover` listing the rest. This is what fixes the uneven row heights in 规则库's 关键词 column.

**7.4 Long filename truncation.**
Rule: `middle-ellipsis`, not end-ellipsis — for hashed filenames like `完税证明f91a7f89f4f34d53a18d187630962c99.pdf`, an end-ellipsis (`完税证明f91a7f89f4f...`) hides the extension and looks broken; middle-ellipsis (`完税证明f91a7...962c99.pdf`) keeps both the readable prefix and the extension visible. Full filename always in a `Tooltip`. Cap displayed length at ~28 characters.

**7.5 Inline action button layout.**
Order left → right: view/edit actions (neutral `text.secondary` icons) → confirm/primary action (`primary` or `success` colored icon) → 8px gap + thin divider → delete (`text.secondary` at rest, `error.main` on hover only). Never place delete adjacent to confirm with no separation — that's the current mis-click risk.

**7.6 Tooltip text for icon-only buttons.**
Every icon button gets a `Tooltip` with a verb-first label, matching the action's own name (see §4 writing rule — the label stays consistent everywhere that action appears):

| Icon | Tooltip text |
|---|---|
| Pencil | "编辑" |
| Checkmark | "确认无误" |
| Trash | "删除" |
| Refresh/circular-arrow | "重新解析" (data-analysis context) |
| Power | "启用" / "停用" (state-dependent, never just "Power") |
| Eye | "查看详情" |
| Download/export icon | "导出检查报告" |

---

## 8. Priority List

| Priority | Item | Pages affected | Effort | Impact |
|---|---|---|---|---|
| P0 | Ship `theme.ts` (colors, type scale, spacing, MuiTableCell/Row/Chip overrides) | All | Low | High — single change fixes cross-page inconsistency |
| P0 | Tag system redesign (§6) | 标书解析, 匹配结果, 错例库, 规则库 | Medium | High — resolves the core "what does this color mean" confusion |
| P0 | Requirement Confirmation table revamp | 标书解析与需求确认 | Medium | High — heaviest-traffic dense page |
| P1 | Rule Library table revamp (keyword overflow, description drawer) | 规则库 | Medium | High |
| P1 | Icon button tooltips + destructive-action spacing (§7.5, §7.6) | All pages with row actions | Low | Medium — quick win, prevents mis-clicks |
| P1 | Filename middle-ellipsis + tooltip | 资质库 | Low | Medium |
| P2 | Dashboard hero banner → same `h2` header used elsewhere (drop the one-off gradient) | 仪表盘 | Low | Medium — cross-page consistency |
| P2 | Matching-detail slide-over: consolidate 3-line status stack into 1 line + drawer | 匹配结果 / 匹配明细 | Medium | Medium |
| P3 | Settings API config chips: switch to neutral `Chip` (out of the 4-tag system) | 设置 | Low | Low |

---

## 9. Page Revamp — Requirement Confirmation (标书解析与需求确认)

**Before:** 2-line category+subcategory pill, 硬性 badge same weight as status, 22-row table with no zebra striping, bare icon actions with delete adjacent to confirm, long requirement text wraps and pushes row height around.

**After (see `RequirementConfirmationPage.tsx`):**
- Single-line `CategoryTag` (category only — subcategory folded into the requirement label).
- `MandatoryTag` (硬性/软性) as its own dedicated dark tag, separate from status.
- `StatusTag` for 解析状态, using neutral (not amber) for "待确认" since it's a pending state, not a to-do — `ActionTag` reserved for genuinely blocking items.
- Compact density (40px rows), zebra striping.
- Requirement text: bold title + 2-line clamped description + tooltip for full text.
- Action column: view (原文页码 link) → edit → confirm, gap + divider, then delete — all wrapped in tooltips.
- Segmented filter (全部/能力要求/提交资料) as `ToggleButtonGroup` instead of plain tab-like buttons, so selection state is visually unambiguous.

## 10. Page Revamp — Rule Library (规则库)

**Before:** 关键词 column wraps many chips causing uneven row height, 规则说明 full paragraph inline, 严格度 tag same red-outline style with no relation to the rest of the tag system, 详情 as a plain text link.

**After (see `RuleLibraryPage.tsx`):**
- Keyword chips capped at 3 + `+N` overflow popover — fixed row height regardless of keyword count.
- 规则说明 and full 命中动作 text moved to a `Drawer` opened via a dedicated "详情" icon button with tooltip; table shows only a 1-line clamped summary.
- 严格度 becomes a `MandatoryTag`-style dark tag (严格/一般) so it visually pairs with the same "attribute, not status" language used on the requirement page — one mental model across the app.
- Zebra striping + compact density, matching §5.

---

## 11. File manifest

| File | Contents |
|---|---|
| `theme.ts` | MUI v5 `createTheme()` — palette, typography, spacing, component overrides (Button/Chip/Card/Table/Tooltip) |
| `StatusTags.tsx` | `<CategoryTag>`, `<StatusTag>`, `<MandatoryTag>`, `<ActionTag>` — the 4-family tag system from §6 |
| `RequirementConfirmationPage.tsx` | Revamped 标书解析与需求确认 table (§9) |
| `RuleLibraryPage.tsx` | Revamped 规则库 table (§10), including keyword overflow popover and detail drawer |

Wrap your app root in `<ThemeProvider theme={theme}>` (with `<CssBaseline />`) and these four files drop in with only your real data-fetching swapped in for the sample data.
