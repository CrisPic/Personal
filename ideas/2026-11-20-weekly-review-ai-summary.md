# Sprout: weekly review habit, notion, journaling, ai summary

**Seed:** "weekly review habit, notion, journaling, ai summary"

## Common thread

All six renditions read the seed the same way: a short daily journal in Notion, and a weekly review in which an AI condenses or questions the week, ending in a few concrete priorities. They agree on a Sunday time slot of 20 to 30 minutes, on small properties like Energy 1-5, Wins and Snags, and on a prompt with a fixed output format. They split on the AI's role (summarizer in 1 to 5, interviewer in 6) and on how much to build up front: a full system (2, 4) or a throwaway test (5). Five of the six raise the same open question: whether journal text may go to an external AI or should stay in Notion AI.

## Renditions

### Rendition 1: Sunday Sweep in Notion
**Lens:** Action list
**Interpretation:** You want a recurring weekly review in Notion, where daily journal entries get condensed into an AI summary that feeds concrete actions for the next week.
**Form:** Actionable item

**Body:**
- [ ] Create a Notion database "Journal" with properties: Date, Mood (1-5), Entry (text), Tags (multi-select).
- [ ] Create a database "Weekly Review" with properties: Week (date), Wins, Stuck on, Energy (1-5), Next week's top 3, AI summary (text).
- [ ] Add a linked view of Journal inside each Weekly Review page, filtered to the last 7 days.
- [ ] Journal for 5 minutes a day, even one line counts. Target 5 of 7 days.
- [ ] Use one AI tool only for the summary for a month. Either Notion AI's summarize action on the linked view, or paste the week's entries into a chat with this prompt: "From these journal entries, list (1) 3 recurring themes, (2) 2 wins, (3) 1 thing that drained energy, (4) 3 actions for next week. Cite the date for each claim."
- [ ] Put a recurring calendar block on Sunday at 18:00, 25 minutes, titled "Sweep."
- [ ] Run the first review this Sunday. Rewrite the AI summary in your own words before saving it, so you keep ownership of the conclusions.
- [ ] Copy "Next week's top 3" into your daily page on Monday, so the review changes what you actually do.
- [ ] After 4 weeks, check whether you opened the review every Sunday. Delete any property you never filled in, and shorten the prompt if the output is noisy.

**First step (≤ 15 min):** In Notion, create the Journal database with the four properties listed above and write one entry for today.
**Open question:** Which AI are you comfortable pasting personal entries into: Notion AI inside your workspace, or an external chat? That choice decides whether raw journal text ever leaves Notion.

### Rendition 2: Six-Week Sunday Review Trial
**Lens:** Project plan
**Interpretation:** You want a recurring weekly review in Notion where you journal about your week and an AI tool condenses those notes into a summary you can actually reread.
**Form:** Plan

**Body:**
**Goal:** By week 6, complete a 20-minute Sunday review in Notion at least 5 of 6 weeks, each with an AI-generated summary saved in the same page.

**Scope:** In: one Notion database, one template, one saved AI prompt, a 6-week trial. Out: Notion automations, mobile widgets, sharing with anyone else.

**Phase 1 (Week 1): Template.** Deliverable: database "Weekly Review" with properties Week (date), Wins (text), Friction (text), Energy (1 to 5), Summary (text). Add a template button that pre-fills three prompts: What mattered? What drained me? What is the one thing for next week?

**Phase 2 (Week 2): Journaling loop.** Deliverable: a recurring 20-minute Sunday calendar block. Complete two reviews using only the template, with no edits to its structure.

**Phase 3 (Weeks 3 to 4): AI summary.** Deliverable: one saved prompt, for example "Summarize these notes into 3 themes, 1 pattern, and 1 question. Quote one exact phrase from my notes." Paste the output into the Summary property. Try Notion AI and one external model for one week each, then keep the one whose summaries you reread.

