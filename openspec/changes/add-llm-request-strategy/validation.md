# Validation Report: LLM Request Strategy Design (v4)

**Reviewers:** Gemini CLI (Architect/QA Persona)
**Date:** 2026-02-20
**Target Design:** `openspec/changes/add-llm-request-strategy/design.md`

---

## 🔍 Executive Summary
The v4 design is **production-ready**. It effectively addresses all previous architectural and reliability concerns, including deadlock prevention, API hammering mitigation, and log hygiene. The testing plan is comprehensive and optimized for CI efficiency.

---

## 🚨 Gating Issues
**None.** The design has successfully cleared all critical architectural risks identified in previous iterations.

---

## ⚠️ Non-Gating Risks

### 1. Head-of-Line (HoL) Blocking (QA Principle #8)
*   **Risk:** As acknowledged in **R3**, the `threading.Lock` scope covers the entire network I/O (`_inner_provider.analyze`).
*   **Impact:** If one request hangs or is slow, other worker threads—even those that would immediately return `None` because the RPD cap has already been reached—must wait for the lock to be released. 
*   **Mitigation:** For the current 3-worker/20-RPD Cron Job, this is acceptable and keeps the implementation simple. If scaling to more workers, consider a "slot-booking" pattern where the lock only guards the assignment of the next execution timestamp.

### 2. Provider-Specific Exception Mapping (QA Principle #1)
*   **Risk:** The design refers to `HTTP429Error`.
*   **Impact:** Different LLM SDKs (Google vs. Anthropic) may raise different exception classes. 
*   **Recommendation:** Ensure the implementation in `strategy.py` correctly catches the specific 429-equivalent exception used by each provider, or that providers normalize their 429s to a common base class.

---

## 💡 Nitpicks

1.  **D2 Consistency:** The decision table uses `isinstance`, while the rationale mentions `type(provider).__name__`. `isinstance` is safer; ensure `strategy.py` avoids circular imports if concrete provider classes are imported for these checks.
2.  **Log Context:** For the `llm_run_limit_reached` warning, including a brief reason (e.g., "Run limit of 20 reached") helps operators quickly understand the log without looking up the environment variable.
3.  **Start-to-Start Edge Case:** If a request takes *longer* than `min_interval_seconds`, the next request will start immediately after the first one finishes. This is correct for RPM, but if the API expects an "inter-request gap" (Start-to-End), this strategy may still trigger 429s. However, for Gemini, Start-to-Start is the standard RPM model.
