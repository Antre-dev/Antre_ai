# Antre Remote — iOS companion app

Control and monitor the Antre agent on your laptop from your iPhone, from anywhere.

- **Home** — live activity feed (SSE), system status, auto-mode toggle
- **Chat** — talk to Antre remotely via `/chat`
- **Permissions** — approve/deny sensitive actions with **Face ID**
- **Settings** — server URL, connection test, security options

Built with **Expo SDK 57** (React Native, TypeScript, expo-router v7), sideloaded
with **SideStore**, built on **GitHub Actions + EAS**.

This folder lives inside the `Antre_ai` repository (with the Python backend).
The CI workflow that builds the app sits at the repo root:
`.github/workflows/build-ipa.yml`.

---

## Project layout

```
app/                  expo-router screens (tabs: home, chat, permissions, settings)
src/
  lib/api.ts          typed API client (status, chat, mode, activity, permissions)
  lib/activity.ts     SSE live-feed hook with auto-reconnect
  lib/settings.ts     persisted settings (expo-secure-store)
  lib/format.ts       display helpers
  components/         StatusCard, ActivityFeed, PermissionCard
  theme.ts            dark theme shared with the web UI
eas.json              EAS build profiles
.github/workflows/    (at repo root) build-ipa.yml — CI build → .ipa artifact
```

## Setup (one time, local)

1. `cd antre-ios && npm install`
2. `npx expo install --fix` — reconcile exact dependency versions for SDK 57
3. `npx expo-doctor` — should report no issues
4. `npm run start` and run it in **Expo Go** or a dev build to try the UI.

> Note: the real permissions screen needs the phase-2 backend endpoints
> (see "Backend contract" below). Everything else works against the web app
> that already runs on the homelab.

## Connecting to your homelab

The app is designed for **Tailscale** — install it on the homelab and the phone,
then enter `https://<host>.ts.net` in Settings. Zero config, encrypted, works
from anywhere, no port forwarding.

Make sure the web app binds `0.0.0.0` (the launcher in `main.py` already does).

## Building the .ipa with GitHub Actions

1. **One-time EAS setup** (needs your Expo account; run once anywhere):
   - `npx eas-cli login`
   - `cd antre-ios && npx eas-cli init` — links the project and writes
     `extra.eas.projectId` into `app.json` (commit that change)
   - `npx eas-cli credentials` — add your Apple ID + app-specific password,
     bundle id `com.antre.remote`. Free Apple IDs work (7-day signing).
2. **Expo token → GitHub secret**:
   - `npx eas-cli token:create` → save the value
   - GitHub repo → Settings → Secrets and variables → Actions → **EXPO_TOKEN**
3. **Run the build**: Actions tab → **Build IPA** → Run workflow.
   (It also runs automatically on push to `main` when `antre-ios/**` changes.)
4. Download `antre-remote.ipa` from the run's artifacts (or the URL in the run
   summary) and open it with **SideStore** on your iPhone. SideStore auto-resigns
   it, so no weekly reinstall needed.

> If your previous Expo + GitHub Actions + SideStore pipeline used a different
> recipe, reuse it — the important bits are `eas.json` and `app.json`.

## Face ID

`expo-local-authentication` handles it. The Permissions tab calls
`authenticateAsync` before `POST /api/permissions/{id}/approve`.
Face ID requires a real device (no simulator). The usage string is set in
`app.json` → `ios.infoPlist.NSFaceIDUsageDescription`.

## Backend contract (phase 2 — to implement)

New endpoints on the existing FastAPI app:

```
GET  /api/permissions/pending          → { requests: [ {id, tool, summary, danger_level, created_at, expires_at} ] }
POST /api/permissions/{id}/approve     → { ok: true }   (agent resumes the tool call)
POST /api/permissions/{id}/deny        → { ok: true }   (agent gets "denied")
```

Server-side plan: a pending-approval queue in `antre/permissions.py`. When a
tool needs approval, the agent registers a request, emits an activity event
(`type: "permission"`), and waits on an asyncio condition/queue (with TTL).
The phone polls or watches SSE; Face ID approve resolves the waiter.

## Roadmap

- [x] App scaffold (4 tabs, SSE, chat, Face ID UI, settings)
- [ ] Backend permission queue + `/api/permissions/*`
- [ ] Tailscale + end-to-end remote test
- [ ] Push notifications when a request needs approval
- [ ] Widget / live activity (iOS) showing agent status
