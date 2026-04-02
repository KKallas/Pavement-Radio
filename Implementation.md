# Pavement Radio — Design Addendum
## Session Decisions & Locked Vocabulary

*This document extends the main Claude.md briefing with design decisions locked in the second design session. When these conflict with the original Claude.md, this document wins.*

---

## Locked Vocabulary

These words mean specific things. Use them consistently or the system becomes ambiguous.

**Waypoint** — a physical trigger point in space and the unit of story authoring. Exactly one trigger type: GPS coordinate with a radius, QR code ID, or ESP32 ID. One waypoint, one trigger. Each waypoint carries its own audio composition (four tracks), an optional list of prerequisite waypoints, and two audio sets: one for when prerequisites are met (on-track) and one for when they are not (off-track). The waypoint is what the author writes.

**Prerequisites** — the list of waypoint IDs that must be visited before this waypoint plays its on-track audio. If the walker arrives without having visited all prerequisites, the off-track audio plays instead — typically a narrator redirecting them to the right place. Prerequisites replace the old event/arc model. The author defines order through prerequisites, not through directed connections.

**Session** — the accumulated state of one walker's run through a tour. Contains a **visited set** (which waypoint IDs the walker has triggered) and a **path log** (append-only ordered array of visited waypoint IDs). Lives in localStorage. The pre-render pipeline reads this.

**Path log** — the ordered visit history. The full log enables retroactive narrative — a late waypoint can reference what the walker experienced first.

**Composition** — the audio content of one waypoint. Always four tracks (see below). Each waypoint has two compositions: **on-track** (prerequisites met) and **off-track** (prerequisites not met). The author can check "same audio" to use one composition for both states.

**Pre-render** — a Python script that runs when the walker is approaching a waypoint, using session state to personalise the composition audio before arrival. Produces warm files. Never runs live.

**Prefetch radius** — 100 metres. When any waypoint comes within this radius, its pre-render fires speculatively. All plausible nearby waypoints warm simultaneously. The walker never waits.

**Cartridge** — the complete tour definition file. A plain Python file (`cartridge.py`). Human-readable and hand-editable. The authoring tool exports this. The player loads and executes this inside a sandbox. Authors can write it directly in any text editor — the GUI is a convenience, not a requirement. Running `python cartridge.py` directly self-verifies the package. An unsigned cartridge does not run, anywhere, ever.

---

## Session State Model

```
session: {
  tour_id: string,
  skin: string,                      // which narrative skin is active
  visited: Set<waypoint_id>,         // which waypoints have been triggered
  path: [waypoint_id, ...],          // ordered visit history
  current_waypoint: waypoint_id | null,
  warm_waypoints: [waypoint_id, ...] // pre-rendered, ready to play
}
```

When a walker triggers a waypoint, the player checks `visited` against the waypoint's `requires` list. If all prerequisites are in `visited`, the on-track composition plays. If not, the off-track composition plays. Either way, the waypoint ID is added to `visited` and appended to `path`.

---

## The Four-Track Audio Model

Every composition has exactly four tracks. They mix independently. When compositions overlap — because the walker moved fast between waypoints, or doubled back — tracks mix per-channel, not per-waypoint. This is also the localisation boundary: swap the VO track for a different language, everything else stays identical.

**ATMO** — continuous ambient soundscape. Fades slowly. When a new event starts, its ATMO crossfades into the previous event's ATMO (or the global tour atmo if no previous event). Never cuts hard. The city always sounds like somewhere.

**SFX** — all foley and point effects. Footsteps on cobblestones, a door, a bell, a gunshot in 1923. Fires on cue, does not loop. Can stack — multiple SFX fire independently.

**DIALOGUE** — in-story character voices. The barman. The ghost. The Soviet officer. These are authored voices, pre-recorded or TTS-rendered per skin. They are characters inside the fiction.

**VO** — the narrator voice. Outside the fiction, addressing the walker directly. The Terry Pratchett footnote voice. This is the track most likely to be personalised by the pre-render script, because it knows the walker's session state and speaks to them specifically.

Track mixing rules for overlapping waypoints:
- ATMO: crossfade, longer composition wins
- SFX: both play, user hears layered foley
- DIALOGUE: queue, do not overlap — finish current line before next
- VO: queue, do not overlap — VO is never interrupted

---

## Cartridge Schema (working draft)

The cartridge is a Python file (`cartridge.py`) with the tour definition as Python dicts/lists. No YAML. The schema below shows the structure:

```python
TOUR = {
    "id": "string",
    "title": "string",
    "skin": "string",                      # narrative frame label
    "global_atmo": "audio_asset_ref"       # plays under everything, always
}

WAYPOINTS = [
    {
        "id": "string",
        "name": "string",
        "trigger": {
            "type": "gps | qr | esp",
            "coords": [lat, lng],          # if gps
            "radius_m": 20,                # if gps, default 20m
            "qr_id": "string",            # if qr
            "esp_id": "string",            # if esp
        },
        "requires": ["waypoint_id", ...],  # must visit these first for on-track audio
        "same_audio": True,                # if True, on-track plays in both states

        # on-track: plays when all prerequisites are met
        "tracks_on": {
            "atmo": "atmo/on/asset.opus",
            "sfx": "sfx/on/asset.opus",
            "dialogue": "dialogue/on/asset.opus",
            "vo": "vo/on/asset.opus"
        },

        # off-track: plays when prerequisites are NOT met
        # typically the narrator redirecting the walker
        "tracks_off": {
            "atmo": "atmo/off/asset.opus",
            "sfx": None,
            "dialogue": None,
            "vo": "vo/off/redirect.opus"   # "You haven't been to the town hall yet..."
        },

        # optional pre-render (phase 2)
        "prerender": {
            "script": "path_to_python",
            "human_description": "string", # SOURCE OF TRUTH — script is compiled artifact
            "output_track": "vo"           # which track receives the rendered file
        }
    }
]
```

Each waypoint is self-contained. The `requires` list defines the intended visit order. The `tracks_on`/`tracks_off` split lets the author guide walkers who arrive out of sequence — the off-track VO can redirect them ("Turn around, head to the town square first") without breaking the experience. When `same_audio` is True, `tracks_on` plays regardless of prerequisite state.

The `human_description` field on the pre-render script is mandatory and is the source of truth. If the script and the description diverge, the description wins and the script gets regenerated. This is the debugging interface, not the code.

---

## Authoring Tool — MVP UIX (`editor.html`)

A single HTML file. No framework. Leaflet.js for the map (CartoDB Dark Matter tiles, free). The tool exports a `.pr` zip package. localStorage autosaves metadata continuously. Audio blobs live in IndexedDB.

