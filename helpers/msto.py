"""
Main-sequence turn-off (MSTO) magnitude in HST WFC3/UVIS F336W as a function of age.

Uses EZPadova (https://mfouesneau.github.io/ezpadova/) to query PARSEC isochrones
from the CMD web interface, finds the turn-off point of each isochrone, and returns
the absolute F336W magnitude of the turn-off versus age. A helper builds an
interpolator so you can map an arbitrary age to the MSTO F336W magnitude.

Requires the `ezpadova` package (installed in the `backpop` conda env) and scipy.
Run with:  conda run -n backpop python msto_f336w.py
"""

from __future__ import annotations

import os

import numpy as np
import pandas as pd
from scipy.interpolate import interp1d
from scipy.signal import find_peaks

import ezpadova
import matplotlib.pyplot as plt

# PARSEC reference solar metallicity (Bressan et al. 2012; Z_sun = 0.0152).
ZSUN_PARSEC = 0.0152

# CMD photometric system file containing the WFC3/UVIS wide filters (incl. F336W),
# with the 2021 updated throughputs and zeropoints.
WFC3_UVIS_PHOTSYS = "YBC_tab_mag_odfnew/tab_mag_wfc3_202101_wide.dat"

# Name of the F336W magnitude column returned by the CMD query.
F336W_COL = "F336Wmag"


def find_msto_index(logTe, prominence: float = 0.01) -> int:
    """Index of the main-sequence turn-off along an isochrone, from logTe shape.

    The PARSEC v1.2S evolutionary-stage ``label`` column is not reliable here, so
    the turn-off is located purely from the morphology of log(Teff) as one walks
    up the isochrone in order of increasing initial mass. The turnoff is the first peak
    in logTe that follows a valley (the "hook" feature).

    Parameters
    ----------
    logTe : array-like
        log10(Teff) ordered by increasing initial mass along one isochrone.
    prominence : float
        Minimum peak/valley prominence (dex) for a feature to count, filtering
        numerical wiggles.

    Returns
    -------
    int
        Index (into the passed, mass-ordered array) of the turn-off point.
    """
    peaks, _ = find_peaks(logTe, prominence=prominence)
    valleys, _ = find_peaks(-logTe, prominence=prominence)

    # usually: first peak that follows a dip.
    for p in peaks:
        if valleys.size and valleys.min() < p:
            return int(p)

    # fallback: bluest point of the main sequence.
    return int(np.argmax(logTe))

def find_msto_index_hottest(logTe) -> int:
    return int(np.argmax(logTe))


def _msto_from_isochrone(
    iso: pd.DataFrame,
    mag_col: str = F336W_COL,
    prominence: float = 0.01,
    method="hook",
) -> float:
    """Return the magnitude at the turn-off point of a single isochrone."""
    iso = iso.sort_values("Mini").reset_index(drop=True)
    if method == "hook":
        idx = find_msto_index(iso["logTe"].values, prominence=prominence)
        return float(iso[mag_col].iloc[idx])
    elif method == "hottest":
        idx = find_msto_index_hottest(iso["logTe"][iso["label"] == 1].values)
        return float(iso[iso["label"] == 1][mag_col].iloc[idx])
    elif method == "brightest":
        idx = find_msto_index_hottest(iso["logL"][iso["label"] == 1].values)
        return float(iso[iso["label"] == 1][mag_col].iloc[idx])


def _isochrone_cache_path(z: float, logage_range, dlogage: float) -> str:
    """Default on-disk cache filename encoding the query parameters."""
    tag = f"Z{z:.5f}_la{logage_range[0]:.2f}-{logage_range[1]:.2f}_d{dlogage:.3f}"
    return f"isochrones_{tag}.pkl"


def fetch_isochrones(
    z_over_zsun: float = 0.2,
    logage_range: tuple[float, float] = (6.0, 10.13),
    dlogage: float = 0.05,
    zsun: float = ZSUN_PARSEC,
    photsys_file: str = WFC3_UVIS_PHOTSYS,
    cache_path: str | None = None,
    refresh: bool = False,
) -> pd.DataFrame:
    """Download (or load from disk) the raw PARSEC isochrone table.

    The CMD query is the slow part, so the full isochrone DataFrame is cached to
    a pickle keyed on (Z, age grid). Subsequent calls with the same parameters
    read the cache instead of re-querying, which lets you iterate on the turn-off
    detection without re-downloading. Pass ``refresh=True`` to force a re-query.

    Parameters
    ----------
    z_over_zsun, logage_range, dlogage, zsun, photsys_file :
        Same meaning as in :func:`msto_f336w_track`.
    cache_path : str or None
        Path to the pickle cache. If None, a default name derived from the query
        parameters is used (so different metallicities/grids don't collide).
    refresh : bool
        If True, ignore any existing cache and re-download.

    Returns
    -------
    pandas.DataFrame
        The full isochrone table as returned by ``ezpadova.get_isochrones``.
    """
    z = z_over_zsun * zsun
    if cache_path is None:
        cache_path = _isochrone_cache_path(z, logage_range, dlogage)

    if not refresh and os.path.exists(cache_path):
        return pd.read_pickle(cache_path)

    isochrones = ezpadova.get_isochrones(
        logage=(logage_range[0], logage_range[1], dlogage),
        Z=(z, z, 0.0),
        photsys_file=photsys_file,
    )
    isochrones.to_pickle(cache_path)
    return isochrones


def msto_f336w_track(
    isochrones: pd.DataFrame,
    prominence: float = 0.01,
    method: str = "hook"
) -> pd.DataFrame:
    """Compute the MSTO F336W (WFC3/UVIS) absolute magnitude as a function of age.

    Parameters
    ----------
    isochrones : pandas.DataFrame
        Isochrone table from :func:`fetch_isochrones`.
    prominence : float
        Minimum peak/valley prominence (dex) for a feature to count, filtering
        numerical wiggles. Passed to :func:`find_msto_index`.

    Returns
    -------
    pandas.DataFrame
        Columns: ``logAge`` (log10 age/yr), ``age_yr`` (linear age), and
        ``msto_F336W`` (absolute F336W magnitude of the turn-off), sorted by age.
    """
    rows = []
    for logage, iso in isochrones.groupby("logAge"):
        mag = _msto_from_isochrone(iso, prominence=prominence, method=method)
        rows.append((float(logage), 10.0 ** float(logage), mag))

    track = pd.DataFrame(rows, columns=["logAge", "age_yr", "msto_F336W"])
    track = track.dropna(subset=["msto_F336W"]).sort_values("age_yr").reset_index(drop=True)
    return track


def make_msto_interpolator(track: pd.DataFrame, in_log_age: bool = True):
    """Build a callable mapping age -> MSTO F336W magnitude from a track table.

    Interpolation is done linearly in log10(age) by default, which is smoother
    for isochrone grids that are uniform in log-age.

    Parameters
    ----------
    track : pandas.DataFrame
        Output of :func:`msto_f336w_track`.
    in_log_age : bool
        If True (default), the returned function expects age in years and
        interpolates in log10(age). If False, it interpolates linearly in age.

    Returns
    -------
    callable
        ``f(age_yr) -> msto_F336W``. Accepts scalars or array-likes. Values
        outside the tabulated age range are extrapolated.
    """
    if in_log_age:
        base = interp1d(
            track["logAge"].values,
            track["msto_F336W"].values,
            kind="linear",
            fill_value="extrapolate",
        )
        return lambda age_yr: base(np.log10(age_yr))

    return interp1d(
        track["age_yr"].values,
        track["msto_F336W"].values,
        kind="linear",
        fill_value="extrapolate",
    )
