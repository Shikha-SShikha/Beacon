---
name: excalidraw-diagram
description: Use when someone asks to draw a diagram, make an Excalidraw diagram, or build an editable diagram. Default for all diagram requests.
---

## Visual Style

These diagrams use a **dark chalkboard aesthetic**: deep navy background, white handwritten text, vivid rounded boxes in a consistent color palette, emoji icons inside nodes, and sketch-style arrows with small annotation labels.

Reference look: think "YouTube explainer slide" — bold, visual, immediately readable, not a corporate org chart.

---

## Workflow

### Step 1: Understand the request
Before generating anything, make sure you know:
- What concept or system are they diagramming?
- What are the major components or sections?
- What is the flow or relationship between them?

If the request is vague (e.g., "make a diagram of Docker"), ask 1-2 clarifying questions:
- What specific aspect? (architecture, networking, volumes, etc.)
- What level of detail? (high-level overview vs. detailed internals)

### Step 2: Research if needed
If you're not confident about the technical accuracy of the concept, research it before diagramming. Verify:
- Correct component names and relationships
- Proper hierarchy and nesting
- Accurate data flow direction

### Step 3: Plan the layout
Before writing any JSON, sketch the layout mentally:
- What are the major sections? (left-to-right or top-to-bottom)
- What is nested inside what?
- What arrows connect what?

Write down the section plan:
```
[Section A: w=170] --60px gap-- [Section B: w=170] --60px gap-- [Section C: w=640]
```

### Step 4: Assign colors and icons
Each logical role gets one color. Pick an emoji icon that represents each node.

Common icon assignments:
- AI/Claude: `✳️` or `🤖`
- Agent: `🤖`
- Tool/Script: `⚙️`
- Database: `🗄️`
- Document/File: `📄`
- API/Network: `☁️`
- Auth/Security: `🔑`
- Output/Done: `✅`
- Warning/Cost: `💸`

Place the icon as a separate text element centered inside the box, above the label text.

### Step 5: Generate elements
Build elements in order:
1. Title text (top center)
2. Subtitle text (below title, smaller, muted)
3. Outer boxes / containers
4. Icon text elements (centered inside each box)
5. Label text elements (below icon, inside each box)
6. Annotation labels on/near boxes (small, muted)
7. Arrows last
8. Arrow annotation labels (small text near midpoint of arrow)

### Step 6: Save and deliver
1. Save to `[concept-slug].excalidraw` in the current directory
2. Show the full JSON in a code block so the user can copy it directly
3. Briefly describe what the diagram shows and what each color represents
4. Tell the user how to use the file:

> **How to view and edit your diagram:**
> - Go to excalidraw.com (free, no account needed)
> - Option A: Click the menu (top-left hamburger icon) > "Open" > select the `.excalidraw` file
> - Option B: Copy the JSON code block above, open excalidraw.com, and paste it with Ctrl+V / Cmd+V
> - Every element is fully editable -- drag to move, grab handles to resize, double-click to edit text

### Step 7: Handle feedback
If the user asks for changes:
- Shifting an element = update x/y on that element + all elements that depend on it
- Changing text = update both `text` and `originalText` fields
- Adding a zone = assign it a color from the palette, keep spacing consistent
- If a diagram gets complex (20+ elements), build it section by section to avoid coordinate errors

---

## Critical Rules

**Text is always white.** All text inside boxes and free-floating labels use `#ffffff`. Annotations and small notes use `#adb5bd`. Never use dark text on dark boxes.

**Every box gets an icon.** Place an emoji as a text element centered horizontally, sitting in the upper portion of the box. The label text goes below it. This gives each node immediate visual identity.

**One color per role.** Blue = one type of thing. Purple = another. Never use the same color for two semantically different roles in the same diagram.

---

## Design Principles

**Dark background, vivid nodes:** The `#1e1e2e` background makes colored boxes pop. Keep box colors saturated — they need contrast to read well on dark.

