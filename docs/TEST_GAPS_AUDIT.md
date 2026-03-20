# DealSim Test Coverage Gap Audit

**Date:** 2026-03-19
**Auditor:** QA Lead Review (Automated)
**Test runner:** pytest
**Test files:** 12 (including conftest.py)
**Source files:** 23 (including __init__.py files)

---

## 1. Function-by-Function Coverage Table

### Legend
- **Y** = Tested (at least one test exercises this function)
- **P** = Partially tested (happy path only, missing edge cases)
- **N** = Not tested
- **I** = Indirectly tested (exercised through integration but no dedicated unit test)

---

### `src/dealsim_mvp/core/simulator.py`

| Function/Method | Tested | Test File | Notes |
|---|---|---|---|
| `TurnSpeaker` (enum) | Y | test_simulator.py | Used throughout |
| `MoveType` (enum) | Y | test_simulator.py | Used throughout |
| `Turn` (dataclass) | Y | test_simulator.py | Used throughout |
| `NegotiationState` (dataclass) | Y | test_simulator.py, test_scorer.py | Used throughout |
| `SimulatorBase.generate_response` | I | test_simulator.py | Abstract; tested via RuleBasedSimulator |
| `SimulatorBase.initialize_state` | Y | test_simulator.py | Via fixture |
| `SimulatorBase.opening_statement` | Y | test_simulator.py | TestOpeningStatement class |
| `RuleBasedSimulator.generate_response` | Y | test_simulator.py | TestOpponentResponse |
| `_extract_offer` | Y | test_simulator.py | Parameterized, 10+ cases |
| `_classify_user_move` | Y | test_simulator.py | TestClassifyUserMove |
| `_update_state_from_user_move` | I | test_simulator.py, test_session.py | No dedicated unit test |
| `_offer_is_acceptable` | I | test_simulator.py | Tested via deal acceptance tests |
| `_compute_opponent_offer` | I | test_simulator.py | No dedicated unit test |
| `_user_concession_ratio` | **N** | - | Never directly tested |
| `_round_offer` | **N** | - | Never directly tested |
| `_user_wants_more` | **N** | - | Never directly tested |
| `_compose_opener` | I | test_simulator.py | Via opening_statement |
| `_compose_acceptance_response` | I | test_simulator.py | Via deal acceptance |
| `_compose_deal_close` | I | test_simulator.py | Via deal acceptance |
| `_render_opponent_response` | I | test_simulator.py | Via generate_response |
| `_question_response` | I | test_simulator.py | Via generate_response |
| `_batna_response` | I | test_simulator.py | Via generate_response |
| `_info_share_response` | I | test_simulator.py | Via generate_response |
| `_anchor_reaction` | I | test_simulator.py | Via generate_response |
| `_concession_reaction` | I | test_simulator.py | Via generate_response |
| `_counter_reaction` | I | test_simulator.py | Via generate_response |
| `_generic_reaction` | I | test_simulator.py | Via generate_response |
| `_holding_line` | I | test_simulator.py | Via generate_response |
| `_new_offer_line` | I | test_simulator.py | Via generate_response |
| `_fmt` | **N** | - | Never directly tested |

### `src/dealsim_mvp/core/persona.py`

| Function/Method | Tested | Test File | Notes |
|---|---|---|---|
| `NegotiationStyle` (enum) | Y | test_persona.py | |
| `PressureLevel` (enum) | Y | test_persona.py | |
| `NegotiationPersona` (dataclass) | Y | test_persona.py | |
| `NegotiationPersona.to_mirofish_config` | Y | test_persona.py | TestMirofishConfig |
| `generate_persona_for_scenario` | Y | test_persona.py | Multiple scenarios |
| `SALARY_NEGOTIATION_TEMPLATES` | Y | test_persona.py | |
| `FREELANCE_RATE_TEMPLATES` | Y | test_persona.py | |
| `RENT_NEGOTIATION_TEMPLATES` | **N** | - | No test for rent personas |
| `MEDICAL_BILL_TEMPLATES` | **N** | - | No test for medical bill personas |
| `CAR_BUYING_TEMPLATES` | **N** | - | No test for car buying personas |
| `SCOPE_CREEP_TEMPLATES` | **N** | - | No test for scope creep personas |
| `RAISE_REQUEST_TEMPLATES` | **N** | - | No test for raise request personas |
| `VENDOR_CONTRACT_TEMPLATES` | **N** | - | No test for vendor personas |
| `COUNTER_OFFER_TEMPLATES` | **N** | - | No test for counter offer personas |
| `BUDGET_REQUEST_TEMPLATES` | **N** | - | No test for budget request personas |

