# Change Request: Reduce free cancellation window to 12 hours

change_type: feature_update

author: Product Manager

### Overview
To improve marketplace reliability, the free cancellation window for booked shifts is being **reduced from 24 hours to 12 hours** before the shift start time.

### Acceptance criteria / User flows
1. If a Pro cancels **≥ 12 hours** before shift start, no reliability penalty is applied and the confirmation modal shows: *“You can cancel up to 12 hours before start without penalty.”*
2. If a Pro cancels **< 12 hours** before shift start, reliability score is reduced and modal explains the penalty.
3. The help center link in the modal is updated to the new policy doc.
4. Analytics event `shift_cancelled` must include new field `free_cancellation_window_hours = 12`.
