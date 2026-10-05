---
name: dev-review
description: Run a developer → reviewer loop on an implementation task in a paper-to-code project. The developer subagent implements, a fresh read-only reviewer subagent reviews it against the paper, and the loop repeats until approved (max 3 rounds).
argument-hint: <task description>
disable-model-invocation: true
---

# Developer → reviewer loop

Task: $ARGUMENTS

You are the orchestrator in the main session. Do not write the implementation yourself. Delegate it to
the subagents below and relay their results:
- `paper-to-code:developer`: implements and hands back a report with "Files changed", "Paper mapping"
  and "Verification" sections.
- `paper-to-code:reviewer`: read-only; returns `VERDICT: APPROVE | CHANGES_REQUESTED` with blocking and
  non-blocking findings.

If the task above is empty, ask the user what to implement before doing anything else. Base your
suggestions on CLAUDE.md's "The method" and on what already exists.

## Procedure
1. **Pre-flight:**
   - Check that `CLAUDE.md` has the sections the agents rely on: Purpose, Commands, Code layout, The
     method, Expected results and Fidelity checklist. If it doesn't, suggest `/paper-to-code:init`.
   - Run `git rev-parse --verify HEAD`. If the repo has no commits yet (e.g. straight after
     `/paper-to-code:init`), offer to commit the scaffold first, and only continue once it is committed.
   - Run `git status --short`. If there are uncommitted changes unrelated to this task, stop and ask the
     user how to proceed. Otherwise the reviewer could not tell them apart from the developer's changes.
     If the changes look like notebook edits made in Jupyter (trailing empty cells, dropped execution
     metadata), say so when you ask.
2. **Round 1, develop:** launch `paper-to-code:developer` with the task text verbatim, plus any
   clarifications the user gave. Note its agent ID, so later rounds can resume it. Wait for its
   hand-back report.
3. **Review:** launch a **new** `paper-to-code:reviewer` in a fresh context every round. A fresh
   reviewer is not anchored on its own earlier reasoning. Give it:
   - the task text, plus the developer's latest "Files changed" and "Paper mapping" sections.
   - **Rounds 2+ only:** the previous round's blocking findings verbatim, under the heading "Previous
     findings". For any finding the developer *disputed*, include the developer's stated reason and
     evidence. Do **not** pass the developer's "fixed" claims; the reviewer verifies those itself.

   Do not pass the developer's reasoning or verification output. Wait for the verdict.
4. **Loop:**
   - `VERDICT: APPROVE`: go to step 5.
   - `VERDICT: CHANGES_REQUESTED`: **resume the same developer** with SendMessage to its agent ID, so it
     keeps the context of its own work. Send the reviewer's blocking findings verbatim; non-blocking
     suggestions are optional, and you may pick the ones worth doing now. If resuming fails, launch a new
     developer with the original task, the findings, and an instruction to read the current uncommitted
     changes first. Then use the new agent's ID from then on.
     Then review again as in step 3.
   - Stop after **3 review rounds** even if the verdict is not APPROVE.
5. **Report to the user:**
   - the final verdict and the number of rounds
   - a summary of what changed (files, plus a paper section/equation mapping)
   - any findings that are still open, or that the developer disputed (relay the dispute and the
     reviewer's position honestly)
   - which notebook(s) to open to see the results
   - the final test and notebook results, which you run yourself (see "Commands" in CLAUDE.md; by
     default `uv run pytest -q` and `uv run pytest --nbmake notebooks/ -q`), plus any check the
     reviewer reported as "not run (blocked by hook)"
   - the non-blocking suggestions you did not act on, so they can be collected into a later cleanup task

Leave the changes uncommitted. Offer to commit, but only commit if the user says so.

## Running several tasks in sequence
If the user asks you to work through several tasks one by one:
- Ask once whether to **commit each task after the reviewer approves it**. This keeps the tree clean,
  so each reviewer sees only its own task's diff. If the user agrees, commit after every `APPROVE`
  without asking again. If a task ends without `APPROVE` after 3 rounds, stop and ask before
  committing or continuing.
- Start each new task with a **fresh developer**. Don't carry a developer whose context has grown very
  large into an unrelated task.
- Keep a running list of the non-blocking suggestions that were not acted on. Offer them as a final
  "cleanup" task, with each item quoted and its file named.