### `src/dealsim_mvp/core/session.py`

| Function/Method | Tested | Test File | Notes |
|---|---|---|---|
| `SessionStatus` (enum) | Y | test_session.py | |
| `NegotiationSession` (dataclass) | I | test_session.py | |
| `TurnResult` (dataclass) | Y | test_session.py | |
| `create_session` | Y | test_session.py | 8 tests |
| `negotiate` | Y | test_session.py | 7 tests |
| `complete_session` | Y | test_session.py | 5 tests |
| `get_transcript` | Y | test_session.py | 2 tests |
| `get_session_state` | Y | test_session.py | Via state assertions |
| `list_sessions` | **N** | - | Never tested |
| `_serialize_session` | **N** | - | Never tested |
| `_deserialize_session` | **N** | - | Never tested |
| `_persist_all` | **N** | - | Never tested |
| `_restore_from_file` | **N** | - | Never tested |
| `_store_session` | I | test_session.py | Called internally |
| `_load_session` | I | test_session.py | Called internally |
| `MAX_ROUNDS` auto-complete | **N** | - | No test for 20-round limit |

### `src/dealsim_mvp/core/scorer.py`

| Function/Method | Tested | Test File | Notes |
|---|---|---|---|
| `DimensionScore` (dataclass) | Y | test_scorer.py | |
| `Scorecard` (dataclass) | Y | test_scorer.py | |
| `generate_scorecard` | Y | test_scorer.py | Extensive |
| `_score_opening_strategy` | Y | test_scorer.py | 3 tests |
| `_score_information_gathering` | Y | test_scorer.py | 3 tests |
| `_score_concession_pattern` | Y | test_scorer.py | 4 tests |
| `_score_batna_usage` | Y | test_scorer.py | 3 tests |
| `_score_emotional_control` | P | test_scorer.py | No test for panic concession path |
| `_score_value_creation` | P | test_scorer.py | Tested via extreme_high_state only |
| `_user_turns` | I | test_scorer.py | Helper, not directly tested |
| `_pct` | **N** | - | Never tested |
| `_check_deceleration` | **N** | - | Never tested |

### `src/dealsim_mvp/core/debrief.py`

| Function/Method | Tested | Test File | Notes |
|---|---|---|---|
| `DebriefResult` (dataclass) | Y | test_debrief.py | |
| `HiddenStateSnapshot` (dataclass) | Y | test_debrief.py | |
| `MoveAnalysis` (dataclass) | Y | test_debrief.py | |
| `generate_debrief` | Y | test_debrief.py | 10 tests |
| `_negotiation_direction` | I | test_debrief.py | Tested via generate_debrief |
| `_build_hidden_state_timeline` | I | test_debrief.py | |
| `_build_move_analysis` | I | test_debrief.py | |
| `_find_closest_to_deal` | I | test_debrief.py | |
| `_compute_optimal_outcome` | I | test_debrief.py | |
| `_find_undiscovered_constraints` | Y | test_debrief.py | Dedicated test |
| `_adjust_willingness` | **N** | - | Never directly tested |
| `_compute_emotional_state` | **N** | - | Never directly tested |
| `_compute_internal_reasoning` | **N** | - | Never directly tested |
| `_summarize_turn` | **N** | - | Never directly tested |
| `_compute_optimal_move` | **N** | - | Never directly tested |

### `src/dealsim_mvp/core/playbook.py`

