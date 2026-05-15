# Design Improvement: Canvas Agent Icons & Table Objects

**Date:** 2026-05-15  
**Screen:** Canvas entities — agents and room objects

---

## TL;DR

Three ready-to-implement variants for how agents and tables look on the canvas. **Variant A** (Glowing Avatar) is the highest-impact change — agents get a person silhouette icon and stronger depth cues; objects get a colored header stripe for instant type recognition. All three share the same Canvas 2D API and slot into the existing `drawAgent()` / `drawObject()` functions.

---

## Current State

```
Agents:
   ╭────╮   ● sc  ← 4px state dot, white border
   │AGT1│         ← bold 8px ID label
   ╰────╯
    Alpha          ← 11px name below

   • r = 15 filled circle, a.color fill, soft glow, white highlight arc
   • "AGENT1" text centered inside (8px)
   • State dot top-right corner
   • Speech bubble above when active

Tables:
   ┌──────────────┐
   │  TABLE 1     │  ← 10px label, centered vertically (or upper half)
   │  (research)  │  ← 8px task chip, lower half
   └──────────────┘
   • Dark fill #1E1E28, 1.5px colored border, r=8
   • Agents-here badge: purple circle top-right
```

---

## Variants

---

### Variant A — Glowing Avatar  ⭐ (recommended)

**What changes:**

**Agents:**
- Body increases to r=17 for slightly more presence
- Replace the flat circle with a two-tone "avatar" look: dark inner ring (r=11) separates a colored outer rim from a dark center
- Draw a small person silhouette (head + shoulders arc) in the center instead of the text ID
- Agent's first letter (large, 14px, semi-transparent) replaces the tiny "AGENT1" text — readable at a glance
- State dot becomes r=5 with a thicker white border (2px) for crispness
- Moving state: dual concentric pulse rings (r+6 and r+9), the outer ring is 40% opacity

```
Before:               After:
                      ╭──────────────╮
  ╭────╮              ║  ╭──────╮    ║   ← outer rim = a.color (r=17)
  │AGT1│     →        ║  │  ⬤   │    ║   ← dark center (r=11, #1C1C22)
  ╰────╯              ║  │ /◡\  │    ║   ← person silhouette
   Alpha              ║  ╰──────╯    ║
                      ╰──────────────╯   ● sc
                           Alpha          ← 12px name, slightly brighter
```

**Objects:**
- Add a colored header bar: top 20% of the rect fills with `s.stroke + "25"` (tinted, very subtle)
- Type icon (4-char emoji: "🖥" "💺" "📦" "🚪") drawn at 14px in the header bar, left-aligned
- Label moves to the bottom 60% of the rect, left-aligned with 8px padding for better readability
- Border radius increases to r=10, border weight to 2px
- Agents-here badge: switches from solid purple circle to a colored pill (height 12px) with a count inside

```
Before:                 After:
┌──────────────┐        ┌──────────────┐
│              │        │ 🖥  header  │  ← tinted strip + emoji icon
│  TABLE 1     │   →    ├ ─ ─ ─ ─ ─ ─ ┤  ← subtle divider line
│  (research)  │        │  TABLE 1    │  ← label
└──────────────┘        │  research   │  ← task chip
                        └──────────────┘
```

**Implementation (key changes):**

```javascript
// drawAgent changes:
const r = 17;
// Outer rim
ctx.fillStyle = a.color; ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI*2); ctx.fill();
// Dark center
ctx.fillStyle = "#1C1C22"; ctx.beginPath(); ctx.arc(x, y, r-5, 0, Math.PI*2); ctx.fill();
// Person silhouette head
ctx.fillStyle = a.color + "CC";
ctx.beginPath(); ctx.arc(x, y-3, 4, 0, Math.PI*2); ctx.fill();
// Shoulders arc
ctx.beginPath(); ctx.arc(x, y+8, 6, Math.PI, 0); ctx.fill();

// drawObject changes:
const headerH = Math.floor(o.h * 0.28);
ctx.fillStyle = s.stroke + "20";
rrect(o.x, o.y, o.w, headerH, [10,10,0,0]); ctx.fill(); // top rounded only
ctx.strokeStyle = s.stroke + "30"; ctx.lineWidth = 1;
ctx.beginPath(); ctx.moveTo(o.x, o.y+headerH); ctx.lineTo(o.x+o.w, o.y+headerH); ctx.stroke();
```

---

### Variant B — Geometric Badge

**What changes:**

**Agents:**
- Body stays circular (r=15) but the outer stroke becomes a bold ring: 2.5px, colored, always visible (not just on hover/state)
- Flat colored fill changes to a radial gradient — center 15% lighter than edge
- Instead of the text "AGENT1", draw the agent's **index number** large (16px bold) in white — clean, minimal, like a sports jersey
- State indicator moves from a dot to a thin arc segment in the lower-right quadrant (135°–270°), colored by state
- Moving: the arc segment animates (rotates), showing speed

```
Before:               After:
  ╭────╮              ╭────╮   ← bold 2.5px ring, a.color
  │AGT1│     →        │  1 │   ← large index number (16px bold)
  ╰────╯              ╰────╯
                       ╰── state arc on lower-right edge
   Alpha                  Alpha
```

