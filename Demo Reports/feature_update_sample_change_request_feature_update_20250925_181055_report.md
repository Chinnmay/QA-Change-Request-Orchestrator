# Feature Update - Test Case Analysis Report

**Generated**: 2025-09-25T18:10:55.636952

## Change Request Metadata

**Type**: feature_update
**Title**: Change Request: Reduce free cancellation window to 12 hours
**Description**: # Change Request: Reduce free cancellation window to 12 hours

change_type: feature_update

author: Product Manager

### Overview
To improve marketplace reliability, the free cancellation window for booked shifts is being **reduced from 24 hours to 12 hours** before the shift start time.

### Acceptance criteria / User flows
1. If a Pro cancels **≥ 12 hours** before shift start, no reliability penalty is applied and the confirmation modal shows: *“You can cancel up to 12 hours before start without penalty.”*
2. If a Pro cancels **< 12 hours** before shift start, reliability score is reduced and modal explains the penalty.
3. The help center link in the modal is updated to the new policy doc.
4. Analytics event `shift_cancelled` must include new field `free_cancellation_window_hours = 12`.

**Acceptance Criteria**:

## Test Cases Analyzed

| # | Test Case Title | Priority | Score | File Name |
|---|----------------|----------|-------|-----------|
| 1 | Pro cancels a booked shift within the allowed cancellation window | P2 - High | 0.625 | tc_004.json |
| 2 | Push-notification permission prompt on first app launch | P3 - Medium | 0.228 | tc_003.json |

## Test Cases Updated

### Pro cancels a booked shift within the allowed cancellation window
**File**: tc_004.json
**Updated**: 2025-09-25T18:10:52.716116

**Feature Impact**: The feature update directly modifies the free cancellation window from 24 hours to 12 hours. This necessitates adjustments to test cases that verify cancellation behavior, specifically focusing on the new 12-hour threshold and the corresponding messaging and penalty implications.

**Changes Made**:
- **preconditions**:
  - Before: Pro is logged in and has a booked shift. The current time is less than 24 hours before the shift start time.
  - After: Pro is logged in and has a booked shift. The current time is less than 12 hours before the shift start time.
- **steps[1].step_expected**:
  - Before: A confirmation modal appears, indicating the penalty and providing a link to the updated policy.
  - After: A confirmation modal appears, indicating the penalty and providing a link to the updated policy.
- **steps[2].step_expected**:
  - Before: The modal text clearly states: "You can cancel up to 24 hours before start without penalty." and mentions the reliability score reduction for cancellations less than 24 hours before the shift.
  - After: The modal text clearly states: "You can cancel up to 12 hours before start without penalty." and mentions the reliability score reduction for cancellations less than 12 hours before the shift.
- **steps[3].step_expected**:
  - Before: The help center link in the modal navigates to the new policy document detailing the 24-hour cancellation window.
  - After: The help center link successfully redirects to the updated policy document.

**Why?**
**Reasoning**: The feature update explicitly states the reduction of the free cancellation window to 12 hours. Therefore, the preconditions and expected outcomes of the test case have been updated to reflect this new 12-hour threshold. Specifically, the time frame for cancellation without penalty and the content of the confirmation modal have been adjusted to match the new policy. The verification of the help center link now points to the updated policy document.

**Assumptions Made**:
- It is assumed that the 'help center link' mentioned in the feature update refers to a link within the cancellation confirmation modal that directs users to the relevant policy documentation.
- It is assumed that the analytics event `shift_cancelled` will be covered in a separate, dedicated test case for analytics verification.

### Push-notification permission prompt and re-enabling
**File**: tc_003.json
**Updated**: 2025-09-25T18:10:55.636868

**Feature Impact**: The feature update directly modifies the free cancellation window from 24 hours to 12 hours. This necessitates an update to test cases that verify cancellation logic, specifically focusing on the new 12-hour threshold and the corresponding messaging.

**Changes Made**:
- **title**:
  - Before: Verify Pro cancellation within the 24-hour free cancellation window
  - After: Verify Pro cancellation within the 12-hour free cancellation window
- **preconditions**:
  - Before: A Pro has a booked shift. The current time is less than 24 hours but more than 0 hours before the shift start time.
  - After: A Pro has a booked shift. The current time is less than 12 hours but more than 0 hours before the shift start time.
- **steps[3].step_expected**:
  - Before: The modal displays: 'You can cancel up to 24 hours before start without penalty.'
  - After: The modal displays: 'You can cancel up to 12 hours before start without penalty.'
- **steps[6].step_expected**:
  - Before: The event includes the field 'free_cancellation_window_hours' with a value of 24.
  - After: The event includes the field 'free_cancellation_window_hours' with a value of 12.

**Why?**
**Reasoning**: The feature update explicitly states the reduction of the free cancellation window from 24 hours to 12 hours. The test case title, preconditions, and the expected text in the confirmation modal have been updated to reflect this new 12-hour window. Additionally, the analytics event verification has been updated to check for the `free_cancellation_window_hours` field with the new value of 12, as per acceptance criteria number 4. The step verifying the reliability score remains relevant as the feature update implies the penalty is applied *after* the 12-hour window.

**Assumptions Made**:
- The existing test case was designed to verify the free cancellation window functionality.
- The specific wording of the confirmation modal is crucial to user understanding and needs to be updated.
- Analytics events are a critical part of verifying feature behavior and must accurately reflect the new parameters.

## Summary

- **Total Test Cases Analyzed**: 2
- **Total Test Cases Updated**: 2
- **Analysis Entries**: 2