| Function/Method | Tested | Test File | Notes |
|---|---|---|---|
| `PlaybookResult` (dataclass) | Y | test_playbook.py | |
| `Objection` (dataclass) | Y | test_playbook.py | |
| `ConcessionStep` (dataclass) | Y | test_playbook.py | |
| `generate_playbook` | Y | test_playbook.py | 15+ tests |
| `_detect_direction` | I | test_playbook.py | |
| `_compute_anchor` | I | test_playbook.py | |
| `_compute_walk_away` | I | test_playbook.py | |
| `_round_to_clean` | **N** | - | Never directly tested |
| `_build_scenario_summary` | I | test_playbook.py | |
| `_build_opponent_profile` | I | test_playbook.py | |
| `_build_opening_line` | Y | test_playbook.py | Style-specific tests |
| `_build_anchor_justification` | I | test_playbook.py | |
| `_build_objections` | I | test_playbook.py | |
| `_build_walk_away_script` | Y | test_playbook.py | |
| `_build_batna_statement` | I | test_playbook.py | |
| `_build_batna_timing` | Y | test_playbook.py | |
| `_build_concession_ladder` | I | test_playbook.py | |
| `_build_key_questions` | I | test_playbook.py | |
| `_build_danger_phrases` | I | test_playbook.py | |
| `_extract_lessons` | Y | test_playbook.py | TestLessonExtraction |

### `src/dealsim_mvp/core/earnings.py`

| Function/Method | Tested | Test File | Notes |
|---|---|---|---|
| `EarningsImpact` (dataclass) | Y | test_tools.py | |
| `YearBreakdown` (dataclass) | Y | test_tools.py | |
| `calculate_lifetime_impact` | Y | test_tools.py | 8 tests |
| `format_impact_summary` | Y | test_tools.py | 1 test |

### `src/dealsim_mvp/core/email_audit.py`

| Function/Method | Tested | Test File | Notes |
|---|---|---|---|
| `EmailAudit` (dataclass) | Y | test_tools.py | |
| `Issue` (dataclass) | Y | test_tools.py | |
| `Severity` (enum) | Y | test_tools.py | |
| `audit_negotiation_email` | Y | test_tools.py | 12 tests |
| `_find_hedging` | I | test_tools.py | |
| `_find_passive` | I | test_tools.py | |
| `_check_anchor` | I | test_tools.py | |
| `_check_justification` | I | test_tools.py | |
| `_check_length` | I | test_tools.py | |
| `_check_emotional` | I | test_tools.py | |
| `_check_gratitude_opening` | I | test_tools.py | |
| `_check_specific_close` | I | test_tools.py | |
| `_detect_strengths` | I | test_tools.py | |
| `_rewrite` | Y | test_tools.py | Tested via hedging removal |
| `_locate_phrase` | **N** | - | Never directly tested |
| `_word_count` | **N** | - | Never directly tested |

### `src/dealsim_mvp/core/challenges.py`

| Function/Method | Tested | Test File | Notes |
|---|---|---|---|
| `DailyChallenge` (dataclass) | Y | test_challenges.py | |
| `get_daily_challenge` | Y | test_challenges.py | 7 tests |
| `get_challenge_by_category` | Y | test_challenges.py | 4 tests |
| `list_categories` | Y | test_challenges.py | 3 tests |
| `list_all_challenges` | Y | test_challenges.py | 2 tests |

### `src/dealsim_mvp/core/offer_analyzer.py`

