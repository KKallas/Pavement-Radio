# Pavement Radio

You are walking a city you thought you knew. You pass the same corner you've passed a hundred times, but today a voice from 1923 is waiting for you there. It tells you something happened here — something specific, something you can almost see if you half-close your eyes. You turn the corner. The voice changes. The street changes. You are still in your city, but the city is not still. It has been staging a performance for you, and you just walked into it.

## How It Works

**Walkers** open a URL on their phone and pick a tour. As they walk, their GPS position, a QR code scan, or a WiFi hotspot connection triggers audio — narration, ambient soundscapes, character dialogue, puzzle hints. No app install. No account. Just a browser and a pair of headphones and a city that suddenly has more layers than you expected.

**Tour makers** are local guides who author routes as narrative skins draped over real locations. A single street corner can exist in ten stories simultaneously: a medieval merchant's last trade, a Cold War dead drop, a ghost who won't shut up about the plumbing. The tour maker writes the skeleton. The walker's behaviour — their pace, their choices, their dwell time at checkpoints — writes the flesh. Two walkers on the same tour hear subtly different versions of the same scene. Tour makers are also the salespeople — they pitch local businesses, close sponsorship deals, and bring venues into their routes. This is their primary income. They know the city, they know the story, and they know which bar owner will say yes to having ghosts walk through the door.

**Sponsors** are local businesses — bars, cafes, bookshops — who pay per walker checkpoint hit. A tour maker walks in, explains the deal, and the venue sets a budget cap and a per-walker rate. Every tour that routes through their location earns them foot traffic. They sign once and appear in every narrative that passes through their door. They never need to know which century just walked in.

**The platform** holds it all together. It manages location infrastructure, escrow accounting, and audio delivery. Tour makers handle the relationships. The platform handles the plumbing. The city runs itself.

## Architecture

```
                          +-----------------+
                          |   Tour JSON     |
                          |  ("cartridge")  |
                          +--------+--------+
                                   |
                                   v
                          +-----------------+
                          |    Web App      |
                          | (single HTML)   |
                          +--------+--------+
                                   |
                    +--------------+--------------+
                    |              |              |
                    v              v              v
              +-----------+  +-----------+  +-----------+
              |    GPS    |  |  QR Code  |  |   WiFi    |
              |  Radius   |  |   Scan    |  |  Hotspot  |
              +-----------+  +-----------+  +-----------+
                    |              |              |
                    +--------------+--------------+
                                   |
                                   v
                          +-----------------+
                          | Audio Playback  |<--- LLM Pre-render
                          | (ambient +      |     Pipeline
                          |  narration +    |     (90-190s ahead)
                          |  dialogue)      |
                          +-----------------+
                                   |
                                   v
                          +-----------------+
                          |   Checkpoint    |
                          |     Event       |
                          +--------+--------+
                                   |
                                   v
                          +-----------------+
                          |   Escrow Log    |
                          | (sponsor debit) |
                          +-----------------+
```

## MVP

The first working demo does one thing well: a walker opens a URL and hears a city come alive as they walk through it.

- **One tour, hardcoded.** Tallinn Old Town, 4-5 waypoints.
- **GPS triggers only.** No QR, no WiFi, no ESP32.
- **No LLM.** Static audio assets, no personalisation pipeline.
- **No sponsor payments.** Checkpoint events log to console, nothing settles.
- **Single HTML file.** No framework, no build step. Loads a tour JSON from a URL parameter, tracks GPS position, triggers waypoints when the walker enters the radius. Audio playback stubbed with on-screen text display until real audio assets exist.

The point is to prove the loop: walk, trigger, hear, walk. Everything else is scaffolding on top of that.

---

*Pavement Radio: a city as a game board, narrated by ghosts, funded by bars.*
