# Frontend architecture

ShieldRAG uses React, strict TypeScript and Vite with React Router. Tailwind CSS and shared layout and feedback components give the Student and Admin workspaces consistent keyboard, mobile and desktop behavior. Lucide icons support text labels, and Instrument Sans is bundled locally. React Hook Form and Zod validate the login form.

| Directory | Responsibility |
| --- | --- |
| `frontend/src/app/` | Providers, canonical routes and route guards |
| `frontend/src/features/auth/` | Login form, Supabase session lifecycle and trusted profile |
| `frontend/src/lib/` | Configuration, Supabase SDK setup and typed FastAPI client |
| `frontend/src/components/`, `frontend/src/pages/` | Shared navigation, feedback and dashboard shells |
| `frontend/src/test/` | Vitest, Testing Library and MSW fixtures |

The app uses TanStack Query for server state. The auth store supplies the active session privately and invalidates both in-flight requests and cache data when it changes. The API client sends the current Bearer to a same-origin path, omits cookies, blocks redirects, supports cancellation and validates JSON responses with endpoint-specific schemas. It maps errors to curated messages by HTTP status and has no automatic request replay.

## Routes and deployment boundary

| Route | Behavior |
| --- | --- |
| `/`, `/login` | Resolve session and trusted profile. Show login for an anonymous visitor. |
| `/student`, `/admin` | Require the corresponding FastAPI-verified role. Pending sessions show loading feedback. |
| `/unauthorized` | Access-denied feedback with an account-specific way back. |
| Other paths | Application 404. |

Vite proxies `/api/v1` and `/health` to the configured development origin. For a production host, serve SPA routes from the frontend origin and forward the API prefix and liveness path to FastAPI before applying the `index.html` fallback. If a deployment requires a separate backend origin, use a same-origin reverse proxy or explicitly design a narrow origin allowlist and request policy for that deployment. The current client rejects absolute API URLs.

Only `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY` and `VITE_API_BASE_URL` are allowed into the app. Vite validates the set before embedding it and leaves invalid or missing configuration blank so the UI can explain setup. The proxy target remains in the Vite process. CI builds with synthetic config, checks the output for credential patterns and tests accidental private-key input. [Local startup and checks](../frontend/README.md).

A local Chromium check exercised the real Vite proxy against FastAPI. `/health` returned 200 and anonymous `/api/v1/me` returned 401. A separate browser check intercepted Supabase sign-in and profile responses to exercise reload, mobile navigation, role denial and sign-out. Manual sign-in with provisioned cloud accounts remains unverified.

Upcoming milestones cover document navigation, upload and review, indexing, RAG questions, audit and evaluation views. The current shell represents those features as upcoming.