| Function/Method | Tested | Test File | Notes |
|---|---|---|---|
| `OfferAnalysis` (dataclass) | Y | test_offer_analyzer.py | |
| `PercentilePosition` (dataclass) | Y | test_offer_analyzer.py | |
| `MissingComponent` (dataclass) | Y | test_offer_analyzer.py | |
| `CounterStrategy` (dataclass) | Y | test_offer_analyzer.py | |
| `analyze_offer` | Y | test_offer_analyzer.py | 7 tests |
| `parse_offer_text` | Y | test_offer_analyzer.py | 9 tests |
| `_normalize_key` | Y | test_offer_analyzer.py | |
| `_estimate_percentile` | Y | test_offer_analyzer.py | 3 tests |
| `_ordinal` | Y | test_offer_analyzer.py | |
| `_get_benchmarks` | I | test_offer_analyzer.py | |
| `_get_equity_benchmarks` | I | test_offer_analyzer.py | |
| `_get_location_multiplier` | I | test_offer_analyzer.py | |
| `_build_counter_strategies` | I | test_offer_analyzer.py | |
| `_parse_currency` | I | test_offer_analyzer.py | Via parse_offer_text |
| `_parse_percent` | I | test_offer_analyzer.py | Via parse_offer_text |
| `_infer_role` | I | test_offer_analyzer.py | Via parse_offer_text |
| `_infer_level` | I | test_offer_analyzer.py | Via parse_offer_text |

### `src/dealsim_mvp/core/store.py`

| Function/Method | Tested | Test File | Notes |
|---|---|---|---|
| `save_sessions` | **N** | - | **No tests at all** |
| `load_sessions` | **N** | - | **No tests at all** |
| `clear_store` | **N** | - | **No tests at all** |
| `_now_iso` | **N** | - | Never tested |

### `src/dealsim_mvp/core/analytics.py` (legacy shim)

| Function/Method | Tested | Test File | Notes |
|---|---|---|---|
| `append_event` | **N** | - | Never tested |
| `append_feedback` | **N** | - | Never tested |
| `read_events` | **N** | - | Never tested |
| `read_feedback` | **N** | - | Never tested |

### `src/dealsim_mvp/analytics.py`

| Function/Method | Tested | Test File | Notes |
|---|---|---|---|
| `AnalyticsTracker.__init__` | **N** | - | Never tested |
| `AnalyticsTracker.track` | **N** | - | **No tests at all** |
| `AnalyticsTracker.track_feature` | **N** | - | Never tested |
| `AnalyticsTracker.get_stats` | **N** | - | **No tests at all** |
| `AnalyticsTracker.get_events` | **N** | - | Never tested |
| `AnalyticsTracker._rotate_if_needed` | **N** | - | Never tested |
| `AnalyticsTracker._read_all` | **N** | - | Never tested |
| `AnalyticsTracker._append` | **N** | - | Never tested |
| `_event_to_feature` | **N** | - | Never tested |
| `get_tracker` | I | test_api.py | Used by API tests implicitly |

### `src/dealsim_mvp/feedback.py`

| Function/Method | Tested | Test File | Notes |
|---|---|---|---|
| `FeedbackCollector.__init__` | **N** | - | Never tested |
| `FeedbackCollector.submit` | I | test_api.py | Via /api/feedback endpoint |
| `FeedbackCollector.get_summary` | **N** | - | Never tested |
| `FeedbackCollector.get_all` | **N** | - | Never tested |
| `FeedbackCollector._rotate_if_needed` | **N** | - | Never tested |
| `FeedbackCollector._read_all` | **N** | - | Never tested |
| `get_collector` | I | test_api.py | Used implicitly |

### `src/dealsim_mvp/app.py`

| Function/Method | Tested | Test File | Notes |
|---|---|---|---|
| `create_app` | I | test_api.py | Via TestClient |
| `_check_rate_limit` | **N** | - | **No tests at all** |
| `_verify_admin` | **N** | - | Never tested |
| `health_check` | Y | test_api.py | |
| `serve_root / serve_root_fallback` | Y | test_api.py | |
| `admin_stats_json` | **N** | - | **No tests at all** |
| `admin_stats_html` | **N** | - | **No tests at all** |
| `rate_limit_middleware` | **N** | - | **No tests at all** |

### `src/dealsim_mvp/api/routes.py`

