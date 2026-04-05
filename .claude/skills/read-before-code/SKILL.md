---
name: read-before-code
description: This skill should be used when starting any non-trivial implementation task, especially when integrating with an existing framework, library, or codebase the model hasn't fully read yet. Prevents wasted rounds caused by writing code before understanding the system.
version: 1.0.0
---

# Read Before Code

## The Problem This Solves

Writing code against a framework without first reading its core files leads to:
- Wrong abstractions (e.g. designing fake tasks when the framework has real ones)
- Multiple rounds of "Continue" to fix fundamental misunderstandings
- Wasted LLM calls re-reading files that should have been read upfront

## Rule

**Before writing any integration code, read ALL relevant framework/library files first.**

Specifically:
1. Identify the entry points (main runner, core classes)
2. Read them ALL in parallel before forming a design
3. Only after reading: state the design in one sentence, then implement

## Checklist Before Writing Code

- [ ] Have I read the framework's main runner / orchestrator?
- [ ] Have I read the task/data format definitions?
- [ ] Have I read the grading / evaluation logic?
- [ ] Have I read at least one example task file?
- [ ] Can I describe in one sentence how data flows through the system?

If any box is unchecked → read first, code second.

## Anti-patterns to Avoid

- Reading one file, forming a hypothesis, writing code, then discovering the hypothesis was wrong
- Asking "Continue" to the user while still exploring — explore fully first
- Creating new files/formats when the framework already has the right ones
- Designing around the framework instead of with it

## Example (this project)

PinchBench integration:
- WRONG: design custom governance task files, custom grade() functions
- RIGHT: read `lib_tasks.py`, `lib_agent.py`, `lib_grading.py`, `benchmark.py`, one example task — THEN design

The correct design (one sentence): governance chain runs first, injects decision as prompt prefix, openclaw agent executes under that governance frame, PinchBench grades the result.

This takes 4 parallel reads + 1 sentence. Not 100 rounds.