**Phase 4 (Weeks 5 to 6): Review the review.** Deliverable: a 15-minute check that counts completed reviews, rereads the last four summaries, and makes at most two prompt changes. Decide keep, change, or stop.

**Risks:**
- Missed weeks break momentum. Fallback: a 5-minute version that fills only Wins and Energy.
- Journal text sent to an external AI may be sensitive. Use a tool you trust and remove names or employer details first.
- Summaries feel generic. The quote requirement in the prompt is the fix.
- Template keeps growing. Freeze it after Phase 1; changes happen only in Phase 4.

**First step (≤ 15 min):** Create the "Weekly Review" database in Notion with the five properties listed in Phase 1 and add a calendar block for next Sunday at 20 minutes.
**Open question:** Is your journal text acceptable to send to an external AI model, or should the summaries stay inside Notion AI only?

### Rendition 3: Weekly review loop: Notion journal plus AI summary
**Lens:** Brainstorm prompt
**Interpretation:** You want a weekly review habit where daily journaling in Notion gets condensed by AI into a short summary you can act on.
**Form:** Brainstorm prompt

**Body:**
```
I want to design a weekly review habit that combines journaling in Notion with an AI-generated summary. Help me explore this as a working system, not a theory. Ask me one question at a time when you need detail.

Context:
- Tool: Notion (databases, templates, linked views are available to me).
- Current state: [e.g., I journal irregularly / I have no journal yet]
- Time budget for the weekly review: [e.g., 30 minutes, Sunday evening]
- What I want the summary to show: [e.g., wins, patterns, open loops, mood trend]

Please work through:
1. A Notion database schema for daily entries (properties, tags, dates) that makes a weekly roll-up easy.
2. A weekly review template: ordered prompts with a time limit per section.
3. A reusable AI summary prompt I can paste into Notion AI or another model, with a fixed output format (e.g., 5 bullets max).
4. How to keep the review from becoming a chore: what to skip, what to automate, what to read by hand.
5. A 4-week trial with one metric that tells me whether it works.

Challenge my assumptions where they look weak. Keep answers concrete and short. End each round with the single next decision I should make.
```