| Endpoint | Tested | Test File | Notes |
|---|---|---|---|
| `POST /api/sessions` | Y | test_api.py | 4 tests |
| `POST /api/sessions/{id}/message` | Y | test_api.py | 5 tests |
| `POST /api/sessions/{id}/complete` | Y | test_api.py | 4 tests |
| `GET /api/sessions/{id}` | Y | test_api.py | 3 tests |
| `GET /api/sessions/{id}/debrief` | **N** | - | **No HTTP-level test** |
| `GET /api/sessions/{id}/playbook` | **N** | - | **No HTTP-level test** |
| `POST /api/offers/analyze` | **N** | - | **No HTTP-level test** |
| `GET /api/market-data/{role}/{location}` | **N** | - | **No HTTP-level test** |
| `GET /api/users/{id}/history` | **N** | - | **No HTTP-level test** |
| `GET /api/users/{id}/patterns` | **N** | - | **No HTTP-level test** |
| `GET /api/challenges/today` | **N** | - | **No HTTP-level test** |
| `POST /api/challenges/today/submit` | **N** | - | **No HTTP-level test** |
| `POST /api/feedback` | Y | test_api.py | 1 test |
| `POST /api/events` | **N** | - | **No HTTP-level test** |
| `GET /api/scenarios` | **N** | - | **No HTTP-level test** |
| `POST /api/tools/earnings-calculator` | **N** | - | **No HTTP-level test** |
| `POST /api/tools/audit-email` | **N** | - | **No HTTP-level test** |
| `GET /api/admin/stats` | **N** | - | **No HTTP-level test** |
| `GET /admin/stats` (HTML) | **N** | - | **No HTTP-level test** |
| `_validate_session_id` | Y | test_api.py | Via 400 status tests |

### `src/dealsim_mvp/api/offer_analyzer.py`

| Function/Method | Tested | Test File | Notes |
|---|---|---|---|
| `analyze_offer` (API version) | Y | test_offer_analyzer.py | 2 tests |
| `get_market_data` | Y | test_offer_analyzer.py | 2 tests |
| `get_available_roles` | Y | test_offer_analyzer.py | 1 test |
| `get_available_locations` | Y | test_offer_analyzer.py | 1 test |
| `calculate_earnings_impact` | Y | test_offer_analyzer.py | 1 test |
| `audit_email` | Y | test_offer_analyzer.py | 2 tests |
| `_normalize_role` | **N** | - | Never directly tested |
| `_normalize_location` | **N** | - | Never directly tested |
| `_parse_offer_components` | I | test_offer_analyzer.py | Via analyze_offer |
| `_generate_counter_strategies` | I | test_offer_analyzer.py | Via analyze_offer |
| `_generate_insights` | I | test_offer_analyzer.py | Via analyze_offer |
| `_build_api_benchmarks` | I | test_offer_analyzer.py | Module-level, auto-runs |

### `src/dealsim_mvp/api/analytics.py`

| Function/Method | Tested | Test File | Notes |
|---|---|---|---|
| `SessionSummary` (dataclass) | I | test_api.py | Via complete endpoint |
| `record_session_for_user` | I | test_api.py | Via complete endpoint |
| `get_user_history` | **N** | - | **No direct test** |
| `get_user_patterns` | **N** | - | **No direct test** |
| `get_todays_challenge` | Y | test_challenges.py | |
| `submit_challenge_response` | Y | test_challenges.py | 4 tests |
| `CHALLENGE_POOL` | Y | test_challenges.py | |
| `_append_jsonl` | **N** | - | Never tested |
| `_read_jsonl` | **N** | - | Never tested |
| `_ensure_dir` | **N** | - | Never tested |

### `src/dealsim_mvp/api/debrief.py`

| Function/Method | Tested | Test File | Notes |
|---|---|---|---|
| `MoveAnalysis` (dataclass) | Y | test_debrief.py | |
| `DebriefReport` (dataclass) | Y | test_debrief.py | |
| `PlaybookEntry` (dataclass) | Y | test_debrief.py | |
| `Playbook` (dataclass) | Y | test_debrief.py | |
| `generate_debrief` (API version) | Y | test_debrief.py | 2 tests |
| `generate_playbook` (API version) | Y | test_debrief.py | 3 tests |
| `_analyse_moves` | I | test_debrief.py | |

### `src/dealsim_mvp/api/models.py`

