# Pavement Radio — Design Addendum
## Session Decisions & Locked Vocabulary

*This document extends the main Claude.md briefing with design decisions locked in the second design session. When these conflict with the original Claude.md, this document wins.*

---

## Locked Vocabulary

These words mean specific things. Use them consistently or the system becomes ambiguous.

**Waypoint** — a physical trigger point in space. Exactly one trigger type: GPS coordinate with a radius, QR code ID, or ESP32 ID. One waypoint, one trigger. No combinations at the waypoint level — complexity lives in the event.

**Event** — the unit of story authoring. A directed arc from one waypoint to another. The walker is always inside exactly one event. Events are linear: a start waypoint, an end waypoint, a composition, a pre-render script. This is what the author writes.

**Session** — the accumulated state of one walker's run through a tour. Contains two things: a **tag accumulator** (unordered set of string tags) and a **path log** (append-only ordered array of visited waypoint IDs). Lives in localStorage. The pre-render pipeline reads this.

**Tag** — a string emitted by a waypoint on visit, or by a puzzle resolution, or by dwell time thresholds. Tags are the session's memory. Branch logic reads tags. Pre-render scripts read tags. Tags do not expire.

**Path log** — the ordered visit history. The last two entries are the direction vector: where the walker came from determines where to push them next. The full log enables retroactive narrative — a late event can reference what the walker saw first.

**Composition** — the audio content of one event. Always four tracks (see below). This is what plays between two waypoints.

**Pre-render** — a Python script that runs when the walker is one event away from a waypoint, using session state to personalise the composition audio before arrival. Produces warm files. Never runs live.

**Prefetch radius** — 100 metres. When any waypoint comes within this radius, its event's pre-render fires speculatively. All plausible next events warm simultaneously. The walker never waits.

**Cartridge** — the complete tour definition file. A plain Python file (`cartridge.py`). Human-readable and hand-editable. The authoring tool exports this. The player loads and executes this inside a sandbox. Authors can write it directly in any text editor — the GUI is a convenience, not a requirement. Running `python cartridge.py` directly self-verifies the package. An unsigned cartridge does not run, anywhere, ever.

---

## Session State Model

```
session: {
  tour_id: string,
  skin: string,                      // which narrative skin is active
  tags: Set<string>,                 // unordered, append-only
  path: [waypoint_id, ...],          // ordered visit history
  current_event: event_id | null,
  warm_events: [event_id, ...]       // pre-rendered, ready to play
}
```

Branch decisions read `tags` for who this walker is and `path[-2:]` for which direction they came from. That pair is sufficient for all routing logic.

---

## The Four-Track Audio Model

Every composition has exactly four tracks. They mix independently. When events overlap at a waypoint — because the walker moved fast, or doubled back — tracks mix per-channel, not per-event. This is also the localisation boundary: swap the VO track for a different language, everything else stays identical.

**ATMO** — continuous ambient soundscape. Fades slowly. When a new event starts, its ATMO crossfades into the previous event's ATMO (or the global tour atmo if no previous event). Never cuts hard. The city always sounds like somewhere.

**SFX** — all foley and point effects. Footsteps on cobblestones, a door, a bell, a gunshot in 1923. Fires on cue, does not loop. Can stack — multiple SFX fire independently.

**DIALOGUE** — in-story character voices. The barman. The ghost. The Soviet officer. These are authored voices, pre-recorded or TTS-rendered per skin. They are characters inside the fiction.

**VO** — the narrator voice. Outside the fiction, addressing the walker directly. The Terry Pratchett footnote voice. This is the track most likely to be personalised by the pre-render script, because it knows the walker's session state and speaks to them specifically.

Track mixing rules for overlapping events:
- ATMO: crossfade, longer event wins
- SFX: both play, user hears layered foley
- DIALOGUE: queue, do not overlap — finish current line before next
- VO: queue, do not overlap — VO is never interrupted

---

## Cartridge Schema (working draft)

```yaml
tour:
  id: string
  title: string
  skin: string                       # narrative frame label
  global_atmo: audio_asset_ref       # plays under everything, always

waypoints:
  - id: string
    trigger:
      type: gps | qr | esp
      coords: [lat, lng]             # if gps
      radius_m: number               # if gps, default 20m
      qr_id: string                  # if qr
      esp_id: string                 # if esp
      esp_hack_level: number         # if esp, 0 = normal connect, 1+ = bypass tricks
    emits: [tag, ...]                # tags written to session on visit

events:
  - id: string
    from_waypoint: waypoint_id
    to_waypoint: waypoint_id
    requires: [tag, ...]             # session must contain all these to play full composition
    fallback_event: event_id | null  # plays instead if requires not met

    composition:
      atmo:
        asset: audio_asset_ref
        fade_in_s: number
        fade_out_s: number
      sfx:
        - asset: audio_asset_ref
          cue_s: number              # seconds from event start
      dialogue:
        - asset: audio_asset_ref
          cue_s: number
          character: string
      vo:
        asset: audio_asset_ref | null         # static fallback
        prompt_template: string | null        # if pre-render is used
        prompt_variables: [session_field, ...] # what session fields to inject

    prerender:
      script: path_to_python         # runs at prefetch time
      human_description: string      # plain language statement of what this script does
                                     # SOURCE OF TRUTH — script is a compiled artifact
      output_track: vo | dialogue    # which track receives the rendered file
```