**Chalkboard font feel:** Use `fontFamily: 1` (Virgil) everywhere. It's handwritten and loose, matching the aesthetic.

**Rounded everything:** All boxes use `roundness: {"type": 3}`. Sharp corners look out of place in this style.

**Sketch roughness:** `roughness: 1` on boxes, `roughness: 1` on arrows. Gives the hand-drawn feel without being sloppy.

**Labels are short:** 2–4 words per label. Longer context becomes a subtitle below the title or a small annotation near the element.

**White space is structure:** 20px minimum gap between siblings inside a container. 60px minimum between major sections.

**Arrows are white or color-matched:** Use `#ffffff` or the destination node's stroke color for arrows. Label every non-obvious arrow with a small annotation 15–20px above the midpoint.

---

## Layout System

Always plan coordinates before writing JSON.

1. Identify major sections (left-to-right or top-to-bottom)
2. Assign fixed width and starting x to each section
3. Calculate gaps: 60px between major sections, 20px between siblings
4. Work top-to-bottom within sections: `next_y = current_y + current_height + gap`

**Padding rules:**
- Title text: centered above the diagram, `y = 20`
- Outer box to icon text: icon sits at `box_y + 15`
- Icon to label text: label sits at `box_y + 55` (for a ~90px tall box)
- Outer box to nested box: 15px offset on all sides
- Sibling elements: 20px gap

**Box sizing:**
- Standard node: `width=160, height=90`
- Wide node: `width=220, height=90`
- Container box: size to content + 30px padding all sides

**Text width trick:** Set text width = parent box width. Text centers automatically when `textAlign: "center"`.

**Arrow labels:** Position as separate text elements, 15–20px above the arrow's midpoint y, with width ~100 and x centered on the arrow.

**Coordinate math example:**
```
Title:     x=center, y=20
Section A: x=60,  w=160  -> right edge = 220
Gap:                        60px
Section B: x=280, w=160  -> right edge = 440
Gap:                        60px
Section C: x=500, w=160  -> right edge = 660
```

---

## Color System

Background: `#1e1e2e` (set in `appState.viewBackgroundColor`)

All text: `#ffffff` (white) for labels, `#adb5bd` for annotations/subtitles

| Zone | Use for | strokeColor | backgroundColor |
|------|---------|-------------|-----------------|
| Blue | Primary entities, main nodes, outputs | `#74c0fc` | `#1864ab` |
| Purple | AI components, skills, config | `#b197fc` | `#5c3bc7` |
| Green | Agents, success states, ready | `#69db7c` | `#1e7e34` |
| Gold | Processing, tools, transformation | `#ffd43b` | `#854d0e` |
| Red | Warnings, costly paths, anti-patterns | `#ff6b6b` | `#891f1f` |
| Teal | Infrastructure, neutral containers | `#4dd9ac` | `#1a6b52` |

For nested elements, use a slightly lighter background than the parent:
- Outer container: `backgroundColor` from palette above
- Inner item: same `strokeColor`, but `backgroundColor` one step lighter (e.g., `#2b5cb8` inside a `#1864ab` container)

---

## Typography Scale

| Role | fontSize | fontFamily | color |
|------|----------|------------|-------|
| Diagram title | 36–40 | 1 (Virgil) | `#ffffff` |
| Subtitle | 18–20 | 1 | `#adb5bd` |
| Section header / box label | 18–20 | 1 | `#ffffff` |
| Icon (emoji) | 28–32 | 1 | `#ffffff` |
| Annotation | 14–15 | 1 | `#adb5bd` |
| Arrow label | 13–14 | 1 | `#adb5bd` |
| Code label | 14–16 | 3 (Cascadia) | `#ffffff` |

---

## Element Schema

Every element needs these base fields. Do not omit any.

