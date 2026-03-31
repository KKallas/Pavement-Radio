# Pavement Radio

You are walking a city you thought you knew. You pass the same corner you've passed a hundred times, but today a voice from 1923 is waiting for you there. It tells you something happened here — something specific, something you can almost see if you half-close your eyes. You turn the corner. The voice changes. The street changes. You are still in your city, but the city is not still. It has been staging a performance for you, and you just walked into it.

## How It Works

**Walkers** open a URL on their phone and pick a tour. As they walk, their GPS position, a QR code scan, or a WiFi hotspot connection triggers audio — narration, ambient soundscapes, character dialogue, puzzle hints. No app install. No account. Just a browser and a pair of headphones and a city that suddenly has more layers than you expected.

**Tour makers** are local guides who author routes as narrative skins draped over real locations. A single street corner can exist in ten stories simultaneously: a medieval merchant's last trade, a Cold War dead drop, a ghost who won't shut up about the plumbing. The tour maker writes the skeleton. The walker's behaviour — their pace, their choices, their dwell time at checkpoints — writes the flesh. Two walkers on the same tour hear subtly different versions of the same scene. Tour makers are also the salespeople — they pitch local businesses, close sponsorship deals, and bring venues into their routes. This is their primary income. They know the city, they know the story, and they know which bar owner will say yes to having ghosts walk through the door.

**Sponsors** are local businesses — bars, cafes, bookshops — who pay per walker checkpoint hit. A tour maker walks in, explains the deal, and the venue sets a budget cap and a per-walker rate. Every tour that routes through their location earns them foot traffic. They sign once and appear in every narrative that passes through their door. They never need to know which century just walked in.

**The platform** publishes tours and maintains a location registry. It does not hold money. It does not control identity. It produces cryptographic proof that things happened, and then gets out of the way. Tour makers handle the relationships. Settlement providers handle the money. The protocol handles the trust.

## The Financial Protocol

This section describes how money moves through the system. It is designed so that anyone reading this can build a compatible implementation from scratch. There is no proprietary component. The cryptography is the protocol.

### Identity

Every participant generates an Ed25519 keypair locally. The public key is their identity. No registration. No server. No email. Works offline. Works on an airplane. Works in a city that has no internet and one bar.

- **Walker**: keypair generated in the browser on first launch. Stored in IndexedDB. The walker never registers anywhere.
- **Tour maker**: keypair generated with the CLI. Public key submitted to the location registry when they choose to publish.
- **ESP32 checkpoint**: keypair burned in at manufacture. Public key printed on a sticker and listed in the location registry.
- **Sponsor**: no keypair needed. The sponsor deposits money with a settlement provider and registers which ESP32 public keys belong to their location. The sponsor's relationship is with the settlement provider (their bank, Stripe, a cooperative), not with the platform.

You are your public key. Lose your private key, lose your identity. That is the tradeoff for no central authority. It is the same tradeoff Bitcoin makes and it is made for the same reason.

### The Receipt

When a walker hits a checkpoint, a **double-signed receipt** is created. This is the atomic unit of the entire financial system.

```
Walker's phone connects to ESP32 WiFi (~30m range)
  → ESP32 sends: { esp_id, nonce, timestamp }
  → Walker signs: { esp_id, nonce, timestamp, walker_pubkey }
  → ESP32 verifies walker's signature, then counter-signs everything
  → Walker receives the double-signed receipt
  → Both parties store their copy
```

The receipt proves two things:
1. The walker was physically present (they connected to a device with 30-metre range)
2. The ESP32 confirmed it (its signature is unforgeable without the physical device)

Neither party can forge the other's half. The receipt is valid without any server. It is valid without the internet. It is valid in ten years. Anyone with the public keys can verify it. The receipt is a fact, not a claim.

For GPS-only triggers (no ESP32), the receipt is single-signed by the walker. This is weaker — the walker could fake their GPS. Single-signed receipts are useful for tour progression and analytics but are not sufficient for sponsor settlement. Physical presence requires physical proof. That proof is a ten-euro microcontroller.

### Settlement

Because receipts verify themselves, **anyone can settle them**. The platform does not hold escrow. The platform does not process payments. The platform does not need to exist for a settlement to happen.

A settlement provider is any entity that:

1. Holds sponsor escrow (money the sponsor deposited)
2. Accepts receipts (from walkers, tour makers, or anyone — receipts are public data)
3. Verifies both signatures on each receipt
4. Debits the sponsor's escrow per verified receipt
5. Credits the tour maker according to the revenue split signed into the tour cartridge
6. Keeps their own ledger of which receipts they have processed

That last point is important. **Each settlement provider maintains their own ledger.** There is no central ledger. There is no shared database. A receipt is a cryptographic fact. Whether it has been settled is a business fact that lives in the settlement provider's books. Two different settlement providers can process the same receipt independently — double-settlement is prevented by the sponsor having a single escrow with a single provider, not by the protocol.

This means:

