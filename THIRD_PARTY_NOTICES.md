# Third-party sources

This repository contains port glue, configuration, preparation tools and build metadata. Dependencies are obtained separately. Pinned revisions and patch hashes are in `dependencies.lock.json`.

- [ReXGlue SDK](https://github.com/rexglue/rexglue-sdk), v0.10.0: Xbox 360 recompilation tools and runtime. Retain the license and notices of the exact SDK and its dependencies when building/distributing.
- [masseffect-nx](https://github.com/nebadasSwifty/masseffect-nx), pinned Horizon SDK fork: runtime and Switch support. This repository does not redistribute its source tree.
- [prototype-switch](https://github.com/fungalspores/prototype-switch), GPL-3.0: reference port, SDK/Mesa patches and packaging tools. `cmake/switch-devkitA64.cmake` is adapted from its generic toolchain and retains its attribution. This project adds relocation support for CMake compiler probes. No Prototype game code or game-specific address hooks are included.
- [mesa-switch](https://github.com/danfromtico/mesa-switch): Mesa/NVK. Its component-specific licenses and `docs/license.rst` apply to the separately built driver.
- [Forwarder-Mod](https://github.com/Skywalker25/Forwarder-Mod): NSP forwarder, commit `9853bd9167d5a7f0c5fdf935864245c1fbcf8282`. Source is obtained separately; the one declaration adjustment is documented in `docs/BUILD.md`.
- [devkitPro](https://devkitpro.org/): devkitA64, libnx and portlibs; their respective licenses apply. Only a download/extraction helper is included here.

Original port glue and scripts in this repository are provided under GPL-3.0. No license in this repository grants rights to the commercial game's executable, assets or translated code. Game titles and trademarks belong to their respective owners.
