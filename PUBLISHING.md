# Publishing — channels and repositories

Maintainer notes. **This repository is being retired**: each project now has its beta channel inside
its own public repository. What follows is the model that replaces it, and what is left here.

## Component map

| Component | Kind | Repository | Beta channel |
|---|---|---|---|
| EBO for Home Assistant | Add-on (slug `ebo`) | [`ha-enabot`](https://github.com/Playcolors-co/ha-enabot) | branch `beta` → `…/ha-enabot#beta` |
| Enabot Local | Integration (domain `enabot_local`) | [`ha-ebo-local`](https://github.com/Playcolors-co/ha-ebo-local) | pre-releases |
| BinHass | Integration (domain `binhass`) | [`ha-binhass`](https://github.com/Playcolors-co/ha-binhass) | pre-releases |
| *(here, until retired)* | Add-on beta of `ebo` | this repo, folder `ebo/` | — |

The `ebo` add-on **bundles** its own native integration at `ebo/ha_integration/custom_components/ebo`
and installs it into the Home Assistant config dir at start-up. That is not a HACS integration and
needs no channel of its own.

## Add-ons: a branch is a channel

Supervisor's repository URL validator is

```python
RE_REPOSITORY = re.compile(r"^(?P<url>[^#]+)(?:#(?P<branch>[\w\-./]+))?$")
```

and the branch group is passed straight to `git clone`. The repository's identity is
`sha1(<whole string>)[:8]`, so `…/ha-enabot` and `…/ha-enabot#beta` are two repositories: two clones,
two add-on slugs, installable side by side with separate configuration.

Keep on the `beta` branch only the identity delta — `name` in `ebo/config.yaml`, `name` in
`repository.yaml`, and a version ahead of stable — so the two are distinguishable in the store.
Promotion is a PR from `beta` to `main`, resolving those lines in favour of `main`.

There is **no `image:` key** in `ebo/config.yaml`, so Supervisor builds the add-on on the device from
the Dockerfile: a beta version number needs no matching image published anywhere.

## Integrations: releases are channels

HACS builds the installable versions like this:

```python
filtered_releases = [r for r in releases
                     if not r.draft and (self.data.show_beta or not r.prerelease)]
self.data.published_tags = [x.tag_name for x in filtered_releases]
```

and `version_to_download` accepts only a published tag or the default branch. So one repository
carries three channels: stable releases for everyone, pre-releases for whoever turns on *Show beta
versions*, and the default branch from the version picker for bleeding-edge testing. Point HACS at
an arbitrary branch and it silently falls back to the default one — that is not a channel.

Keep `manifest.json` `version` in step with the release tag (`0.1.0b1` ↔ `v0.1.0b1`).

**One HACS integration per repository**, always: HACS resolves the content by taking the *first*
directory under `custom_components/`, so a second one takes the slot from the first and swaps it out
from under anyone who downloaded it. Grouping them in a subfolder does not help — `custom_components`
is a Python package namespace that Home Assistant scans exactly one level deep, so every entry must
be an integration domain carrying its own `manifest.json`.

## Branch protection

`main` is protected on every repo (PR required, three green checks, no force-push), and the rulesets
target `~DEFAULT_BRANCH` only — so a `beta` branch can be pushed directly.

The workflows have no `paths:` filters on purpose: a required check that is *skipped* rather than
passed blocks the merge permanently.

## Secrets

All repositories are public. Vendor SDK licences, device tokens, Kalay/Agora credentials and account
passwords never enter them: they come from the config flow or the add-on options, and vendor binaries
stay outside of git.