**Two modes (toolbar):**

**Navigate mode** — pan and zoom the map. Tap a waypoint to open its editor panel. This is the default.

**Place mode** — tap anywhere on the map to drop a new waypoint. Each waypoint appears as a circle with its trigger radius.

**Map canvas (full screen)** — dark-themed city map. Waypoints render as green circles (radius visualised). Waypoints with prerequisites show in blue with a `[n]` badge indicating prerequisite count. Dashed amber arrows show prerequisite dependencies between waypoints — the intended visit order is visible at a glance without reading any config.

**Waypoint editor panel (slide-up sheet on tap)** — everything about one waypoint:
- **Name** — editable text field
- **Coordinates** — lat/lng number inputs (editable for precise placement)
- **Trigger radius** — slider 5–100m with numeric display
- **Prerequisites** — dropdown to add other waypoints as prerequisites, each listed with a delete button. Empty by default — the author explicitly opts into ordering
- **Same audio checkbox** — shown when prerequisites exist. Checked by default (one set of audio plays regardless of prerequisite state). Uncheck to reveal the on-track/off-track tab switcher
- **Audio tracks** — four track rows (ATMO, SFX, DIALOGUE, VO). Each row: upload button, filename display, play/pause, delete. When "same audio" is unchecked, two tabs switch between on-track (green, plays when prerequisites met) and off-track (amber, plays when prerequisites not met — the narrator redirects the walker)
- **Delete waypoint** — removes the waypoint and cleans up all prerequisites that reference it

**Save/Open buttons (toolbar):**
- **Save** — builds and downloads a `.pr` zip package: `cartridge.py` (with self-verification), `manifest.json` (sha256 of every file), and audio assets organised in `atmo/`, `sfx/`, `dialogue/`, `vo/` directories with `on/`/`off/` subdirectories
- **Open** — uploads a `.pr` zip, parses the Python dicts from `cartridge.py`, loads audio blobs from the zip, restores everything on the map

The map is not decorative. The map is the editor. Geography and narrative are the same axis.

---

## Pre-Render Pipeline Logic

```
walker position updates every 3 seconds
↓
calculate distance to all waypoints
↓
any waypoint within 100m?
  → fire pre-render script for that waypoint
  → pass: session.visited, session.path, waypoint.requires
  → script writes rendered audio to warm_waypoints cache
  → timeout: if script fails after 30s, mark fallback
↓
walker hits waypoint trigger radius (default 20m)
  → check session.visited against waypoint.requires
  → all prerequisites met? → play on-track composition
  → prerequisites missing? → play off-track composition
  → play warm (pre-rendered) composition if available, static fallback if not
  → add waypoint_id to session.visited
  → append waypoint_id to session.path
```

Pre-render scripts are sandboxed: they receive a session JSON on stdin, write one audio file to a designated output path, and exit. No network access except to TTS APIs. No filesystem access outside their sandbox directory. A malicious tour author cannot reach anything outside their own waypoint's pre-render output.

---

## Branch Logic

The system does not enforce a linear sequence. The walker can visit waypoints in any order. Prerequisites determine what they *hear*, not where they can *go*.

A walker who arrives at a waypoint without having visited its prerequisites hears the off-track composition — typically the narrator redirecting them: "You should visit the town hall first. Head north through the square." The waypoint still registers as visited. When the walker has completed the prerequisites and returns, the on-track composition plays. The city teaches sequence through narration, not through walls.

If `same_audio` is true (the default when no prerequisites are set), the same four tracks play regardless of visit order. The author only needs to think about on-track/off-track when they explicitly add prerequisites — the complexity is opt-in.

The prefetch radius (100m) prepares all nearby waypoints simultaneously. The player pre-renders both on-track and off-track compositions when approaching a waypoint with prerequisites, since it cannot know in advance which the walker will need.

---

## Localisation Model

The four-track architecture is the localisation boundary. A tour in Estonian is the same cartridge with the DIALOGUE and VO tracks swapped for Estonian-language assets. ATMO and SFX are universal — cobblestones sound the same in every language.

The cartridge schema supports a `locale/` directory in the package that maps locale codes to alternative asset refs for DIALOGUE and VO tracks. The player selects locale at tour start (or inherits from browser preference) and loads the appropriate track assets. One cartridge, multiple languages, no structural changes.

---

## Cartridge Signing & Verification

The cartridge is a plain Python file. No custom header format, no comment-block syntax — just Python variables and a few lines of verification code at the bottom. The file is the signing system.

### Key Infrastructure

Authors generate an Ed25519 keypair on platform registration. The private key never leaves their machine. The public key is submitted to the platform registry and associated with their author identity. Registration is where the platform fee is collected — the keypair is the receipt.

### What the Cartridge Looks Like