**First step (≤ 15 min):** Create one Notion database named "Journal" with three properties (Date, Mood 1-5, Entry) and write one entry today.
**Open question:** Should the weekly summary focus on reflection (feelings and patterns) or on action (open tasks and next week's focus)?

### Rendition 4: Sunday Review Loop: Notion in, AI summary, three priorities out
**Lens:** Workflow
**Interpretation:** You want a weekly habit where daily journaling in Notion gets turned into a short AI-assisted summary that sets the next week's priorities.
**Form:** Plan

**Body:**
**Trigger:** Calendar event every Sunday 18:00, titled "Weekly review", 30 min. Phone reminder 10 min before.

**Tools:** Notion (Journal database, Tasks database, Weekly Reviews database), plus Notion AI or any LLM you paste into.

**Steps**
1. **Brain dump (5 min).** Open the Journal database. Create a new Weekly Reviews page and list loose ends as bullets.
2. **Tag the week (5 min).** Each daily journal entry gets three properties: Energy (1-5), Win (text), Stuck (text). Fill in any missing days from memory.
3. **Summarize (5 min).** Filter Journal to the last 7 days, copy the text, paste it into the AI with this prompt:

```
Below are my journal entries for the past 7 days. Reply in under 150 words:
1) recurring energy patterns, 2) the two wins that matter most,
3) the one thing I keep avoiding. Then propose 3 priorities for next week,
each with a concrete first action. Be direct, no flattery.
```

4. **Decide (10 min).** Pick exactly three priorities from the AI output. Create each as a task in Tasks and link it to the review page.
5. **Close (5 min).** Rate the week 1-5 and write one sentence starting "Next week I will stop..."

**Output:** One page in Weekly Reviews titled with the ISO week (e.g. "2026-W47 Review") with properties: Energy average (rollup from Journal), Top 3 priorities (relations to Tasks), AI summary (edited, not pasted raw), week rating, and the "stop" sentence.

**First step (≤ 15 min):** Create the Weekly Reviews database in Notion with the properties above and block Sunday 18:00 in your calendar.
**Open question:** Is your daily journaling already happening in Notion, and are you comfortable sending those entries to an external AI, or should step 3 use Notion AI only?

### Rendition 5: Five-Day Journal-to-AI Summary Test
**Lens:** Smallest experiment
**Interpretation:** You want to know whether a short daily journal plus an AI-written weekly summary becomes a review habit you would actually keep, and you can learn that in one work week without building a system.
**Form:** Plan

**Body:**
Run Monday to Friday, then judge the result on Friday evening.

Setup (10 min, Monday)
- In Notion, create a database "Week test" with four properties: Date (date), Entry (text), Energy (number 1-5), Snag (text).
- Set a phone reminder for 9:00 pm, Mon-Fri, titled "3 lines".

Daily (3 min, Mon-Fri)
- Add one row: what happened, one win, one snag, energy 1-5. Do not edit past rows.

Friday review (15 min)
- Select the five rows and copy them as plain text.
- Paste into an AI tool with this prompt: "Here are my five journal entries. Give me (1) the top three themes, (2) one pattern I seem to be avoiding, (3) two concrete actions for next week. Be blunt and quote me where possible."
- Rate the summary 1-5 for "this is accurate about my week."

Success metric (all three must hold)
1. At least 4 of 5 days have an entry.
2. Summary accuracy rating is 4 or higher.
3. You have started at least one of the two suggested actions by Sunday, or you can name a specific reason you did not.

Decision: if all three hold, repeat for a second week. If entries drop below 3 or the summary feels generic, stop or change one variable (the prompt or the reminder time), not both.

Total time cost: about 25 min for the week.

**First step (≤ 15 min):** Create the "Week test" database in Notion with the four properties and set the 9:00 pm reminder.
**Open question:** Are you comfortable pasting raw journal text into an external AI tool, or should the test use Notion's built-in AI instead?

### Rendition 6: Ban the Summary, Keep the Questions
**Lens:** Contrarian reframe
**Interpretation:** The seed treats the weekly review as a way to compress your week into an AI summary, but the real value is the open questions a week leaves behind, so the AI should interrogate you instead of summarizing you.
**Form:** Plan

**Body:**
Flip: a weekly review is not a recap. It is a short interview you conduct on yourself, with the AI asking the questions. Summaries close a week; questions keep it open long enough to learn from.

Why: an AI summary makes the week feel finished, so you feel informed and skip the thinking. A question forces the thinking and shows what your journal says versus what you assume it says.

Setup (one Notion page, saved as a template called "Week interview"):
- Properties: Week (date), Energy 1-5, one-word mood, "Surprised me" (text).
- Journal section: paste the last 7 days of entries or link the daily pages.
- Prompt block, pasted into Notion AI or any LLM: "Do not summarize. Read my entries below and ask me exactly 3 questions I have not answered in my own writing. Each question must cite a specific entry. Then stop and wait."

Every Sunday, 25 minutes:
1. Run the prompt on the week's entries.
2. Answer each question in 3 to 5 sentences, written on the Notion page, not in the chat.
3. Pick the answer that contradicts your current plan and write one concrete action for Monday.
4. Keep the one question that bothered you; delete the rest.

Test it: run this for 4 weeks with no AI summary at all, then count how many weekly actions you actually finished compared with your old reviews.

**First step (≤ 15 min):** Create the Notion template with the four properties and paste the prompt block into it.
**Open question:** Should the AI see only this week's entries, or the last 4 weeks, so it can ask about patterns instead of single days?

## Recommendation

Start with **Rendition 5**, the five-day test. It costs about 25 minutes and tells you within a week whether you will actually journal. If it passes, move to **Rendition 4** as the permanent Sunday workflow, and replace its summary prompt with the question prompt from **Rendition 6** on one Sunday to see which one leads to more finished actions.
