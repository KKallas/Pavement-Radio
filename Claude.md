# Pavement Radio — Claude Code Briefing

## What This Is

**Pavement Radio (PR)** is a platform for location-triggered interactive audio tours. Local guides author routes. Local businesses sponsor checkpoints. Walkers experience the city as a layered narrative — ghost sounds, story narration, puzzle triggers — delivered through a GPS-aware web app with no native install required.

The abbreviation **PR** is intentional brand strategy. It means something to business owners before you explain the product.

> *A city as a game board, narrated by ghosts, funded by bars.*

---

## Core Mechanic

A walker opens the PR web app and selects a tour. As they move through the city, GPS coordinates, QR code scans, or WiFi hotspot connections trigger pre-authored audio segments. The audio can include ambient soundscapes (horse carriages, steam machinery, crowd noise from another century), narration, character dialogue, and puzzle hints. LLM-generated audio layers over the fixed tracks — pre-rendered from walker history and behaviour choices made earlier in the tour, personalised and waiting before the waypoint is reached.

The time-loop puzzle mechanic is a first-class design feature: tours can be authored so that an object, phrase, or action encountered at the end retroactively explains something from the beginning. Walkers carry information backward through story time while moving forward through physical space.

---

## Tour Authoring

The platform separates **locations** from **stories**. This distinction is the core of the business model.

A **location** is platform infrastructure: physical coordinates, an ESP32 checkpoint ID, a sponsor contract, and a verified physical presence. The sponsor owns the location node. It knows nothing about any story.

A **tour** is a sequence of location references dressed in a narrative skin. It subscribes to locations and brings its own audio layers, character voices, prompt templates, and puzzle logic. The same bar can appear in ten tours simultaneously — a 1920s speakeasy, a Cold War dead drop, a dystopian 2089 freighter crew's last shore leave — and the sponsor gets foot traffic from all of them. Same checkpoint, same conversion mechanic, ten different conversations between the walker and a barman who has no idea which century just walked in.

Each waypoint in a tour definition has:
- a location reference (platform location ID)
- trigger type: GPS radius, QR code, WiFi hotspot
- audio assets: ambient layer + narration + character dialogue, specific to this tour's narrative frame
- optional LLM prompt template: variables filled from walker state at pre-render time
- optional puzzle state: sets or reads a session flag
- narrative instruction to the walker (what to do, what to say, what to order)

Tour makers set the narrative frame (Ankh-Morpork city guard, casino heist, Cold War spy drop, ghost from 1847) and the platform handles delivery. The location owner never needs to know the story. The story author never needs to negotiate with the location — the platform holds the sponsorship contract and splits the payment.

---

## Sponsor Model

Sponsors are local businesses. They set a **budget cap** and a **per-registered-walker payment**. When a walker hits their checkpoint, the escrow system logs the event. Payment releases on confirmation (ESP32 token, QR scan). The platform handles accounting and settlement. Tours are free for walkers; tips to tour makers are optional. The platform takes a cut of sponsor payments.

A sponsored location earns from every tour that routes through it. The sponsor signs once, gets included in all narratives. This is a **conversion funnel with a story wrapped around it**. That is the pitch to local businesses.

---

## Technical Architecture (starting point, open to revision)

**Frontend:** Single HTML file MVP first — no framework dependency, runs in mobile browser, uses the Web Geolocation API, Web Audio API, and localStorage for walker state. Designed to be shareable as a URL with the tour ID as a parameter or fragment. The tour definition is a **game cartridge** — a JSON or Markdown file loaded from a URL. The player is the browser. The city is the board.

**LLM audio pre-render pipeline:** Personalised audio is never generated live. The system tracks walker pace and GPS trajectory, predicts waypoint arrival time, and fires a Python script 90–190 seconds before the walker is expected to hit the trigger. The script runs in an isolated sandbox, calls ElevenLabs (or any TTS API — swappable), writes the rendered audio file to the sandbox directory, and exits. When the waypoint triggers, the file is already warm and plays immediately. No streaming latency, no failed API call mid-story.

Tour guides author a **prompt template** and select a voice model. Walker state — waypoints visited, choices made, dwell times, paths taken — populates the template variables at render time. Two walkers on the same tour hear subtly different versions of the same scene without the guide writing two tours. The guide writes the skeleton, the walker's behaviour writes the flesh. The sandbox isolation means the generation script has no access to anything outside its own directory — the tour guide's Python runs with no elevated permissions and produces exactly one file. If render fails, the static fallback audio plays. The walker never knows.