| Model | Tested | Notes |
|---|---|---|
| All Pydantic models | **N** | Models file is documented as "mirror" of routes.py. No dedicated validation tests. |

---

## 2. API Endpoint HTTP-Level Coverage

| Endpoint | HTTP Test? | Gap Severity |
|---|---|---|
| `GET /health` | Y | - |
| `GET /` | Y | - |
| `POST /api/sessions` | Y | - |
| `POST /api/sessions/{id}/message` | Y | - |
| `POST /api/sessions/{id}/complete` | Y | - |
| `GET /api/sessions/{id}` | Y | - |
| `GET /api/sessions/{id}/debrief` | **NO** | **HIGH** |
| `GET /api/sessions/{id}/playbook` | **NO** | **HIGH** |
| `POST /api/offers/analyze` | **NO** | **HIGH** |
| `GET /api/market-data/{role}/{location}` | **NO** | **MEDIUM** |
| `GET /api/users/{id}/history` | **NO** | **MEDIUM** |
| `GET /api/users/{id}/patterns` | **NO** | **MEDIUM** |
| `GET /api/challenges/today` | **NO** | **MEDIUM** |
| `POST /api/challenges/today/submit` | **NO** | **MEDIUM** |
| `POST /api/feedback` | Y | - |
| `POST /api/events` | **NO** | **MEDIUM** |
| `GET /api/scenarios` | **NO** | **LOW** |
| `POST /api/tools/earnings-calculator` | **NO** | **HIGH** |
| `POST /api/tools/audit-email` | **NO** | **HIGH** |
| `GET /api/admin/stats` | **NO** | **HIGH** |
| `GET /admin/stats` (HTML) | **NO** | **MEDIUM** |

**Summary:** 6 of 21 endpoints have HTTP-level tests. 15 endpoints have zero HTTP-level tests.

---

## 3. Missing Edge Case Coverage

### 3.1 Empty / Boundary Inputs

| Gap | Affected Module | Severity |
|---|---|---|
| `create_session(scenario={"target_value": 0})` | session.py | HIGH - target_value=0 may produce division errors in persona math |
| `create_session(scenario={"target_value": -1})` | session.py | HIGH - negative target propagates through all calculations |
| `negotiate(sid, msg)` with 2000-char message (max_length boundary) | routes.py | LOW |
| `negotiate(sid, msg)` with only whitespace | simulator.py | MEDIUM |
| `negotiate(sid, msg)` with only special characters/emoji | simulator.py | LOW |
| `get_user_history(user_id="")` - empty user ID | api/analytics.py | MEDIUM |
| `get_user_patterns(user_id="")` - empty user ID | api/analytics.py | MEDIUM |
| `parse_offer_text` with only equity shares (no dollar amounts) | core/offer_analyzer.py | LOW |
| `audit_email` with only newlines | api/offer_analyzer.py | LOW |
| `calculate_earnings_impact(0, 0)` - zero salaries | api/offer_analyzer.py | MEDIUM |
| `calculate_earnings_impact(100000, 50000)` - negotiated < current | api/offer_analyzer.py | MEDIUM - negative difference, acceptable? |
| `FeedbackCollector.submit` with rating=0 or rating=999 | feedback.py | MEDIUM - clamped to 1-5 but untested |
| `FeedbackCollector.submit` with empty session_id | feedback.py | LOW |

### 3.2 Error Paths

| Gap | Affected Module | Severity |
|---|---|---|
| File system errors during analytics write | analytics.py | HIGH - silently swallows all exceptions |
| Corrupt JSONL lines in events file | analytics.py | MEDIUM - _read_all skips bad lines, untested |
| Corrupt session store JSON | store.py | HIGH - load_sessions renames to .corrupt, untested |
| `save_sessions` when disk is full / read-only | store.py | MEDIUM |
| `_rotate_if_needed` rotation logic | analytics.py, feedback.py | HIGH - file rotation never tested |
| Rate limiter with no client IP (`request.client` is None) | app.py | MEDIUM |
| Admin endpoint with empty DEALSIM_ADMIN_KEY env var | app.py | HIGH - returns 503, untested |
| Admin endpoint with wrong key | app.py | HIGH - returns 403, untested |
| `_validate_session_id` with SQL injection / XSS payloads | routes.py | LOW - validated by UUID regex, but untested |
| `POST /api/events` with disallowed event_type | routes.py | MEDIUM - returns 400, untested |

