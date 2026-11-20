# Frontend authentication

The browser signs in with Supabase Auth's email/password SDK using the public project URL and publishable key. The Supabase SDK restores its own session and refreshes tokens. The app disables URL session detection and provides no signup or role-selection flow. [Supabase password sign-in](https://supabase.com/docs/reference/javascript/auth-signinwithpassword) · [Supabase auth state events](https://supabase.com/docs/reference/javascript/auth-onauthstatechange).

## Session and role resolution

1. Observe the SDK's initial session and subsequent auth events. Keep protected routes in a loading state while checking access.
2. Send the authenticated access token to FastAPI `GET /api/v1/me`.
3. Validate a UUID `id`, the `student` or `admin` role, and nullable `email` and `display_name`. Match the returned ID to the active session's user ID.
4. Render the workspace for that role. Missing profiles, unsupported roles and mismatched identities deny access.
5. On token or account changes, abort requests from the previous session, clear TanStack Query and recheck the profile. An expired or rejected token triggers one in-flight SDK refresh for that session, followed by a new profile check. API writes are never replayed automatically.
6. On sign-out, withdraw protected state immediately and ask the Supabase SDK to remove the current local session and request remote revocation. Suppress late session events and show a notice if remote confirmation fails.

Only the FastAPI response supplies the role. Bearer verification, authorization decisions and RLS remain on the backend. Frontend guards control navigation. A 403 or invalid profile denies access. The profile request uses the 12-second API deadline. On timeout, network failure or HTTP 503, the app keeps the session, hides protected content and offers a manual retry of `/me`. Only an authentication rejection or session expiry initiates session recovery. Sign-out and account changes cancel pending requests and discard their results. Errors displayed in the app come from fixed frontend messages.

## Browser storage and limits

Supabase stores the session in origin-scoped browser storage for reloads and cross-tab auth events. Same-origin script execution, including an XSS vulnerability, can access that storage. Use a trusted HTTPS origin, restrict script sources and dependencies, and avoid storing private application data in browser storage. Remote logout failure cannot confirm server-side refresh-token revocation. Already issued JWTs follow the provider's expiry rules.

Tests exercise intercepted HTTP and controlled auth events, including invalid credentials, expired tokens, missing profiles, timeouts and account switches. Live Student and Admin sign-in through this frontend remains unverified. Manual sign-in requires an already provisioned account and a reachable Supabase project. Account signup, invite acceptance, password reset UI and interactive MFA are outside this milestone. [Setup and test commands](../frontend/README.md).
