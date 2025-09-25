# Change Request: Waitlist for full shifts (Pro App)

change_type: new_feature

author: Product Manager

### Overview
Businesses occasionally over-book a shift and then need additional Pros as backups if someone cancels.  To streamline this, introduce a **waitlist** feature that lets Pros join a queue for a full shift.

### Acceptance criteria / User flows
1. A shift marked *Full* in the Open Shifts feed displays a **“Join waitlist”** button instead of **“Book shift.”**
2. After tapping “Join waitlist,” the Pro sees a confirmation toast: *“You’ve been added to the waitlist. We’ll notify you if a spot opens.”*
3. When another Pro cancels, the first user in the waitlist is automatically booked and receives a push notification.
4. Pros can remove themselves from the waitlist from the Gig Details screen.
5. Analytics event `waitlist_join` is fired with `{ shift_id, user_id }` when a Pro joins.
6. Waitlist order is FIFO.

### Definition of done
• Feature available behind remote-config key `enable_shift_waitlist` (default **off** in production).  
• All backend & mobile changes deployed and smoke-tested.