### 3.3 Concurrent Access

| Gap | Affected Module | Severity |
|---|---|---|
| Concurrent `negotiate()` calls on same session | session.py | HIGH - `_sessions_lock` is only held during load/store, not during the full negotiate cycle |
| Concurrent `_append` calls to JSONL files | analytics.py, feedback.py | LOW - uses threading.Lock |
| Concurrent `save_sessions` / `load_sessions` | store.py | MEDIUM - separate lock from session lock |
| Race between `_rotate_if_needed` and `_read_all` | analytics.py | MEDIUM - read is not locked |

---

## 4. Test Quality Assessment

### 4.1 Tests That Only Check "Doesn't Crash"

| Test | File | Issue |
|---|---|---|
| `test_empty_message` | test_simulator.py | Only checks `isinstance(turn, Turn)` -- does not verify move type or state changes |
| `test_very_long_message` | test_simulator.py | Only checks `isinstance(turn, Turn)` |
| `test_unicode_in_response` | test_challenges.py | Only checks `"total" in result` |
| `test_very_long_response` | test_challenges.py | Only checks `"total" in result` |
| `test_submit_with_empty_response` | test_challenges.py | Only checks `"total" in result` and `>= 0` |
| `test_empty_text` | test_offer_analyzer.py | Only checks that `"role" in result` |
| `test_unknown_role_falls_back_to_general` | test_offer_analyzer.py | Only checks `isinstance` |

### 4.2 Assertion Specificity Issues

| Test | File | Issue |
|---|---|---|
| `test_default_values` | test_api.py | Only checks status_code 201, no field validation |
| `test_index_endpoint_exists` | test_api.py | Only checks status 200, not content type or body |
| `test_submit_feedback` | test_api.py | Does not verify feedback was actually persisted |
| `test_competitive_concedes_less_than_collaborative` | test_simulator.py | Wrapped in `if` -- silently passes when offers are None |
| `test_accommodating_concedes_most` | test_simulator.py | Same `if` guard issue |
| `test_deal_reached_within_reservation` | test_integration.py | Wrapped in `if result.resolved` -- may silently skip |
| `test_no_deal_outside_reservation` | test_integration.py | Wrapped in `if not state.resolved` -- may silently skip |

### 4.3 Tests Testing Implementation Details

| Test | File | Issue |
|---|---|---|
| `test_salary_persona_has_salary_names` | test_persona.py | Checks exact persona name strings from templates -- breaks if names change |
| `test_freelance_persona_has_budget_client_traits` | test_persona.py | Same issue -- tied to template names |
| `test_unknown_type_falls_back_to_salary` | test_persona.py | Checks against internal template name set |
| `test_hard_tightens_reservation` / `test_easy_increases_reservation` | test_persona.py | Uses `random.seed(42)` to pin template selection -- fragile if template order changes |

---

## 5. Flaky Test Risks

### 5.1 Randomness-Dependent

| Test | File | Risk |
|---|---|---|
| All persona tests using `generate_persona_for_scenario` | test_persona.py | `random.choice` selects template -- different templates have different base values. Tests using `random.seed(42)` mitigate this partially. |
| All simulator response tests | test_simulator.py | `random.choice` in response rendering and `random.random()` in AVOIDING style. Could affect concession amount tests and style comparison tests. |
| `test_competitive_concedes_less_than_collaborative` | test_simulator.py | Depends on random response text -- the `if` guard may hide failures when offers are None. |
| All integration tests | test_integration.py | Persona generation uses random template selection. |

### 5.2 Time-Dependent

