# Playcolors.co — Home Assistant beta channel

Beta / test builds of Playcolors.co **Home Assistant add-ons and integrations**. This is the
pre-release channel: things here are newer, and may break. Every project's **stable** version lives
in its own public repository (see the table below) — this repo only ever holds betas.

One repository, two front doors: Home Assistant picks up the **add-ons** from the Add-on Store, HACS
picks up the **integration** from the same URL. Adding it in both places costs nothing and lets you
test the whole line-up from a single source.

## What's in beta right now

| Project | Kind | Install from | Stable channel |
|---|---|---|---|
| [`ebo/`](ebo/) | **Add-on** — EBO for Home Assistant: drive, see and hear your Enabot EBO robot (cloud family: Air 2, X, Max). Bundles and auto-installs its own `ebo` integration. | Add-on Store | [Playcolors-co/ha-enabot](https://github.com/Playcolors-co/ha-enabot) |
| [`custom_components/ebo_local/`](custom_components/ebo_local/) | **Integration** — EBO Local: talks to the EBO Air 2 on your LAN, no vendor cloud in the live path. Research in progress. | HACS | [Playcolors-co/ha-ebo-local](https://github.com/Playcolors-co/ha-ebo-local) |

Not every project betas here: a standalone integration may instead ship its betas as GitHub
pre-releases from its own repository. Currently that's
[BinHass](https://github.com/Playcolors-co/ha-binhass) (Waltham Forest bin collections) — add that
repo in HACS and turn on *Show beta versions* to follow its beta channel.

## Install the add-ons (Home Assistant Add-on Store)

**Settings → Add-ons → Add-on Store → ⋮ (top right) → Repositories**, then add:

```
https://github.com/Playcolors-co/ha-addons-beta
```

The beta builds appear in the store alongside the stable ones. A beta add-on and its stable twin
have different slugs, so you can **install both side by side** and compare.

## Install the integration (HACS)

**HACS → ⋮ (top right) → Custom repositories**, then add the same URL with category
**Integration**:

```
https://github.com/Playcolors-co/ha-addons-beta
```

Then download *EBO Local (unofficial, beta)* and restart Home Assistant.

> **Beta and stable cannot coexist.** Unlike add-ons, an integration is identified by its domain
> (`ebo_local`), so the beta installs over the stable one in `custom_components/`. Pick one channel
> per Home Assistant instance. To go back, remove it in HACS and re-download from
> [`ha-ebo-local`](https://github.com/Playcolors-co/ha-ebo-local).

## How this channel works

- **Everything here is a pre-release.** Expect rough edges; report anything odd on the relevant
  project's issue tracker (the stable repo linked above).
- **Stable lives elsewhere.** Once a beta is proven it is promoted to the project's own public repo.
- **Layout.** Add-ons are one top-level folder each (the folder holding `config.yaml`); the HACS
  integration lives in `custom_components/<domain>/`. The two mechanisms ignore each other:
  Supervisor only scans top-level folders with a `config.yaml`, HACS only downloads
  `custom_components/<domain>/`.
- **One HACS integration per repository** — that is a HACS limit, not a choice. See
  [PUBLISHING.md](PUBLISHING.md) for what happens when a second one arrives.

Maintainers: the promote-to-stable recipe and the per-project mapping live in
[PUBLISHING.md](PUBLISHING.md).

## Not affiliated

These are free, unofficial projects, not affiliated with or endorsed by the vendors of the devices
they work with.