```python
"""Tallinn Old Town — Medieval Skin"""

# --- identity ---
AUTHOR = "kaspar@pavementradio.io"
PUBKEY = "AAAAC3NzaC1lZDI1NTE5AAAAI..."
SIGNATURE = "base64encodedsignature..."
SIGNED_AT = "2026-03-31T21:00:00Z"
MANIFEST_HASH = "9f8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c3b2a1f0e9d8c7b6a5f4e3d2c1b0a9f8e"

# --- tour definition ---
TOUR = {
    "id": "tallinn-old-town-medieval",
    "title": "Tallinn Old Town",
    "skin": "medieval",
    "global_atmo": "atmo/on/old-town-rain.opus",
}

WAYPOINTS = [
    {
        "id": "viru-gate",
        "name": "Viru Gate",
        "trigger": {"type": "gps", "coords": [59.4365, 24.7490], "radius_m": 20},
        "requires": [],
        "same_audio": True,
        "tracks_on": {
            "atmo": "atmo/on/old-town-rain.opus",
            "sfx": "sfx/on/cobblestone-steps.opus",
            "dialogue": None,
            "vo": "vo/on/intro-narration.opus"
        },
        "tracks_off": {
            "atmo": "atmo/on/old-town-rain.opus",
            "sfx": "sfx/on/cobblestone-steps.opus",
            "dialogue": None,
            "vo": "vo/on/intro-narration.opus"
        }
    },
    {
        "id": "town-hall",
        "name": "Town Hall",
        "trigger": {"type": "gps", "coords": [59.4370, 24.7453], "radius_m": 20},
        "requires": ["viru-gate"],          # must visit Viru Gate first
        "same_audio": False,
        "tracks_on": {
            "atmo": "atmo/on/town-square-bustle.opus",
            "sfx": "sfx/on/church-bell.opus",
            "dialogue": "dialogue/on/ghost-monologue.opus",
            "vo": "vo/on/town-hall-history.opus"
        },
        "tracks_off": {                     # walker skipped Viru Gate
            "atmo": "atmo/off/town-square-quiet.opus",
            "sfx": None,
            "dialogue": None,
            "vo": "vo/off/redirect-to-viru.opus"  # "Start at the gate. Head east."
        }
    },
    # ...
]

REVENUE_SPLIT = {
    "tour_maker": 0.70,
    "platform": 0.20,
    "settlement": 0.10
}

# --- self-verification (runs when you execute this file directly) ---
if __name__ == "__main__":
    import hashlib, json, os, sys

    def verify():
        cart_dir = os.path.dirname(os.path.abspath(__file__))
        manifest_path = os.path.join(cart_dir, "manifest.json")
        if not os.path.exists(manifest_path):
            print("No manifest.json found.")
            return False
        manifest_bytes = open(manifest_path, "rb").read()
        if hashlib.sha256(manifest_bytes).hexdigest() != MANIFEST_HASH:
            print("FAIL: manifest.json modified since signing.")
            return False
        manifest = json.loads(manifest_bytes)
        for filepath, entry in manifest["files"].items():
            full_path = os.path.join(cart_dir, filepath)
            if not os.path.exists(full_path):
                print(f"FAIL: missing {filepath}")
                return False
            data = open(full_path, "rb").read()
            if len(data) != entry["size"]:
                print(f"FAIL: size mismatch {filepath}")
                return False
            if hashlib.sha256(data).hexdigest() != entry["sha256"]:
                print(f"FAIL: checksum mismatch {filepath}")
                return False
        declared = set(manifest["files"].keys()) | {"manifest.json", "cartridge.py"}
        for root, dirs, files in os.walk(cart_dir):
            for f in files:
                rel = os.path.relpath(os.path.join(root, f), cart_dir)
                if rel.startswith("."):
                    continue
                if rel not in declared:
                    print(f"FAIL: undeclared file {rel}")
                    return False
        print(f"OK: {len(manifest['files'])} files verified.")
        print(f"    tour: {TOUR['title']}")
        return True

    sys.exit(0 if verify() else 1)
```

That's the whole thing. A tour author opens `cartridge.py` in any editor, reads the tour definition as plain dicts and lists, and runs `python cartridge.py` to verify nothing has been tampered with. No SDK install needed for basic verification — just Python and the standard library.

The Ed25519 signature verification (checking `SIGNATURE` against `PUBKEY`) requires `cryptography` and runs in the platform player and the `pr` CLI. The self-verification at the bottom is intentionally limited to checksum validation — the thing an author does twenty times a day while building. Full cryptographic verification is for the player and the publish pipeline.

### Three Trust Tiers

**Platform-verified** — signed, author registered, fee paid. Appears in the tour directory. Eligible for sponsor routing and revenue share. Walker sees a clean play interface with no warnings.

**Community-signed** — signed with a known Ed25519 keypair, author not registered with the platform. Plays with a visible "independent author" badge. The walker knows who made it — the keypair is a persistent identity — but the platform has not vetted or taken a fee. No directory listing, no sponsor routing, no revenue share.

**Unsigned** — hard stop by default. Walker can explicitly opt in with one deliberate tap. UI language is neutral and accurate: *"This tour has not been verified by Pavement Radio. The author has not registered with the platform."* Not "dangerous." A fact. The walker decides. Unsigned tours have no economic identity — you cannot earn from one even if a thousand people walk it.

The opt-in exists because authors testing their own tours before publishing should not need to register first. It is not a loophole.

### Signing as Economic Identity

The signature is the author's identity inside the platform's economics. Per-walker analytics, author revenue share, the review system, sponsor checkpoint attribution — all of it anchors to the keypair. Crossing the signing threshold is how an author becomes part of the ecosystem rather than adjacent to it.

### Author CLI

```bash
pr keygen                      # generates keypair, stores private key locally
pr sign my-tour/cartridge.py   # signs with ~/.pr/private.key, writes SIGNATURE variable
pr verify my-tour/             # full chain: signature → manifest → assets
pr publish my-tour/            # sign + pack + upload to platform registry
```

The private key never touches the platform. The platform cannot forge an author's signature even if compromised. That is the security property that makes the whole thing trustworthy.

---

## Cartridge Package Format (`.pr`)

The cartridge is not just a signed Python file — it is a self-contained archive that ships everything the player needs to run the tour offline. The `.pr` is a standard ZIP file with a fixed internal layout. The player unzips it, verifies integrity, and plays. No network dependency after download.

### Package Layout

```
my-tour.pr
│
├── cartridge.py                    # the signed Python file (entry point)
├── manifest.json                   # file inventory with checksums
│
├── atmo/
│   ├── on/                         # on-track (prerequisites met)
│   │   ├── old-town-rain.opus
│   │   └── tavern-interior.opus
│   └── off/                        # off-track (prerequisites not met)
│       └── town-square-quiet.opus
│
├── sfx/
│   ├── on/
│   │   ├── door-creak.opus
│   │   └── cobblestone-steps.opus
│   └── off/
│
├── dialogue/
│   ├── on/
│   │   ├── ghost-monologue.opus
│   │   └── barman-greeting.opus
│   └── off/
│
├── vo/
│   ├── on/
│   │   ├── intro-narration.opus
│   │   └── town-hall-history.opus
│   └── off/
│       ├── redirect-to-viru.opus   # "Start at the gate. Head east."
│       └── redirect-to-square.opus
│
└── locale/
    └── et/                          # Estonian localisation
        ├── dialogue/
        │   └── on/
        │       └── ghost-monologue.opus
        └── vo/
            ├── on/
            │   └── intro-narration.opus
            └── off/
                └── redirect-to-viru.opus
```

The four top-level asset directories mirror the four-track audio model: `atmo/`, `sfx/`, `dialogue/`, `vo/`. Each has `on/` and `off/` subdirectories for the two audio states. When `same_audio` is true, the `off/` directory is either empty or contains duplicates of the `on/` assets. The `locale/` directory holds per-language overrides for DIALOGUE and VO only — ATMO and SFX are universal.

Asset format is Opus (`.opus`) — small files, wide browser support, good at low bitrates for voice. The player MAY accept `.mp3` and `.wav` as fallbacks, but Opus is the default export from the authoring tool.

### `manifest.json`

The manifest is the integrity contract. Every file in the archive (except `manifest.json` itself) has an entry with its sha256 hash and byte size.

