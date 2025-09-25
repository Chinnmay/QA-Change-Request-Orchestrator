# Change Request: Push-notification token not refreshed after re-enabling

change_type: bug_fix

author: QA engineer

### Overview
We discovered that when a Pro **turns OFF push notifications in Settings and then turns them back ON**, the device’s push token is *not* re-registered with the backend, resulting in missed notifications.

### Steps to reproduce
1. Launch Pro app with notifications **allowed**.  
2. Go to **Settings › Notifications** and toggle **Allow Push Notifications** **OFF**.  
3. Kill and relaunch the app (token is removed on backend).  
4. Return to Settings and toggle **Allow Push Notifications** **ON**.  
5. Observe via Charles/Proxyman: **no** `register_push_token` API call is sent.

### Acceptance criteria
- When toggling push notifications **ON**, the app sends `register_push_token` with a fresh token within 5 seconds.
- A success toast *“Notifications re-enabled”* is displayed.
- Token is present in Django admin under the user profile.