**Objects:**
- Replace border with a **left accent stripe**: a 3px vertical bar on the left edge, colored by type
- Fill brightens slightly: `s.fill` blends toward the stroke color at 8% opacity
- Label becomes left-aligned with the accent stripe as a visual anchor
- Object type abbreviation in a tiny badge (top-right): "TBL", "PC", "CHR" — muted, small

```
Before:                 After:
┌──────────────┐        ▌──────────────┐  ← 3px accent stripe
│  TABLE 1     │   →   ▌  TABLE 1  TBL │  ← label left-aligned + type badge
│  (research)  │       ▌  research     │
└──────────────┘        ──────────────┘
```

**Implementation (key changes):**

```javascript
// drawAgent changes:
const grad = ctx.createRadialGradient(x-3, y-3, 1, x, y, r);
grad.addColorStop(0, lighten(a.color, 0.25));
grad.addColorStop(1, a.color);
ctx.fillStyle = grad;
ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI*2); ctx.fill();
ctx.strokeStyle = a.color; ctx.lineWidth = 2.5;
ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI*2); ctx.stroke();
// Index number
const idx = parseInt(a.id.replace(/\D/g, '')) || 1;
ctx.fillStyle = "#fff"; ctx.font = "bold 16px 'Inter', sans-serif";
ctx.fillText(idx, x, y + 1);

// drawObject changes:
// Accent stripe
ctx.fillStyle = s.stroke; ctx.fillRect(o.x, o.y + 8, 3, o.h - 16);
// Label left-aligned
ctx.textAlign = "left";
ctx.fillText(o.label || o.id, o.x + 12, cy);
```

---

### Variant C — Minimal Dot Grid (isometric-inspired)

**What changes:**

**Agents:**
- Agents become **octagon** shapes (8-sided polygon, r=15) — more distinctive, clearly "entity" not "button"
- Fill is very dark (close to canvas background, #222228), outline is a.color at 2px
- A 3×3 dot grid (6px spacing) replaces the text label — each dot colored by agent state
- No glow shadow by default; instead a very thin outer halo ring (r+1, 30% opacity) on hover/selected
- Speech bubble style stays the same

```
Before:               After:
  ╭────╮              ⬡────⬡   ← octagon outline, a.color
  │AGT1│     →        │ ● ● │   ← 3×3 dot grid, state-colored
  ╰────╯              ⬡────⬡
   Alpha                  Alpha
```

**Objects:**
- Objects get a **corner cut** on top-right: `r=8` normal except top-right is 0 (like a sticky note fold)
- Fill unchanged, but the border adds a dotted top edge: `setLineDash([2, 3])`
- A small "×" dismiss anchor appears bottom-right on hover (would need JS hover detection)
- Objects with tasks show a colored left edge instead of a separate chip

```
Before:                 After:
┌──────────────┐        ┌─────────────╱
│  TABLE 1     │   →    │  TABLE 1    │  ← corner fold top-right
│  (research)  │        ├╌╌╌╌╌╌╌╌╌╌╌╌┤  ← dotted divider
└──────────────┘        │  research   │  ← task below divider
                        └─────────────┘
```

**Implementation (key changes):**

```javascript
// Octagon helper
function octagon(cx, cy, r) {
  ctx.beginPath();
  for (let i = 0; i < 8; i++) {
    const a = (Math.PI/8) + (Math.PI/4)*i;
    i === 0 ? ctx.moveTo(cx + r*Math.cos(a), cy + r*Math.sin(a))
            : ctx.lineTo(cx + r*Math.cos(a), cy + r*Math.sin(a));
  }
  ctx.closePath();
}
// Agent body
ctx.fillStyle = "#222228"; octagon(x, y, r); ctx.fill();
ctx.strokeStyle = a.color; ctx.lineWidth = 2; octagon(x, y, r); ctx.stroke();
// 3×3 dot grid
const dotClr = sc; const sp = 5;
for (let row = -1; row <= 1; row++) for (let col = -1; col <= 1; col++) {
  ctx.fillStyle = (row === 0 && col === 0) ? dotClr : dotClr + "55";
  ctx.beginPath(); ctx.arc(x + col*sp, y + row*sp, 1.5, 0, Math.PI*2); ctx.fill();
}
```

---

## Comparison

| | Variant A (Glowing Avatar) | Variant B (Geometric Badge) | Variant C (Dot Grid) |
|---|---|---|---|
| Agent shape | Circle (r=17) | Circle (r=15, bold ring) | Octagon (r=15) |
| Agent label | Person silhouette + big initial | Large index number | 3×3 dot grid |
| Object change | Header strip + emoji | Left accent stripe | Corner fold + dotted divider |
| Effort | Medium | Low | Medium |
| Mood | Warm, human, Notion-ish | Clean, numeric, sport-jersey | Geometric, techy, blueprint |
| Glow | Yes (softer) | No | No |

---

## What's Working (Keep These)

1. **Per-agent colors** — The `a.color` palette (each agent has its own hue) is the strongest orientation cue. Don't lose this in any variant.
2. **Speech bubble above agent** — The dark `#2C2C32` bubble with colored border tail is the best readability pattern for activity text. Keep in all variants.
3. **Animated moving ring** — The sin-pulse ring on `moving` state reads instantly. Keep it in A and B.
4. **OBJ_STYLE per-type colors** — Purple for table, cyan for computer, amber for chair: this color language already works. Build on it rather than replacing it.
5. **Agents-here badge** — The top-right purple circle with count is simple and works. Variant A refines it to a pill; B and C keep it as-is.
