# DealSim 100-Agent Review & Polish Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement fixes task-by-task.

**Goal:** Review the complete DealSim product with 100 agents across 6 waves, fix all issues found, produce 3 PDF documents, and prepare for cloud deployment.

**Architecture:** Wave-based review → fix → re-review pipeline. Backend review first (Wave 1), then frontend/UX review (Wave 2), then fixes (Wave 3), then documentation (Wave 4), then UpCloud deployment review (Wave 5).

---

## Wave 1: Backend Security + Quality Review (25 agents)
**Purpose:** Find all backend bugs, security issues, API inconsistencies
**Agents:** Security reviewers, API testers, code quality auditors

## Wave 2: Frontend UX/UI + Feature Review (25 agents)
**Purpose:** Find UX issues, missing QoL features, accessibility problems
**Agents:** UX psychologists, UI experts, feature gap analysts

## Wave 3: Fix Cycle (applied in dependency order)
**Purpose:** Fix everything Waves 1-2 found
**Order:** Security fixes → API fixes → Core logic fixes → Frontend fixes → QoL features

## Wave 4: Re-review (10 agents verifying fixes)
**Purpose:** Verify Wave 3 fixes didn't break anything
**Agents:** Subset re-checking changed files only

## Wave 5: Documentation (15+15 agents)
**Purpose:** Produce 3 PDFs:
1. Company Internal Document (pipeline, security, architecture)
2. Investor Document (features, market, metrics)
3. User Guide (how to navigate the app)

## Wave 6: UpCloud Deployment Review (20 agents)
**Purpose:** Can we deploy on UpCloud? What changes needed?
**Agents:** DevOps specialists, cloud architects