### Base fields (all types)
```json
{
  "id": "unique-string",
  "type": "rectangle|ellipse|diamond|arrow|line|text|freedraw",
  "x": 0, "y": 0,
  "width": 160, "height": 90,
  "angle": 0,
  "strokeColor": "#74c0fc",
  "backgroundColor": "#1864ab",
  "fillStyle": "solid",
  "strokeWidth": 2,
  "strokeStyle": "solid",
  "roughness": 1,
  "opacity": 100,
  "groupIds": [],
  "frameId": null,
  "roundness": {"type": 3},
  "boundElements": [],
  "updated": 1,
  "link": null,
  "locked": false
}
```

### Text fields (add to base)
```json
{
  "type": "text",
  "backgroundColor": "transparent",
  "strokeColor": "transparent",
  "text": "Label text",
  "fontSize": 18,
  "fontFamily": 1,
  "textAlign": "center",
  "verticalAlign": "top",
  "containerId": null,
  "originalText": "Label text",
  "lineHeight": 1.25
}
```

### Arrow fields (add to base)
```json
{
  "type": "arrow",
  "backgroundColor": "transparent",
  "strokeColor": "#ffffff",
  "roughness": 1,
  "roundness": {"type": 2},
  "points": [[0, 0], [100, 0]],
  "lastCommittedPoint": null,
  "startBinding": null,
  "endBinding": null,
  "startArrowhead": null,
  "endArrowhead": "arrow"
}
```

### Key values
- **fontFamily:** 1 = Virgil (handwritten, default), 2 = Helvetica, 3 = Cascadia (monospace)
- **roughness:** 1 = slightly sketch-like (use for all elements)
- **fillStyle:** `"solid"` for all boxes in this dark style
- **roundness on boxes:** `{"type": 3}` always
- **roundness on arrows:** `{"type": 2}` for curved arrows
- **strokeStyle:** `"solid"` default, `"dashed"` for optional/secondary connections

---

## Common Patterns

### Standard node with icon + label
```
[Rect: x, y, w=160, h=90, strokeColor=zone, backgroundColor=zone_dark, roundness={type:3}]
[Icon text: x, y+12, w=160, fontSize=28, text="🤖", textAlign=center]
[Label text: x, y+52, w=160, fontSize=18, text="Agent X", textAlign=center, color=#ffffff]
```

### Title + subtitle block
```
[Title: x=0, y=20, w=full_width, fontSize=38, text="Diagram Title", color=#ffffff, textAlign=center]
[Subtitle: x=0, y=70, w=full_width, fontSize=18, text="Tagline here", color=#adb5bd, textAlign=center]
```

### Container with nested items
```
[Host rect: x=0, y=0, w=560, h=160, strokeColor=#74c0fc, backgroundColor=#1864ab]
[Host label: x=0, y=10, w=560, fontSize=16, color=#adb5bd, text="container name"]
[Item 1: x=15, y=50, w=160, h=90, strokeColor=..., backgroundColor=...]
[Item 2: x=195, y=50, w=160, h=90, ...]
[Item 3: x=375, y=50, w=160, h=90, ...]
```

### Arrow with annotation
```
[Arrow: x=start_x, y=mid_y, points=[[0,0],[gap,0]], strokeColor=#ffffff]
[Label: x=start_x, y=mid_y-22, w=gap, fontSize=13, text="in parallel", color=#adb5bd, textAlign=center]
```

### Side-by-side comparison (Don't vs Do)
```
[Left container: red zone, label "✗ Don't"]
[Right container: green zone, label "✓ Do"]
[Dashed vertical divider line in the middle]
```

---

## JSON Wrapper

Every diagram uses this shell:
```json
{
  "type": "excalidraw",
  "version": 2,
  "source": "https://excalidraw.com",
  "elements": [ ... ],
  "appState": {
    "gridSize": null,
    "viewBackgroundColor": "#1e1e2e"
  },
  "files": {}
}
```