- **Stripe** can be a settlement provider. Sponsors deposit via card, receipts trigger Stripe payouts.
- **A local bank** can be a settlement provider. Sponsors have escrow accounts at that bank. Same receipts, same verification, different payment rail.
- **A cooperative of tour makers** can settle amongst themselves. They collect receipts, audit them, and pay out.
- **Two people and a laptop** can settle. The tour maker shows up at the bar with a USB stick. The bar owner runs `pr settle receipts/ --verify` and pays cash. The cryptography works the same at every scale.

The revenue split is encoded in the tour cartridge and signed by the tour maker at publish time:

```python
REVENUE_SPLIT = {
    "tour_maker": 0.70,
    "platform":   0.20,
    "settlement": 0.10,
}
```

A settlement provider who alters the split would be provably violating the signed cartridge. The tour maker's signature is the contract. The settlement provider is the executor. These roles do not overlap.

### Validation

Anyone can validate any receipt at any time. The verification requires:
- The receipt itself (a JSON object with two signatures)
- The walker's public key (embedded in the receipt)
- The ESP32's public key (published in the location registry, also embeddable in receipts)

That is it. No API call. No authentication. No permission. The verification is a pure function: bytes in, boolean out. The code is open source. If you do not trust our implementation, write your own. Ed25519 is Ed25519.

A settlement provider who processes receipts is responsible for:
- Keeping their own ledger of processed receipt hashes (to avoid processing the same receipt twice)
- Verifying signatures before crediting or debiting
- Publishing their ledger (or a hash of it) so the tour maker and sponsor can audit

The settlement provider's ledger is their responsibility. Not the platform's. Not the walker's. The receipts are the shared truth. The ledger is the provider's accounting of that truth. If a provider's ledger does not match the receipts, the receipts win.

### Why This Is Not a Blockchain

The receipts are signed, timestamped, and independently verifiable. That is everything a blockchain provides for this use case, without:

- Transaction fees
- Confirmation latency
- A token that needs a price
- Regulatory ambiguity about running a money service
- Miners, validators, or consensus mechanisms operated by strangers
- Explaining gas fees to a bar owner in Tallinn

If someone wants to anchor receipt hashes to a blockchain for additional auditability, they can. The receipts are just data. But the system does not require it and does not default to it. Ed25519 is sufficient. We do not add complexity to signal sophistication.

## Bootstrap

Building this system requires money. Here is an honest accounting of what that money is for, where it should come from, and what happens to the people who provide it.

### What It Costs

Phase 1 (the protocol and MVP): two people, six months, minimal infrastructure. The tour cartridge format, the browser player, the CLI tools, the ESP32 firmware, one working tour in one city. Cost: salaries and rent. Call it €60–100K depending on geography.

Phase 2 (the settlement module and first bank integration): one banking API integration, compliance review, the open-source settlement node. Cost: €40–60K in engineering, €10–20K in legal and compliance.

Phase 3 (the authoring tool and tour maker onboarding): the map-based editor, documentation, the first ten tour makers in the first three cities. Cost: €30–50K plus travel.

Total bootstrap budget: roughly €150–200K to reach a self-sustaining system with real tours, real sponsors, and real settlement.

### Where the Money Comes From

**Option 1: Grants.** This is a cultural infrastructure project as much as a technology project. EU cultural innovation funds, city tourism development grants, creative industry grants exist for exactly this kind of work. The pitch: "an open protocol that turns any city into a stage, funded by local businesses, with no platform lock-in." Grant money does not take equity. It does not want a return. It wants outcomes. Our outcome is cities with more foot traffic in local businesses and an open protocol anyone can build on.

**Option 2: Pre-sold settlement licenses.** Go to a bank. Explain that for €50K you will build and open-source a settlement module that plugs into their core banking API. Every tour in their market settles through them. They hold the escrow. They earn 10% of every checkpoint payment. Their compliance team audits the system with a Python script. The bank's €50K buys them first-mover advantage in their market, not equity in the platform. This is a service contract, not an investment.

**Option 3: Pre-sold tours.** A tour maker in Tallinn authors a tour before the platform launches. The tour maker pre-sells sponsorships to five bars at €200 each. That is €1000 per tour, enough to cover the tour maker's time and contribute to platform development. Ten tour makers across three cities, five sponsors each: €50K in pre-revenue that proves the model before anything is "launched."

**Option 4: Personal runway.** The founders fund it themselves for as long as they can, building the MVP in the evenings while employed, the way most things that last were built. This is slow. It is also the only option that comes with zero strings.

### What We Do Not Take

We do not take venture capital. Not because venture capital is evil but because the incentive structure is incompatible with the design.

VC money wants a return. A return requires either an exit (acquisition) or a monopoly (platform lock-in). An exit means selling the platform to someone who will extract rent from it. A monopoly means closing the protocol so competitors cannot interoperate. Both of these destroy the thing that makes the system work: the fact that anyone can run a settlement node, anyone can validate a receipt, and no single entity controls the money flow.

