# Playcolors.co — Home Assistant beta channel

Beta / test builds of Playcolors.co **Home Assistant add-ons and integrations**. This is the
pre-release channel: things here are newer, and may break. Each project's **stable** version lives in
its own repository (linked below).

## Add this repository to Home Assistant

**Settings → Add-ons → Add-on Store → ⋮ (top right) → Repositories**, then add:

```
https://github.com/Playcolors-co/ha-addons-beta
```

The beta builds will then appear in the store alongside the stable ones. You can install a stable
project and its beta side by side to test.

## What's in beta right now

| Project | What it is | Stable channel |
|---|---|---|
| [`ebo/`](ebo/) | **EBO for Home Assistant** — drive, see and hear your Enabot EBO robot from Home Assistant | [Playcolors-co/ha-enabot](https://github.com/Playcolors-co/ha-enabot) |

More add-ons and integrations will show up here as they enter beta.

## How this channel works

- **Everything here is a pre-release.** Expect rough edges; report anything odd on the relevant
  project's issue tracker.
- **Stable lives elsewhere.** Once a beta is proven, it's promoted to the project's own stable repo
  (the "Stable channel" column above). This repo only ever holds beta builds.
- **One folder per project.** Each subfolder is a self-contained add-on or integration with its own
  README, version and changelog.

## Not affiliated

These are free, unofficial projects, not affiliated with or endorsed by the vendors of the devices
they work with.
