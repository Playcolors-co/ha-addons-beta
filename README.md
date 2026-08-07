# Playcolors.co — Home Assistant beta channel

> ⚠️ **This repository is being retired.** Every project now carries its own beta channel inside its
> own public repository, so there is nothing left for a separate beta repo to do. See
> [what replaces it](#what-replaces-this-repo). It stays up, unchanged, until the new channels are
> confirmed working.

Beta / test builds of Playcolors.co Home Assistant add-ons.

## What's still here

| Project | Kind | Stable channel |
|---|---|---|
| [`ebo/`](ebo/) | **Add-on** — EBO for Home Assistant: drive, see and hear your Enabot EBO robot (cloud family: Air 2, X, Max) | [Playcolors-co/ha-enabot](https://github.com/Playcolors-co/ha-enabot) |

Add it in **Settings → Add-ons → Add-on Store → ⋮ → Repositories**:

```
https://github.com/Playcolors-co/ha-addons-beta
```

## What replaces this repo

Both Home Assistant front doors can serve a beta channel from a project's own repository — no second
repository needed on either side.

**Add-ons** — Supervisor accepts a `#<branch>` suffix on a repository URL and identifies a repository
by the hash of the *whole* string, so a branch-pinned URL is a separate repository whose add-on
installs alongside the stable one:

```
https://github.com/Playcolors-co/ha-enabot#beta
```

**Integrations** — HACS offers, per repository, the stable releases, plus pre-releases to anyone who
turns on *Show beta versions*, plus the default branch from the version picker:

| Project | Repository | Beta |
|---|---|---|
| Enabot Local | [`ha-ebo-local`](https://github.com/Playcolors-co/ha-ebo-local) | pre-releases (`v0.1.0b1`) |
| BinHass | [`ha-binhass`](https://github.com/Playcolors-co/ha-binhass) | pre-releases |

The `ebo_local` integration that briefly lived here has moved to its own repository and was renamed
to the domain **`enabot_local`**. If you downloaded it here through HACS, remove it and download it
again from [`ha-ebo-local`](https://github.com/Playcolors-co/ha-ebo-local).

## Not affiliated

These are free, unofficial projects, not affiliated with or endorsed by the vendors of the devices
they work with.