The `human_description` field on the pre-render script is mandatory and is the source of truth. If the script and the description diverge, the description wins and the script gets regenerated. This is the debugging interface, not the code.

---

## Authoring Tool — MVP UIX

A single HTML file. No framework. Leaflet.js for the map (OpenStreetMap tiles, free). The tool exports a cartridge YAML file. localStorage autosaves continuously.

**Three zones:**

**Map canvas (main area)** — real map of the city. Click to place a waypoint node. Click two waypoints to draw a directed event arc between them. Node color: gray (no composition), yellow (composition authored), green (pre-render script attached). Arc color follows destination node. The whole story's shape is visible at a glance.

**Event panel (right sidebar, opens on arc click)** — everything about one event. Top: trigger config for destination waypoint (type selector, radius, IDs). Middle: four-track composition stack — one row per track (ATMO, SFX, DIALOGUE, VO), each row has a human description field, an asset filename slot, and relevant timing controls. Bottom: requires tags (multi-select from tag rail), emits tags (text input), pre-render human description field, output track selector.

**Tag rail (bottom strip)** — every tag used anywhere in the cartridge, auto-populated as authors type into requires/emits fields. Click a tag to highlight every event and waypoint that touches it. Audit your narrative logic without reading YAML.

**Export button (top right)** — dumps cartridge YAML. That's it.

The map is not decorative. The map is the editor. Geography and narrative are the same axis.

---

## Pre-Render Pipeline Logic

```
walker position updates every 3 seconds
↓
calculate distance to all waypoints
↓
any waypoint within 100m?
  → fire pre-render script for that waypoint's incoming event(s)
  → pass: session.tags, session.path, event.prompt_template
  → script writes rendered audio to warm_events cache
  → timeout: if script fails after 30s, mark fallback
↓
walker hits waypoint trigger radius (default 20m)
  → play warm composition if available
  → play static fallback if not
  → append waypoint_id to session.path
  → union event.emits into session.tags
  → close current event, open next
```

Pre-render scripts are sandboxed: they receive a session JSON on stdin, write one audio file to a designated output path, and exit. No network access except to TTS APIs. No filesystem access outside their sandbox directory. A malicious tour author cannot reach anything outside their own event's pre-render output.

---

## Branch Logic

The system does not enforce a linear sequence. The walker's path emerges from tag prerequisites and the prefetch radius preparing all nearby options simultaneously.

A waypoint visited without its required tags plays a partial composition — atmosphere only, a hint that something is missing. The walker feels the gap. When they have accumulated the right tags and return, the full composition unlocks. The city teaches sequence through withholding, not through walls.

The push after a waypoint fires reads:
```
current_waypoint_id + path[-1] + dominant_tags → recommended next event
```

The author writes this routing table explicitly for dramatic branches that matter. Everything else falls back to tag-weight scoring: the event whose `requires` tags most overlap with the current session tags wins.

---

## Localisation Model

The four-track architecture is the localisation boundary. A tour in Estonian is the same cartridge with the DIALOGUE and VO tracks swapped for Estonian-language assets. ATMO and SFX are universal — cobblestones sound the same in every language.

The cartridge schema supports a `locales` block per composition that maps locale codes to alternative asset refs for DIALOGUE and VO tracks. The player selects locale at tour start (or inherits from browser preference) and loads the appropriate track assets. One cartridge, multiple languages, no structural changes.

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
    "global_atmo": "atmo/old-town-rain.opus",
}

WAYPOINTS = [
    {
        "id": "town-hall",
        "trigger": {"type": "gps", "coords": [59.4370, 24.7453], "radius_m": 20},
        "emits": ["visited_town_hall"],
    },
    # ...
]

EVENTS = [
    {
        "id": "approach-town-hall",
        "from_waypoint": "viru-gate",
        "to_waypoint": "town-hall",
        "requires": [],
        "composition": {
            "atmo": {"asset": "atmo/old-town-rain.opus", "fade_in_s": 3, "fade_out_s": 5},
            "sfx": [{"asset": "sfx/cobblestone-steps.opus", "cue_s": 0}],
            "dialogue": [{"asset": "dialogue/ghost-monologue.opus", "cue_s": 5, "character": "ghost"}],
            "vo": {"asset": "vo/intro-narration.opus"},
        },
    },
    # ...
]