```json
{
  "version": 1,
  "tour_id": "tallinn-old-town-medieval",
  "created_at": "2026-03-31T14:00:00Z",
  "files": {
    "cartridge.py": {
      "sha256": "a3f9c2d1e8b47f3a9c0d2e1f8b47a3f9c2d1e8b47f3a9c0d2e1f8b47f3a9c0d",
      "size": 12480
    },
    "atmo/old-town-rain.opus": {
      "sha256": "7d3e8f1a2b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e",
      "size": 245760
    },
    "sfx/door-creak.opus": {
      "sha256": "1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b",
      "size": 18432
    }
  }
}
```

### Signing Covers the Manifest

The `SIGNATURE` in `cartridge.py` signs everything in the file except the `SIGNATURE` variable itself. Since `MANIFEST_HASH` is a variable in that same file, the signature transitively covers every asset in the package.

The chain of trust:

```
author's Ed25519 private key
  └─ signs → cartridge.py (all variables except SIGNATURE itself)
                └─ MANIFEST_HASH variable verifies → manifest.json
                                                       └─ manifest.json verifies → every asset file
```

One signature protects the entire package. Tampering with any single byte in any file — the Python script, the manifest, or any audio asset — breaks the chain.

### Verification Levels

**Quick check (author workflow)** — run `python cartridge.py` in the tour directory. Uses only the standard library. Walks the manifest and checks every file's sha256 and size. Reports missing files, undeclared files, checksum mismatches. No cryptography needed — this is for the author iterating on their tour locally.

**Full verification (player and publish pipeline)** — the `pr verify` CLI command or the browser player's JS equivalent. Verifies the Ed25519 signature on `cartridge.py` against the `PUBKEY`, then walks the manifest chain exactly like the quick check. A file present in the archive but absent from the manifest is treated as tampering, not as a harmless extra. The manifest is an exhaustive inventory. No undeclared cargo.

### Author CLI (updated)

```bash
pr pack my-tour/               # validates layout, builds manifest.json,
                               # writes MANIFEST_HASH into cartridge.py,
                               # signs cartridge.py, zips into my-tour.pr

pr verify my-tour.pr           # full chain verification: sig → manifest → assets
                               # (or just: cd my-tour/ && python cartridge.py
                               #  for quick checksum-only verification)

pr unpack my-tour.pr           # extracts to my-tour/ for editing

pr publish my-tour.pr          # verify + upload to platform registry
```

The `pr pack` command is the only path to a valid `.pr` package. It:
1. Reads all files from the tour directory
2. Computes sha256 for every asset
3. Writes `manifest.json`
4. Computes sha256 of `manifest.json` and writes `MANIFEST_HASH` into `cartridge.py`
5. Signs `cartridge.py` with `~/.pr/private.key`, writes `SIGNATURE` variable
6. Zips everything into `my-tour.pr`

The order is strict because each step depends on the previous hash. The author cannot hand-edit `cartridge.py` after packing without invalidating the signature — `pr pack` is the last step, always.

### Player-Side Unpacking

The player (browser) receives the `.pr` zip via URL, fetches it, and:

1. Unzips into an in-memory or IndexedDB-backed virtual filesystem
2. Reads `cartridge.py` as text, parses out `PUBKEY`, `SIGNATURE`, `MANIFEST_HASH`, and the tour data (the player reads the Python as structured text — it does not execute Python in the browser)
3. Verifies Ed25519 signature using `crypto.subtle` — if it fails, hard stop (TAMPERED) or user opt-in (UNSIGNED)
4. Verifies `manifest.json` sha256 matches `MANIFEST_HASH`, then checks every asset file against the manifest
5. Resolves asset references (e.g. `atmo/old-town-rain.opus`) against the unpacked files
6. Caches the unpacked tour in IndexedDB for offline replay — keyed by `tour_id + manifest hash`

A cached tour whose hash matches is never re-verified. A re-download with a different hash triggers full re-verification. The walker can play offline indefinitely once the package is cached.

The browser-side verification uses the same chain of trust as the Python self-verification — just implemented in JS with Web Crypto. No Python runs in the browser. The cartridge's Python is only executed by the pre-render pipeline (server-side) and by authors locally.

### Size Constraints

No hard limit on package size, but the authoring tool warns above 50MB and blocks above 200MB. Most tours will be 5–30MB — voice-quality Opus at 24kbps is roughly 180KB per minute. A 45-minute tour with full four-track coverage fits comfortably in 20MB.

---

## What to Build First

1. The single-file HTML player (`index.html`) — loads a `.pr` package from a URL parameter, watches GPS position, fires waypoint triggers, checks prerequisites, plays on-track or off-track audio accordingly. One hardcoded Tallinn Old Town tour with 4–5 waypoints, GPS triggers only.

2. The authoring tool (`editor.html`) — map canvas, waypoint editor with prerequisite management and dual audio set authoring, `.pr` zip export/import. *(Built — see editor.html)*

3. The cartridge schema validator — a Python script that reads a `cartridge.py` and reports errors: missing prerequisites, orphaned asset references, broken prerequisite chains (circular dependencies).

4. The pre-render sandbox — a Python script runner that accepts session JSON on stdin, executes a waypoint's pre-render script in isolation, and writes one audio file out.

5. The identity manager (`identity.html`) — generate Ed25519 keypair, choose handle, export/import key. Shared across all tools on the same origin. *(Built — see identity.html)*

6. The audio recorder and editor (`recorder.html`) — record from microphone with GPS tagging and Ed25519 signing, import external audio files, trim, destructive composite, loop fade, plugin architecture placeholders. Export signed audio with provenance sidecar JSON.

The player, authoring tool, recorder, and identity manager are all single HTML files. They share nothing at runtime except the Ed25519 identity (via shared IndexedDB/localStorage on the same origin). The `cartridge.py` inside the `.pr` zip is the contract between player and editor. The sidecar JSON is the contract between recorder and editor.

---

## Audio Recorder & Editor (`recorder.html`) — Design (2026-04-02)

### The Problem

Tour makers need audio. The four-track model (ATMO, SFX, DIALOGUE, VO) requires a steady supply of field recordings, voice takes, and ambient captures. Currently, tour makers bring their own audio files with no provenance metadata — no one knows where a recording was made, when, or by whom. If a tour uses a beautiful rain ambience from Tallinn's Old Town, there is no way for another tour maker to find it, credit it, or visit the same spot to record more.

The audio layer should be a shared commons. Not a centralised library — a signed, attributable pool where every clip carries its own provenance and anyone can verify who recorded it, where, and when.

### Core Concept

Anyone can record audio and sign it with their Ed25519 identity. The recording carries embedded metadata: GPS coordinates, timestamp, recorder's public key, and a signature over the raw audio data. This metadata is permanent and non-removable — it is the recording's birth certificate.

