#!/usr/bin/env python
# This file is part of sso_injection.
"""CLI: Arrokoth-centered SD-MOC injection diagnostic figure."""

from __future__ import annotations

import argparse
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Query JPL Horizons for Arrokoth, sample the local SD-MOC cell, and "
            "write diagnostics: fiducial vs +24h sky positions and CDFs of "
            "a/e/i/Omega/omega/M."
        )
    )
    parser.add_argument(
        "--epoch",
        default="2022-06-20",
        help="Ephemeris epoch (default: 2022-06-20)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="docs/arrokoth_injection_diagnostics.png",
        help="Output PNG path (default: docs/arrokoth_injection_diagnostics.png)",
    )
    parser.add_argument(
        "--density",
        type=float,
        default=20000.0,
        help="Temporary density override so the local cell is well populated",
    )
    parser.add_argument(
        "--trail-hours",
        type=float,
        default=4.0,
        help="Trail vector length in hours of sky motion",
    )
    parser.add_argument(
        "--neighbors",
        action="store_true",
        help="Also sample HEALPix neighbors of Arrokoth's cell",
    )
    parser.add_argument(
        "--max-plot",
        type=int,
        default=2000,
        help="Cap number of sources drawn in the figure",
    )
    args = parser.parse_args(argv)

    from sso_injection.diagnostics import run_arrokoth_injection_diagnostics

    sky, info, path = run_arrokoth_injection_diagnostics(
        args.epoch,
        output_path=Path(args.output),
        density_override=args.density,
        trail_hours=args.trail_hours,
        include_neighbors=args.neighbors,
        max_plot_sources=args.max_plot,
    )
    print(
        f"Wrote {path} with {len(sky)} synthetic sources near Arrokoth "
        f"(RA={info['ra_deg']:.4f}, Dec={info['dec_deg']:.4f}, "
        f"r={info['r_au']:.3f} AU, delta={info['delta_au']:.3f} AU)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
