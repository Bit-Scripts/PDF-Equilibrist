# Roadmap

[Version française](ROADMAP.fr.md)

This is a plain list of what is planned or being considered. It is not a schedule: items move when time and
feedback allow it. Suggestions are welcome as [issues](https://github.com/Bit-Scripts/PDF-Equilibrist/issues).

## Planned

- **Follow the system light/dark setting.** The interface is dark only today. It should use a light theme by
  default when the system is not set to dark mode, and stay dark when the system (or the user, in the settings)
  asks for it. Requested by the AppImageHub catalog review, committed to publicly in
  [AppImage/appimage.github.io#10396](https://github.com/AppImage/appimage.github.io/pull/10396).
- **Interactive tools that are not wired yet** (they need an interactive canvas): freehand pencil, link areas,
  hand-drawn signature, page crop. Some of them are already visible in the ribbon but do nothing yet.

## Considered

- **AppImage update information** (`appimagetool -u` and a published `.zsync` file), so that AppImageUpdate
  and similar tools can update the AppImage. The AppImage already has its own in-app update (Help › About).
- **Security-tool screenshot in English** for `README.md` (the CVE check dialog; it needs a real network check).
- **macOS**: only if the project gains enough traction; a Homebrew formula rather than a signed app, to avoid the
  cost of an Apple developer certificate.

## Maintenance

- Replace `license = {text = ...}` in `pyproject.toml` with the SPDX form before the setuptools deprecation
  deadline (February 2027).
- Linux PPA publishing: upload the source archive once and the second series without it, polling Launchpad
  between the two, instead of relying on a manual single-series rerun when an upload times out.
- Fedora COPR: decide whether to keep the `rawhide` chroot, which fails independently of the code.