# --- self-verification (runs when you execute this file directly) ---
if __name__ == "__main__":
    import hashlib, base64, json, os, sys, zipfile

    def verify():
        # find the .zip this cartridge lives in (or the directory around it)
        cart_dir = os.path.dirname(os.path.abspath(__file__))
        manifest_path = os.path.join(cart_dir, "manifest.json")

        if not os.path.exists(manifest_path):
            print("No manifest.json found — cannot verify assets.")
            return False

        # check manifest hash
        manifest_bytes = open(manifest_path, "rb").read()
        manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
        if manifest_hash != MANIFEST_HASH:
            print("FAIL: manifest.json has been modified since signing.")
            return False

        # check every file listed in manifest
        manifest = json.loads(manifest_bytes)
        for filepath, entry in manifest["files"].items():
            full_path = os.path.join(cart_dir, filepath)
            if not os.path.exists(full_path):
                print(f"FAIL: missing file {filepath}")
                return False
            file_bytes = open(full_path, "rb").read()
            if len(file_bytes) != entry["size"]:
                print(f"FAIL: size mismatch for {filepath}")
                return False
            if hashlib.sha256(file_bytes).hexdigest() != entry["sha256"]:
                print(f"FAIL: checksum mismatch for {filepath}")
                return False

        # check for undeclared files
        declared = set(manifest["files"].keys()) | {"manifest.json"}
        for root, dirs, files in os.walk(cart_dir):
            for f in files:
                rel = os.path.relpath(os.path.join(root, f), cart_dir)
                if rel not in declared:
                    print(f"FAIL: undeclared file {rel}")
                    return False

        print(f"OK: all {len(manifest['files'])} files verified.")
        print(f"    author: {AUTHOR}")
        print(f"    signed: {SIGNED_AT}")
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
│   ├── old-town-rain.opus
│   ├── harbour-wind.opus
│   └── tavern-interior.opus
│
├── sfx/
│   ├── door-creak.opus
│   ├── church-bell.opus
│   └── cobblestone-steps.opus
│
├── dialogue/
│   ├── barman-greeting.opus
│   ├── ghost-monologue.opus
│   └── officer-interrogation.opus
│
├── vo/
│   ├── intro-narration.opus
│   ├── waypoint-3-fallback.opus     # static VO fallback if pre-render fails
│   └── finale.opus
│
└── locale/
    └── et/                          # Estonian localisation
        ├── dialogue/
        │   ├── barman-greeting.opus
        │   └── ghost-monologue.opus
        └── vo/
            ├── intro-narration.opus
            └── finale.opus
```

The four top-level asset directories mirror the four-track audio model: `atmo/`, `sfx/`, `dialogue/`, `vo/`. The `locale/` directory holds per-language overrides for DIALOGUE and VO only — ATMO and SFX are universal.

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

1. The cartridge schema validator — a Python script that reads a YAML cartridge and reports errors. This defines the format precisely before anything else depends on it.

2. The single-file HTML player — loads a cartridge from a URL parameter, watches GPS position, fires waypoint triggers, logs events to console. Audio stubbed as text display. No pre-render, no branching. One hardcoded Tallinn Old Town tour with 4 waypoints, GPS triggers only.

3. The authoring tool HTML — map canvas, event panel, tag rail, YAML export. No asset upload in MVP — asset fields are just filename strings the author manages manually.

4. The pre-render sandbox — a Python script runner that accepts session JSON on stdin, executes a tour-supplied script in isolation, and writes one audio file out.

The player and the authoring tool are both single HTML files. They share nothing at runtime. The cartridge YAML is the only contract between them.

---

## What Not to Build Yet

No backend. No settlement implementation. No payment rails. No asset hosting. No analytics pipeline. No app store. The cartridge is a file. The player is a URL. The authoring tool is a file. Walker identity generates on first launch with zero network calls. Receipts accumulate locally. A tour author in Narva at 2am needs a text editor and a GPS coordinate. Settlement is phase two — but the receipt format and signing are designed now so everything built in phase one produces valid receipts from day one.

**Do not build more than the story needs. The gaps are load-bearing.**

---

## Walker Identity & Decentralised Settlement (2026-03-31)

### The Problem

If the platform controls identity, the platform controls payment. If the platform controls payment, no one else can run the system. The platform becomes a tollbooth, and tollbooths attract regulators, rent-seekers, and single points of failure. We want the opposite: a system where anyone can verify that a walker visited a checkpoint, and anyone can settle the resulting payment, and no single entity can shut it down or skim it.

### Walker Identity

The walker generates an Ed25519 keypair on first launch. The private key stays on their device (IndexedDB, never exported). The public key is their identity — a 32-byte string, no registration, no email, no server involved.

The walker's public key is their **wallet address** in the same way a Bitcoin address is a public key hash. Except there is no blockchain, no token, no gas fee. Just a keypair and a signature.

```
First launch:
  → crypto.subtle.generateKey("Ed25519")
  → store private key in IndexedDB
  → public key = walker ID
  → done. No network call. No registration. Works in airplane mode.
```

The walker can back up their keypair (export to file, QR code, passkey sync) or generate a new one. Losing the private key means losing the identity — and the accumulated walk history attached to it. That's the tradeoff for no central authority.

Multiple devices: the walker exports their private key and imports it on the other device. Or they generate a second keypair and link them with a self-signed attestation: "pubkey A and pubkey B are the same walker, signed by A, countersigned by B." Any settlement provider that sees both signatures treats them as one identity. No server needed.

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

*Append decisions to this document as they are made. Do not edit retroactively — add dated sections at the bottom if earlier decisions are revised.*