If the platform takes VC money, the VCs will eventually ask why the settlement layer is open source instead of proprietary. They will ask why any bank can settle instead of only "our" payment system. They will ask why the protocol does not have a token. These are rational questions from their perspective. They are also the precise list of decisions that would kill the system.

The system is designed to be unkillable. That means it cannot have an owner who is incentivised to kill it.

### Exits

Honest accounting of how people who put money into this get it back:

**Grant funders** do not expect financial return. They expect a report, a working system, and cultural impact metrics (foot traffic in participating venues, number of tours authored, cities active). We provide these because they are also the metrics we care about.

**Banks** earn ongoing revenue from settlement fees. Their €50K buys a perpetual 10% of every checkpoint payment settled through their system, in their market. The return is proportional to adoption in their geography. If the system works, it pays for itself within a year of the first tour going live in their market. If it does not work, they lost €50K and gained an interesting technology exploration project they can write about in their innovation report.

**Tour makers** earn from day one. Their income is the sponsor payments minus the settlement provider's cut. The platform's 20% revenue share is the only ongoing cost, and it is capped in the signed cartridge — the platform cannot raise it without the tour maker re-signing. If the platform tries to raise fees, the tour maker forks the code, runs their own settlement, and keeps 90% instead of 70%. The platform's pricing is disciplined by the credible threat of exit.

**The founders** earn from the platform's 20% revenue share, which kicks in when real tours with real sponsors are generating real receipts. This is slow money. There is no liquidity event. There is no acquisition premium. There is a system that generates a modest, ongoing percentage of a growing number of small transactions across a growing number of cities. If the founders want to get rich, this is the wrong project. If the founders want to build something that outlasts them, this is the right structure.

### Self-Perpetuation

The system is designed so that the platform's disappearance does not stop the system from functioning.

If the platform goes offline tomorrow:
- Every published tour cartridge still works (it is a signed file on the walker's device)
- Every ESP32 still issues receipts (it has no network dependency)
- Every settlement provider still settles (they verify receipts against public keys, not against a platform API)
- Every walker still walks (the player is a single HTML file, cached in their browser)

The only thing that stops working is the tour directory (where new walkers discover tours) and the location registry (where ESP32 public keys are published). Both are static JSON files that can be mirrored by anyone. The platform's going-concern value is in curation, not in control.

This is the design constraint: build the thing so it works without you. If you succeed, you are useful but not necessary. If you are useful but not necessary, you must earn your place every day. That is a healthier incentive than a moat.

Anyone who reads this document can build a compatible system. The tour format is open. The receipt format is open. The verification is a pure function. The settlement protocol is open. If five competing platforms emerge, they all speak the same receipt language. A bar owner's ESP32 works with all of them. A walker's receipts settle with any of them. Competition happens at the layer of curation, authoring tools, and settlement convenience — not at the layer of the protocol.

This is what it means to build infrastructure instead of a product. The product is what tour makers build on top. The infrastructure is what we build underneath. Infrastructure should be boring, reliable, and impossible to monopolise. Like a pavement.

## Architecture

```
Walker's phone                          ESP32 checkpoint
┌──────────────┐                        ┌──────────────┐
│  Browser     │◄──── WiFi (~30m) ────►│  Ed25519 key │
│  Ed25519 key │                        │  HTTP server │
│  Tour player │                        │  Duty cycle  │
└──────┬───────┘                        └──────────────┘
       │
       │ double-signed receipt
       │
       ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Settlement  │     │  Settlement  │     │  Settlement  │
│  Provider A  │     │  Provider B  │     │  Provider C  │
│  (Stripe)    │     │  (local bank)│     │  (co-op)     │
│              │     │              │     │              │
│  own ledger  │     │  own ledger  │     │  own ledger  │
└──────────────┘     └──────────────┘     └──────────────┘
       │                    │                    │
       ▼                    ▼                    ▼
   Sponsor A            Sponsor B            Sponsor C
   escrow               escrow               escrow
```

```
Tour cartridge flow:

  cartridge.py ──── signed by tour maker's Ed25519 key
       │
       ├── MANIFEST_HASH ──── verifies manifest.json
       │                            │
       │                            └── sha256 of every asset file
       │
       ├── TOUR, WAYPOINTS, EVENTS ──── tour definition
       │
       └── REVENUE_SPLIT ──── signed revenue contract
```

## MVP

The first working demo does one thing well: a walker opens a URL and hears a city come alive as they walk through it.

- **One tour, hardcoded.** Tallinn Old Town, 4-5 waypoints.
- **GPS triggers only.** No QR, no WiFi, no ESP32.
- **No LLM.** Static audio assets, no personalisation pipeline.
- **No settlement.** Receipts log to console. Nobody gets paid yet.
- **Single HTML file.** No framework, no build step. Loads a tour cartridge from a URL parameter, tracks GPS position, triggers waypoints when the walker enters the radius.

The point is to prove the loop: walk, trigger, hear, walk. Everything else is scaffolding on top of that.

---

*Pavement Radio: a city as a game board, narrated by ghosts, funded by bars.*

*This document is a protocol specification. If you can read it, you can build it. That is the point.*