When a tour maker uses a signed clip in their tour, the provenance chain is visible: the tour's `cartridge.py` references an audio file, that file carries a signature, that signature traces back to a public key, that public key traces back to a person who stood at specific coordinates at a specific time and pressed record. Anyone can verify this. Anyone can visit the same location. Anyone can find other tours that use the same clip, or other clips by the same recorder.

The recordings are not uploaded anywhere automatically. The recorder exports files. The tour maker imports them into the editor. The files carry their provenance with them wherever they go — on a USB stick, in a shared folder, in a zip file attached to an email. The metadata is in the file, not in a database.

### Recording

The recorder is a single HTML file. It uses the MediaRecorder API to capture audio from the device microphone. It uses the Geolocation API to tag the recording with coordinates. It uses the Web Crypto API to sign the result with the user's Ed25519 keypair (generated on first launch, same as walker identity — same key if the recorder and player share an origin, separate key otherwise).

**Recording flow:**

```
User taps Record
  → MediaRecorder starts capturing from microphone
  → GPS position sampled at start and end of recording
  → User taps Stop
  → Raw audio is captured as a WAV or Opus blob
  → Metadata is assembled:
      {
        recorder_pubkey: "base64...",
        location: { lat: 59.4370, lng: 24.7453, accuracy_m: 8 },
        recorded_at: "2026-04-02T14:30:00Z",
        duration_s: 47.2,
        sample_rate: 48000,
        format: "wav"
      }
  → Signature is computed over: sha256(audio_bytes) + metadata JSON
  → File is stored locally in IndexedDB with metadata
```

The signature covers the raw audio data and the metadata together. If either is modified after recording, the signature breaks. This means:

- You cannot re-tag a recording with a different location
- You cannot claim someone else's recording as yours
- You cannot silently alter the audio and keep the original provenance
- You *can* derive a new clip from the original (edit, trim, process) — but the derived clip gets a new signature and its metadata includes a `derived_from` field pointing to the original's hash. The provenance chain is explicit.

### Import from External Recorder

Not everyone records with their phone. Some people use dedicated field recorders, shotgun mics, binaural rigs. The recorder tool handles this:

**Import flow:**

```
User taps Import
  → File picker accepts .wav, .mp3, .opus, .flac, .ogg
  → Audio is loaded into the editor
  → User is prompted to add location:
      - Use current GPS position ("I'm at the recording location now")
      - Enter coordinates manually
      - Pick on map (same Leaflet map as the editor)
      - Leave blank ("location unknown" — still usable, just not geo-tagged)
  → User confirms
  → File is signed with recorder's Ed25519 key
  → Metadata notes: source: "imported", original_filename: "zoom-h6-take-042.wav"
  → Stored in IndexedDB
```

The imported file gets the same provenance treatment as a live recording. The `source: "imported"` flag is honest — anyone checking the metadata knows this was not captured live through the browser. The signature still guarantees who imported it and when.

### Audio Editor

The editor is destructive — it modifies the actual audio buffer. There is no undo history beyond the last save. This is intentional: the audio files must be small and final for tour packaging. Non-destructive editing belongs in a DAW, not in a mobile browser tool.

All editing operates on a single audio buffer (an `AudioBuffer` from the Web Audio API). The waveform is rendered to a `<canvas>` element with touch-draggable selection regions.

#### Core Operations

**Trim** — select a region by dragging on the waveform. Cut everything outside the selection. This is the most-used operation: a 3-minute field recording becomes a 15-second ambient loop.

**Destructive composite** — select a region containing a click, pop, footstep, or unwanted transient. The editor replaces the selection with interpolated audio from the surrounding context. Implementation: crossfade the samples immediately before the selection into the samples immediately after, with a cosine blend across the gap width. This is not noise removal — it is a surgical patch. Good enough for removing a cough from a 30-second atmo recording. Not good enough for removing traffic from a voice-over. That is what the plugin architecture is for.

**Loop fade** — for ambient tracks that need to loop seamlessly. The editor takes the last N seconds and the first N seconds of the buffer, crossfades them into each other, and writes the result as the new start/end. The loop point becomes inaudible. N is configurable (default 2 seconds). The waveform display shows the loop boundary with a visual marker.

#### Plugin Architecture

The editor has slots for audio processing plugins. Each plugin is a function that receives an `AudioBuffer` (or a selected region of one) and returns a modified `AudioBuffer`. Plugins are not loaded from external sources — they are defined in the HTML file itself, each in a clearly marked block.

**Plugin interface:**

```javascript
// Every plugin implements this shape
{
  id: "compressor",
  name: "Compressor",
  description: "Reduce dynamic range",
  params: [
    { id: "threshold", name: "Threshold", type: "range", min: -60, max: 0, default: -24, unit: "dB" },
    { id: "ratio", name: "Ratio", type: "range", min: 1, max: 20, default: 4, unit: ":1" },
    { id: "attack", name: "Attack", type: "range", min: 0.001, max: 0.1, default: 0.01, unit: "s" },
    { id: "release", name: "Release", type: "range", min: 0.01, max: 1, default: 0.1, unit: "s" },
  ],
  process: function(audioBuffer, selection, params) {
    // operates on audioBuffer in place or returns new buffer
    // selection: { startSample, endSample } or null for full buffer
    return modifiedAudioBuffer;
  }
}
```

**Placeholder plugins (shipped with recorder.html, implemented later):**

- **Equalizer** — 3-band parametric EQ (low shelf, mid peak, high shelf). For rolling off low-frequency rumble from wind or removing harsh sibilance from voice recordings.
- **Compressor** — threshold, ratio, attack, release. For evening out dynamic range in dialogue recordings where the speaker moves relative to the mic.
- **De-esser** — frequency-targeted compressor. Detects sibilance (typically 4–8 kHz), applies gain reduction only to those frequencies. For voice-over tracks.
- **Noise gate** — threshold-based silence trimmer. For cleaning up dialogue recordings: silence between phrases becomes actual silence, not room tone at -40dB.

The plugin params render as sliders in the editor panel. The user adjusts, previews (non-destructive playback through the processing chain), and applies (destructive write to the buffer). Preview uses the Web Audio API's real-time processing nodes (`BiquadFilterNode`, `DynamicsCompressorNode`). Apply renders offline via `OfflineAudioContext` and writes the result back to the buffer.

Each plugin that ships with the file is a placeholder: the `process` function contains a `// TODO: implement` comment and returns the buffer unchanged. The interface, parameter UI, and preview wiring are all in place. The actual DSP is filled in later — or by anyone who forks the file.

### Provenance Metadata Format