| Test | File | Risk |
|---|---|---|
| `test_none_uses_today` | test_challenges.py | Uses `date.today()` -- if run exactly at midnight, may flake. |
| `test_get_todays_challenge_returns_dict` | test_challenges.py | Uses `date.today()` via `hashlib.md5` -- deterministic per day but result changes daily. |
| Session auto-cleanup in `store.py` | - | `_MAX_AGE_SECONDS = 3600` -- any test depending on persisted sessions can flake if test suite takes >1 hour. |

### 5.3 File-System-Dependent

| Test | File | Risk |
|---|---|---|
| `_clear_sessions` autouse fixture | conftest.py | Calls `_SESSIONS.clear()` but `_restore_from_file()` runs at module import -- if `.dealsim_sessions.json` exists from a previous run, stale sessions may leak in. |
| All tests implicitly | conftest.py | `AnalyticsTracker` and `FeedbackCollector` write to `data/` directory -- no cleanup. Cross-test contamination possible. |
| `submit_challenge_response` | test_challenges.py | Writes to `data/challenge_submissions.jsonl` -- never cleaned up between tests. |

---

## 6. Summary of Critical Gaps

### Priority 1 (Blocking)

1. **15 of 21 API endpoints have no HTTP-level test** -- including debrief, playbook, offer analysis, earnings calculator, email audit, admin stats, scenarios, events, user history, user patterns, challenges.
2. **`store.py` has zero tests** -- file persistence is completely untested. Corrupt file handling, atomic writes, auto-cleanup, and file rotation are all unverified.
3. **`analytics.py` and `feedback.py` have zero dedicated tests** -- the JSONL tracking system (track, get_stats, get_events, file rotation) is entirely untested.
4. **Rate limiter has no tests** -- `_check_rate_limit` is untested. A bug here silently blocks or allows all traffic.
5. **Admin authentication has no tests** -- `_verify_admin`, missing key (503), wrong key (403) are all unverified.

### Priority 2 (High)

6. **8 of 10 persona template sets are untested** -- only salary and freelance templates are tested. Rent, medical bill, car buying, scope creep, raise, vendor, counter offer, and budget request templates have zero coverage.
7. **`list_sessions()` is untested** -- public API function with no test.
8. **Session serialization/deserialization untested** -- `_serialize_session` and `_deserialize_session` handle complex state reconstruction; bugs here lose user sessions silently.
9. **MAX_ROUNDS auto-complete untested** -- the 20-round limit that auto-completes sessions is never exercised.
10. **Concurrent access to negotiate() is unsafe** -- lock only protects dict access, not the full negotiate cycle. No concurrent test exists.

### Priority 3 (Medium)

11. **Several tests silently skip via `if` guards** -- `test_deal_reached_within_reservation`, `test_no_deal_outside_reservation`, and concession comparison tests wrap assertions in `if` blocks that may never execute.
12. **Test isolation for file-writing modules is poor** -- analytics, feedback, and challenge submission tests write to shared `data/` directory with no cleanup.
13. **`_check_deceleration` and `_round_offer` have no unit tests** -- these affect scoring and offer rounding respectively.
14. **Negative/zero earnings impact untested** -- `calculate_earnings_impact(100000, 50000)` (negotiated < current) behavior is undocumented and untested.

---

## 7. Recommended Test Additions (Priority Order)

1. Add HTTP-level tests for all 15 missing endpoints (especially debrief, playbook, offer analysis, admin).
2. Add a `test_store.py` with tests for save/load/clear, corrupt file handling, and auto-cleanup.
3. Add a `test_analytics.py` with tests for AnalyticsTracker: track, get_stats, get_events, file rotation.
4. Add a `test_feedback.py` with tests for FeedbackCollector: submit, get_summary, get_all, rating clamping.
5. Add rate limiter tests in `test_api.py`: normal flow, rate exceeded (429), cleanup of stale IPs.
6. Add admin auth tests: missing key (503), wrong key (403), correct key (200).
7. Add persona template tests for all 10 scenario types.
8. Remove `if` guards from integration tests -- use deterministic personas that guarantee the tested outcome.
9. Add `tmp_path` fixtures to isolate file-writing tests from each other.
10. Add concurrency test: two threads calling `negotiate()` on the same session simultaneously.
