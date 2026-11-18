#!/usr/bin/env python
# This file is part of lsst_deep_mop / sso_injection.
"""Write example Keplerian orbit and sky Trail tables (no pipetask required)."""

from __future__ import annotations

import argparse
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Sample one SD-MOC cell and write example orbit + sky tables "
            "(ECSV/parquet). Optional Arrokoth-centered mode uses Horizons."
        )
    )
    parser.add_argument(
        "-o",
        "--outdir",
        default=".",
        help="Output directory for example_orbits.* / example_sky.*",
    )
    parser.add_argument("--density", type=float, default=3000.0)
    parser.add_argument("--healpix-order", type=int, default=6)
    parser.add_argument("--ipix", type=int, default=30472, help="HEALPix nested pixel id")
    parser.add_argument("--dist-bin", type=int, default=0)
    parser.add_argument("--r-inner", type=float, default=40.0)
    parser.add_argument("--r-outer", type=float, default=46.0)
    parser.add_argument("--epoch", default="2022-06-20", help="Sky propagation epoch")
    parser.add_argument(
        "--arrokoth",
        action="store_true",
        help="Use Arrokoth's Horizons cell instead of --ipix/--dist-bin",
    )
    args = parser.parse_args(argv)

    from astropy.time import Time

    from sso_injection.config import OrbitPopulationConfig
    from sso_injection.diagnostics import (
        cell_for_heliocentric_state,
        fetch_arrokoth_ephemeris,
        propagate_orbits_to_sky,
    )
    from sso_injection.sample import sample_sdmoc_cell
    from sso_injection.sdmoc import SDMocCell, SDMocIndex

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    config = OrbitPopulationConfig()
    config.density = float(args.density)
    config.healpix_order = int(args.healpix_order)
    config.distance_inner_au = float(args.r_inner)
    config.distance_outer_au = float(args.r_outer)
    config.n_distance_bins = 1
    config.distance_bin_edges_au = []

    if args.arrokoth:
        info = fetch_arrokoth_ephemeris(args.epoch)
        config.model_epoch_mjd = float(info["obstime"].mjd)
        index = SDMocIndex(config)
        cell = cell_for_heliocentric_state(index, info["x_au"], info["y_au"], info["z_au"])
        obstime = info["obstime"]
        print(f"Arrokoth cell ipix={cell.ipix} dist_bin={cell.dist_bin} r={info['r_au']:.3f} AU")
    else:
        config.model_epoch_mjd = float(Time(args.epoch).mjd)
        index = SDMocIndex(config)
        cell = SDMocCell(ipix=int(args.ipix), dist_bin=int(args.dist_bin))
        obstime = Time(args.epoch)

    orbits = sample_sdmoc_cell(cell, index, config=config)
    if len(orbits) == 0:
        raise SystemExit(f"No orbits sampled for cell {cell}; try higher --density")

    sky = propagate_orbits_to_sky(orbits, obstime)

    orbit_ecsv = outdir / "example_orbits.ecsv"
    orbit_parquet = outdir / "example_orbits.parquet"
    sky_ecsv = outdir / "example_sky.ecsv"
    orbits.write(orbit_ecsv, format="ascii.ecsv", overwrite=True)
    orbits.write(orbit_parquet, format="parquet", overwrite=True)
    sky.write(sky_ecsv, format="ascii.ecsv", overwrite=True)
    print(f"Wrote {len(orbits)} orbits → {orbit_ecsv}, {orbit_parquet}")
    print(f"Wrote {len(sky)} sky rows → {sky_ecsv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