Each audio file produced by the recorder carries a sidecar `.json` file with the same base name (or the metadata is embedded in the file's ID3/Vorbis tags when the format supports it). For the MVP, sidecar JSON is simpler and works with every format:

```json
{
  "version": 1,
  "type": "pr-audio",
  "audio_hash": "sha256:a3f9c2d1...",
  "recorder": {
    "pubkey": "base64...",
    "signature": "base64..."
  },
  "location": {
    "lat": 59.4370,
    "lng": 24.7453,
    "accuracy_m": 8
  },
  "recorded_at": "2026-04-02T14:30:00Z",
  "duration_s": 47.2,
  "format": "opus",
  "source": "live",
  "derived_from": null,
  "edit_history": [
    "trim 0.0-2.3s, 44.1-47.2s",
    "loop_fade 2.0s",
    "composite 12.4-12.6s"
  ],
  "tags": ["atmo", "rain", "old-town", "tallinn"]
}
```

The `edit_history` is append-only. Every destructive operation logs a human-readable description of what it did. The original `audio_hash` refers to the hash *after* the latest edit — the history documents the transformations, but only the final file is kept. If you need the original, you have the original. The recorder does not store every intermediate version.

The `tags` field is free-form and author-assigned. Tags are for discovery: a tour maker looking for rain ambience searches `["rain", "atmo"]` and finds every signed recording that matches. Tags are not enforced — they are suggestions. The audio is what it sounds like, not what the tag says.

### Derived Works

When a tour maker uses a clip from someone else's recording:

1. The clip's sidecar JSON is included in the `.pr` tour package alongside the audio file
2. The tour's `cartridge.py` can reference the original recorder's pubkey for attribution
3. Anyone inspecting the tour can trace any audio asset back to its recorder, location, and timestamp

This creates a web of attribution without a central database. The graph is implicit in the files themselves. If ten tours use the same rain recording from Tallinn Old Town, all ten carry the same `recorder.pubkey` in their sidecar JSONs. A tool that scans `.pr` packages can reconstruct the graph: which recorders contribute to which tours, which locations produce the most-used clips, which tour makers share audio sources.

There is no licensing system in the protocol. The recorder signs audio and publishes it. A tour maker uses it. The signature is attribution, not permission. If the community wants to build a licensing layer on top (Creative Commons, revenue share for audio contributors), it can — the provenance metadata is sufficient to support any licensing model. The protocol does not choose one. The gaps are load-bearing.

### Recorder UI (MVP)

A single HTML file, mobile-first. Three screens:

**Record screen** — large Record button (red circle, large tap target). GPS status indicator. Timer showing recording duration. Level meter showing input amplitude. Stop button appears while recording. On stop: preview playback, name the recording, confirm or discard.

**Library screen** — list of all local recordings with: name, duration, location (if tagged), date, waveform thumbnail. Tap to open in editor. Import button for external files. Export button to save a recording + its sidecar JSON as a zip.

**Editor screen** — full-width waveform display on `<canvas>`. Touch to select regions. Toolbar: Trim, Composite, Loop Fade. Plugin slots below the toolbar (collapsed by default, expand on tap). Each plugin shows its parameter sliders when expanded. Preview button (plays the current buffer through the processing chain without writing). Apply button (destructive write). Export button (saves the edited audio + updated sidecar JSON).

---

## What Not to Build Yet

No backend. No settlement implementation. No payment rails. No asset hosting. No analytics pipeline. No app store. The cartridge is a file. The player is a URL. The authoring tool is a file. Walker identity generates on first launch with zero network calls. Receipts accumulate locally. A tour author in Narva at 2am needs a text editor and a GPS coordinate. Settlement is phase two — but the receipt format and signing are designed now so everything built in phase one produces valid receipts from day one.

**Do not build more than the story needs. The gaps are load-bearing.**

---

## Walker Identity & Decentralised Settlement (2026-03-31)

### The Problem

If the platform controls identity, the platform controls payment. If the platform controls payment, no one else can run the system. The platform becomes a tollbooth, and tollbooths attract regulators, rent-seekers, and single points of failure. We want the opposite: a system where anyone can verify that a walker visited a checkpoint, and anyone can settle the resulting payment, and no single entity can shut it down or skim it.

### Identity System (`identity.html`)

Every participant — walker, tour maker, recorder — generates an Ed25519 keypair locally. The public key is the identity. The private key stays on the device (IndexedDB, exportable). No registration, no email, no server.

Each identity also has a **handle** — a human-readable screen name chosen by the user. The handle is cosmetic. It is **not unique**. No duplicate check, anywhere. Two people can pick the same handle. The public key is the real identity. The handle is for humans.

**Identity management flow:**

```
identity.html
  → User enters a handle ("kaspar", "ghost_narrator", "rain_collector")
  → Ed25519 keypair generated via crypto.subtle.generateKey
  → Private key stored in IndexedDB (never leaves device unless exported)
  → Public key = identity, stored in localStorage as base64
  → Export: downloads a .pr-identity.json file containing handle + JWK keypair
  → Import: uploads a .pr-identity.json, verifies key pair, restores identity
  → Delete: wipes keys from IndexedDB, clears localStorage
```

**Handle collisions on servers:** When two different pubkeys share the same handle on the same settlement provider or directory server, they are disambiguated by appending an index in arrival order: `kaspar[0]`, `kaspar[1]`. The server does not reject either. It does not ask either to change. The index is a display suffix, not part of the identity. The pubkey is the identity. The handle is a courtesy.

This means:
- Handle squatting is impossible — there is nothing to squat
- No one needs permission to pick a name
- The handle can change at any time without affecting the identity
- Two users with the same handle on different servers have no collision at all

**Cross-tool identity:** The identity is shared across all PR tools on the same origin (player, editor, recorder) via the same IndexedDB and localStorage. The recorder signs audio with the same key the walker uses for checkpoint receipts. The tour maker signs cartridges with the same key. One keypair, all roles. The role is determined by what you do with the key, not by the key itself.

**Multi-device:** Export the `.pr-identity.json` and import it on the other device. Or generate a second keypair and link them with a self-signed attestation: "pubkey A and pubkey B are the same person, signed by A, countersigned by B." Any settlement provider that sees both signatures treats them as one identity. No server needed.

### ESP32 Identity

Each ESP32 checkpoint device gets an Ed25519 keypair burned in at provisioning. The private key lives in flash. The public key is printed on a sticker, registered with the sponsor at installation, and published in the location registry (a static JSON file anyone can mirror).

The ESP32 has no network connection. It has no idea who the walker is, what tour they are on, or what the platform thinks about anything. It knows one thing: someone connected and requested a checkpoint token.

### The Double-Signed Receipt

When a walker hits an ESP32 checkpoint:

```
1. Walker's browser connects to ESP32 WiFi, hits 192.168.1.1/checkpoint
2. ESP32 responds with a challenge: { esp_id, nonce, timestamp }
3. Walker's browser signs: { esp_id, nonce, timestamp, walker_pubkey }
   → signed with walker's private key
4. Browser sends signed payload back to ESP32
5. ESP32 verifies walker signature, then counter-signs the whole thing:
   → { walker_signed_payload, esp_signature }
6. Browser receives the double-signed receipt. Stores it locally.
```

The receipt proves:
- **The walker was physically present** (they connected to the ESP32's WiFi, which has a range of ~30 metres)
- **The ESP32 confirmed it** (its signature is unforgeable without access to the physical device)
- **The timestamp is anchored** (the ESP32's monotonic clock, agreed by both parties)
- **Neither party can forge the other's half** (each signature requires the respective private key)

This is the atomic unit of the entire payment system. Everything else — escrow, settlement, analytics, revenue share — is accounting performed on a pile of these receipts.

For GPS-only and QR triggers (no ESP32 involved), the receipt is single-signed by the walker. This is weaker — the walker could fake their GPS position. But it is still useful for tour progression and analytics, just not for sponsor settlement. Sponsors who want payment-grade proof of presence deploy an ESP32. The hardware is the trust anchor, not the platform.

### Receipt Format

```json
{
  "version": 1,
  "type": "checkpoint",
  "tour_id": "tallinn-old-town-medieval",
  "event_id": "approach-town-hall",
  "waypoint_id": "black-dog-bar",
  "timestamp": "2026-03-31T15:42:00Z",
  "walker": {
    "pubkey": "base64...",
    "signature": "base64..."
  },
  "checkpoint": {
    "esp_id": "esp32-bd-001",
    "pubkey": "base64...",
    "nonce": "random16bytes",
    "signature": "base64..."
  }
}
```

Receipts are append-only. The walker accumulates them in localStorage. They can export them, share them, submit them to any settlement provider. The receipts are self-contained — anyone with the public keys can verify them without contacting any server.

### Decentralised Settlement

Because receipts are self-verifying, **anyone can run the settlement layer**. The platform does not hold escrow. The platform does not process payments. The platform produces cryptographic proof that payments should happen, and then gets out of the way.

#### How Settlement Works

A **settlement provider** is any entity that:
1. Holds sponsor escrow (money deposited by the sponsor)
2. Accepts receipts from walkers (or from anyone — receipts are public)
3. Verifies receipt signatures (walker + ESP32)
4. Debits sponsor escrow per verified receipt
5. Credits tour maker and platform according to the revenue split
6. Settles to the walker's chosen payment rail (if there's a walker reward component)

The settlement provider can be:
- **Stripe** — the platform runs a Stripe integration as one settlement option. Sponsors deposit via card. Receipts trigger payouts.
- **A local bank** — a bank in Estonia builds a settlement module. Sponsors have escrow accounts at that bank. Same receipts, different payment rail.
- **A cooperative** — a group of tour makers runs their own settlement node. They collect receipts, audit them, and settle amongst themselves.
- **The sponsor directly** — a bar owner who trusts the tour maker can skip the escrow entirely. The tour maker shows up with a USB stick of signed receipts. The bar owner runs `pr settle receipts/ --verify` and pays out. Two people and a laptop.

All of them verify the same receipts. All of them apply the same logic. The settlement code is open source. The receipts are the contract, not the platform's database.

#### Sponsor Setup

```
Sponsor registers at any settlement provider:
  → deposits escrow (e.g. €500)
  → sets per-walker rate (e.g. €0.50)
  → registers ESP32 public key(s) for their location(s)
  → sets budget cap and optional daily/weekly limits
  → done. No platform account needed.
```

The sponsor's contract is with the settlement provider, not with the platform. The platform never touches the money. If the platform disappears tomorrow, the sponsors still have their escrow at their bank, and the receipts are still valid.

#### Revenue Split

Encoded in the tour cartridge (the `cartridge.py` file), signed by the author:

```python
REVENUE_SPLIT = {
    "tour_maker": 0.70,    # 70% to the person who sold the sponsorship
    "platform": 0.20,      # 20% platform fee
    "settlement": 0.10,    # 10% to whoever runs the settlement node
}
```

The settlement provider reads this from the cartridge. The split is part of the signed payload — the author commits to it at publish time. A settlement provider who changes the split would be provably violating the signed contract.

#### The Bank Pitch

> "For €50K we open-source a settlement module that plugs into your core banking API. Any bank that deploys it becomes a settlement provider for every Pavement Radio tour in their market. You hold the escrow. You earn 10% of every checkpoint payment. The receipts verify themselves — your compliance team can audit the entire system with a Python script. No platform dependency. No API to maintain. The only moving part is money in, money out, and a sha256 check in between."

This is how the system scales without the platform scaling. Every local bank that deploys the settlement module becomes infrastructure. The platform stays small — it publishes cartridges and maintains the location registry. The money flows through institutions that are already regulated, already trusted, already have the sponsor's business account.

#### Why Not Blockchain

The receipts are signed, timestamped, and independently verifiable. That is everything a blockchain provides for this use case, without:
- Transaction fees
- Confirmation latency
- A token that needs to have a price
- Regulatory ambiguity about whether you're running a money service
- Explaining to a bar owner in Tallinn what a gas fee is

The trust model is simpler: the walker trusts their own device. The sponsor trusts their own ESP32. The settlement provider trusts Ed25519. Nobody needs to trust a consensus mechanism operated by strangers.

If someone wants to anchor receipt hashes to a blockchain for additional auditability, they can. It's an append-only log of hashes — any chain will do. But the system does not require it and does not default to it. The cryptography is sufficient.

---

## Tour Promotion Kit — Editor Built-In (2026-04-02)

### The Problem

Tour makers create something strange and beautiful and then have no idea how to tell anyone about it. Promotion is a separate skill, a separate tool, a separate mental mode. The gap between "I just finished this tour" and "someone is walking it" is where most tours die. If the tour maker has to open Canva, write copy from scratch, find a screenshot tool, resize for Instagram, and remember what hashtags work — they won't. The ones who do promote are the ones who were already good at marketing. The product should not select for marketers.

Self-promotion must be the path of least resistance. The moment the tour maker hits Save, the next thing the editor offers is not "done" — it is "tell people."

### Design Principle

The promotion flow is not a separate tool. It lives inside `editor.html`, directly after the save/export action. The editor already knows everything about the tour: the waypoints, the city, the route shape, the narrative skin, the audio track names. It uses that knowledge to pre-generate promotional materials that the tour maker only needs to approve and share. Zero blank-page anxiety.

### The Flow

```
Tour maker hits Save
  → .pr package downloads
  → Editor immediately opens the Promotion Panel (slide-up sheet, same pattern as waypoint editor)
  → Panel contains:
      1. A generated map card (static image of the route)
      2. Pre-written copy in three lengths (tweet, caption, paragraph)
      3. Photo upload slots (up to 4)
      4. One-tap share buttons for each platform
```

The panel is dismissible. It is not a gate. But it appears by default, every time, because the moment after saving is the moment of highest motivation. The tour maker just finished something — they want to show it off. The editor catches that impulse and gives it a channel.

### Map Card

The editor renders a static image of the tour route onto a map snapshot. This is the hero image for every social post. It is generated entirely client-side:

- The Leaflet map canvas is captured as a PNG via `HTMLCanvasElement.toDataURL()` (CartoDB tiles are canvas-rendered, so this works without CORS issues when using the canvas renderer)
- Waypoints are drawn as numbered circles on the route
- The tour title is overlaid at the top in a clean sans-serif font
- The city name (derived from reverse geocoding the centroid of the waypoints, or manually entered by the author) is overlaid below the title
- A subtle PR watermark/logo sits in the corner — small enough to be tasteful, persistent enough to be discoverable
- The card is sized for social media: 1200×630px (Open Graph / Twitter Card standard) and 1080×1080px (Instagram square). Both are generated. The tour maker picks which to use per platform.

The map card is the thing that makes someone stop scrolling. A route drawn on a dark city map with numbered waypoints looks like a conspiracy board or a treasure map. It is inherently shareable because it provokes curiosity: "what is this route and why does it have seven stops?"

### Pre-Written Copy

The editor generates three lengths of promotional copy from the tour metadata:

**Short (tweet-length, ~200 chars):**
Uses tour title, city, waypoint count, and narrative skin to generate a hook. Example:
> *"7 waypoints through Tallinn Old Town. A medieval ghost has something to tell you at the town hall. Free, GPS-guided, no app install. [link]"*

**Medium (Instagram caption, ~400 chars):**
Adds the first waypoint's name as a starting point, mentions the tour duration estimate (derived from waypoint distances), and includes a call to action.

**Long (paragraph for a blog post or event listing, ~800 chars):**
Full description including the narrative frame, what the walker will experience, and practical details (starting point, estimated walking time, what to bring — headphones).

All three are editable inline. The tour maker can rewrite any of them before sharing. The generated text is a starting point, not a mandate. The point is that the text field is never empty.

Copy generation is deterministic template expansion from tour metadata — no LLM call needed. The templates are baked into `editor.html`. They use the tour title, skin name, city, waypoint count, waypoint names, estimated distance, and estimated walking time. Simple string interpolation. If the tour metadata is good, the copy is good. If the metadata is sparse, the copy is sparse but still functional.

### Photo Slots

The map card alone is strong, but real photos of the locations convert better. The promotion panel has four photo upload slots:

- Tap to upload from camera roll or take a photo
- Photos are resized client-side to social media dimensions (1080px wide max)
- Photos are arranged in a carousel preview (for platforms that support multi-image posts)
- The first photo slot suggests: "Photo of the starting point" — the rest are free
- Photos are stored temporarily in memory — they are not part of the `.pr` package and not saved to IndexedDB. They exist only for the duration of the promotion flow. If the tour maker closes the panel and reopens it, the photos are gone. This is intentional: photos are ephemeral promotion material, not tour assets.

### Share Actions

Each share button composes a platform-specific post and opens the native share flow:

**Web Share API (primary path):**
If the browser supports `navigator.share()` (most mobile browsers do), the "Share" button triggers the native share sheet with:
- `title`: tour title
- `text`: the selected copy length (short by default)
- `url`: the tour's playable URL (tour link with the tour ID parameter)
- `files`: the map card image + any uploaded photos (if `navigator.canShare({files})` returns true)

This covers every platform the user has installed — Instagram, WhatsApp, Telegram, Twitter, Facebook, email — in one tap. The operating system handles the routing. The editor does not need to know which platforms exist.

**Fallback share buttons (desktop and browsers without Web Share API):**

- **Copy link** — copies the tour URL to clipboard. Toast confirmation.
- **Copy text + link** — copies the selected copy length + URL. For pasting into any text field.
- **Download images** — downloads the map card (and photos if uploaded) as a zip. For manual posting on desktop.
- **Twitter/X** — opens `https://twitter.com/intent/tweet?text=...&url=...` in a new tab with the short copy pre-filled.
- **WhatsApp** — opens `https://api.whatsapp.com/send?text=...` with copy + URL.
- **Telegram** — opens `https://t.me/share/url?url=...&text=...` with copy + URL.

Each button shows a platform icon and the platform name. The buttons are styled consistently with the editor's dark theme. They are not an afterthought bolted onto a settings page — they are prominent, colourful, and inviting.

### Repeat Promotion

The promotion panel is also accessible from a "Share" button in the editor toolbar — not just after save. A tour maker who wants to promote an existing tour opens the `.pr` file, hits Share, and the same panel appears with the same generated materials. This covers the case where the tour maker saved yesterday and wants to post today, or wants to create a fresh post for a different platform.

### What This Does Not Do

- **No account creation.** The tour maker does not log in to anything. Share actions use platform URLs and the Web Share API. The editor has no server-side component.
- **No analytics.** The editor does not track whether the share happened, which platform was used, or whether anyone clicked the link. Analytics are for the platform backend (phase 2). The editor is a tool, not a funnel.
- **No scheduling.** The tour maker shares now or never. If they want to schedule posts, they use their own tools. The editor catches the impulse; it does not manage a content calendar.
- **No AI copy generation.** The copy templates are deterministic string interpolation. Adding LLM-generated copy is possible later but is not MVP. The templates are good enough because the tour metadata is specific enough. "7 waypoints through Tallinn Old Town" is already more compelling than whatever a tour maker would write from scratch while staring at a blank text box.

### Why This Works

The tour maker's workflow becomes: author → save → share. Three steps, one tool, one session. The share step requires exactly zero creative decisions if the tour maker accepts the defaults — the map card is generated, the copy is generated, the link is generated. They tap Share and pick a platform. Done.

The people who will never open Canva will still share a map card that looks like a treasure map because it appeared in front of them at the right moment and all they had to do was tap. That is the entire design philosophy: **the promotion material generates itself from the creative work the tour maker already did.**

---

*Append decisions to this document as they are made. Do not edit retroactively — add dated sections at the bottom if earlier decisions are revised.*