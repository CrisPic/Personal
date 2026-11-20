---
name: sprout
description: Grow a raw idea seed (a word cloud, loose phrase, or half-formed thought about an idea, workflow or project) into at least 5 renditions (actionable items, plans, brainstorming prompts) by fanning out parallel Haiku `idea-sprouter` subagents. Use when the user says /sprout, "sprout this", "grow this idea", or dumps unstructured thoughts and wants them shaped.
argument-hint: <word cloud or phrase>
---

# Sprout: grow an idea seed into at least 5 renditions

The seed is: **$ARGUMENTS**

If the seed is empty, ask the user for it in one line and stop.

## Step 1: Fan out in parallel

In **one single message**, launch **6** `idea-sprouter` subagents in parallel (Agent tool,
`subagent_type: "idea-sprouter"`, foreground). Launching 6 instead of 5 leaves a spare in case
one fails. Give each one the seed exactly as written, plus one lens:

| ID | Lens | Aim |
|----|------|-----|
| 1 | Action list | A checklist of 5 to 10 concrete next actions |
| 2 | Project plan | Goal, scope, 3 to 4 phases with deliverables, risks |
| 3 | Brainstorm prompt | A ready-to-paste prompt for a later exploring session |
| 4 | Workflow | A repeatable process or system: trigger → steps → output, plus tools |
| 5 | Smallest experiment | An MVP or test you can do in under 1 week, with a success metric |
| 6 | Contrarian reframe | Flip or widen the idea: what it could be instead, and why |

Prompt template for each worker:

```
SEED: <seed exactly as written>
LENS: <lens> (<aim>)
RENDITION_ID: <ID>
```

## Step 2: Check and refill until you have at least 5

A rendition is **valid** when it has all of these: a title, Lens, Interpretation, Form, Body,
First step, and Open question. It must also be about the seed and not a duplicate of another
rendition.

- Count the valid renditions.
- If there are **fewer than 5**, launch more `idea-sprouter` workers in parallel for the missing
  ones. Use the lenses that failed, or new lenses such as "Habit/routine", "Content piece",
  "Tool/automation" or "Collaboration pitch". Repeat until you have at least 5 valid ones.
  Stop after 3 refill rounds, and tell the user if you still have fewer than 5.
- Do not write renditions yourself to fill the gap. They must come from the workers.

## Step 3: Compile and present

Show the user:

1. **Seed:** the seed, quoted.
2. **Common thread:** 2 to 3 sentences on what all renditions agree the idea is about, and where
   they split.
3. **The renditions:** all valid ones, in order, unchanged except for small formatting fixes.
4. **Recommendation:** which 1 or 2 renditions to pursue first, and why, in 2 to 3 lines.

Then save the full output to `ideas/<YYYY-MM-DD>-<short-slug>.md` in the project root (create
the folder if it does not exist), so the seed can be revisited later. Tell the user the path.
