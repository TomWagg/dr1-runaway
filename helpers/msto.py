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


def _isochrone_cache_path(Z: float, logage_range, dlogage: float) -> str:
    """Default on-disk cache filename encoding the query parameters."""
    tag = f"Z{Z:.5f}_la{logage_range[0]:.2f}-{logage_range[1]:.2f}_d{dlogage:.3f}"
    return f"isochrones_{tag}.pkl"


def fetch_isochrones(
    Z: float,
    logage_range: tuple[float, float] = (6.0, 10.13),
    dlogage: float = 0.05,
    photsys_file: str = WFC3_UVIS_PHOTSYS,
    cache_folder: str | None = None,
    refresh: bool = False,
) -> pd.DataFrame:
    """Download (or load from disk) the raw PARSEC isochrone table.

    The CMD query is the slow part, so the full isochrone DataFrame is cached to
    a pickle keyed on (Z, age grid). Subsequent calls with the same parameters
    read the cache instead of re-querying, which lets you iterate on the turn-off
    detection without re-downloading. Pass ``refresh=True`` to force a re-query.

    Parameters
    ----------
    Z : float
        Metallicity of the isochrones.
    logage_range, dlogage, zsun, photsys_file :
        Same meaning as in :func:`msto_f336w_track`.
    cache_folder : str or None
        Path to the folder where the pickle cache will be stored. If None, current directory is used.
    refresh : bool
        If True, ignore any existing cache and re-download.

    Returns
    -------
    pandas.DataFrame
        The full isochrone table as returned by ``ezpadova.get_isochrones``.
    """
    cache_folder = "." if cache_folder is None else cache_folder
    os.makedirs(cache_folder, exist_ok=True)
    cache_path = os.path.join(cache_folder, _isochrone_cache_path(Z, logage_range, dlogage))

    if not refresh and os.path.exists(cache_path):
        return pd.read_pickle(cache_path)

    isochrones = ezpadova.get_isochrones(
        logage=(logage_range[0], logage_range[1], dlogage),
        Z=(Z, Z, 0.0),
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


def make_msto_interpolator(track: pd.DataFrame):
    base = interp1d(
        track["logAge"].values,
        track["msto_F336W"].values,
        kind="linear",
        fill_value="extrapolate",
    )
    return lambda age_yr: base(np.log10(age_yr))