**WiFi hotspot checkpoint:** The walker receives an audio instruction to connect to a named network (e.g. "connect to BlackDogBar"). That network is a battery-powered ESP32 acting as a WiFi access point, running a minimal HTTP server on its local IP. The walker's browser hits `192.168.1.1/checkpoint`, receives a signed token or story fragment, disconnects, and continues. No platform API dependency, no NFC, no Bluetooth, no manufacturer whose terms might change next quarter. The instruction layer (audio) makes the human perform the bypass action. The human hand is the API call.

The ESP32 runs on a duty cycle: active for 10 minutes, sleeping for 30. The walker must be physically present during the active window — dwell time inside the sponsor venue. The hardware enforces what the sponsor is paying for without any additional logic. Unit cost is a few euros, battery life extends to months, ships pre-configured. The duty cycle feeds directly into the narrative layer: "the signal only broadcasts at certain intervals — wait for it." The technical constraint is the fiction. We use human hands with instructions to bypass walls.

**Trigger types in priority order for MVP:** GPS radius → QR code → WiFi hotspot.

**Backend (phase 2):** Tour authoring interface, location registry, sponsor escrow accounting, walker analytics, payment settlement. Lightweight Python API (FastAPI) with a simple database. Sponsor dashboard shows checkpoint hits across all tours, conversion events, and remaining budget.

---

## README — Write This First

The README should do four things in order:

**1. Name the feeling** — one paragraph on what it feels like to use PR. You are walking a city you thought you knew. A voice from 1923 tells you something happened here. You turn a corner. Something happens.

**2. Explain the system** — tour makers, walkers, sponsors, the platform. One paragraph each. No jargon.

**3. Show the architecture** — a simple ASCII or Mermaid diagram: Tour JSON → Web App → GPS/QR/WiFi trigger → Audio playback → LLM pre-render pipeline → Sponsor checkpoint event → Escrow log.

**4. Define the MVP** — what the first working demo does: one hardcoded tour, GPS triggers only, no LLM, no sponsor payments. A walker opens a URL and hears a city come alive as they walk through it.

---

## Immediate Next Steps for Claude Code

1. Write the README as specified above.
2. Scaffold the repo: `/tour-engine` (frontend), `/api` (backend stubs), `/tours` (sample tour definitions), `/docs`.
3. Create a sample tour definition file — use Tallinn Old Town as the test case — with 4–5 waypoints, GPS coordinates, audio metadata, one QR trigger, and one WiFi hotspot trigger. Author it as two skins on the same locations: one medieval, one near-future.
4. Build the single-file HTML MVP that loads a tour JSON from a URL parameter, tracks GPS position, and logs waypoint hits to console (audio playback stubbed with placeholder text display).
5. Define the tour JSON schema formally once the MVP loop works.

---

## What This Actually Is (Read This When You Are Overengineering)

The walkers are the ghosts. Standing still on a busy street, hearing something no one else can hear, then moving with inexplicable purpose toward a bar where they order something specific and stare at the bathroom wall. To every bystander they are a minor urban mystery. Collectively they are a performance the city is staging without knowing it.

The city does not know it is a stage. The walkers do not know they are the cast. The bars do not know they are the set. It runs on a ten euro microcontroller sleeping in a box behind the beer taps.

This is Situationist International territory — the derive, the city as a text you read by walking — except Debord never figured out how to fund it with bar tabs and ESP32s.

The system should be self-perpetuating with minimal effort. A tour guide in Tallinn authors something strange at 2am. A walker in Prague stumbles into a location that belongs to four stories simultaneously. A bar owner notices the monthly number going up without understanding why. None of them need to know the whole picture for the thing to work. That is the design constraint and the aesthetic principle at the same time.

**Do not build more than the story needs. The gaps are load-bearing.**

---

## Voice and Tone

The platform is counter-culture in the best sense: it gives people a reason to be in a city and a permission structure to interact with strangers (the bartender, the doorman) without social anxiety. The narration style across all tour templates should feel like Terry Pratchett wrote the city guide and then a slightly drunk historian added footnotes. Warm, precise, funny at unexpected moments, never condescending.

---

*This document is the single source of truth for onboarding Claude Code into the PR project. Update it as decisions are made.*