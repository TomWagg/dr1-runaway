from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

# columns + colspecs for Brott+2011 evol/*.track.dat (from your byte-by-byte snippet)
# note: pandas colspecs are 0-based, end-exclusive. bytes in the ReadMe are 1-based, end-inclusive.

TRACK_COLS: list[str] = [
    "t", "Mass", "Teff", "logL", "R", "log(Mdot)", "logg", "Vsurf", "Prot", "Vcrit", "Ge",
    "eps(H)", "eps(He)", "eps(Li)", "eps(Be)", "eps(B)", "eps(C)", "eps(N)", "eps(O)", "eps(F)", "eps(Ne)",
    "eps(Na)", "eps(Mg)", "eps(Al)", "eps(Si)", "eps(Fe)", "sH1", "sHe3", "sHe4", "sLi7", "sBe9", "sB10",
    "sB11", "sC12", "sC13", "sN14", "sN15", "sO16", "sO17", "sO18", "sF19", "sNe20", "sNe21", "sNe22",
    "sNa23", "sMg24", "sMg25", "sMg26", "sAl26", "sAl27", "sSi28", "sSi29", "sSi30", "sFe56", "cH1", "cHe3",
    "cHe4", "cLi7", "cBe9", "cB10", "cB11", "cC12", "cC13", "cN14", "cN15", "cO16", "cO17", "cO18", "cF19",
    "cNe20", "cNe21", "cNe22", "cNa23", "cMg24", "cMg25", "cMg26", "cAl26", "cAl27", "cSi28", "cSi29",
    "cSi30", "cFe56"]

# byte ranges from your table (start-end, 1-based inclusive) converted to pandas colspecs:
# (start-1, end) 0-based with end-exclusive
TRACK_COLSPECS: list[tuple[int, int]] = [
    (0, 12), (13, 22), (23, 35), (36, 44), (45, 55), (56, 65), (66, 75), (76, 86),
    (87, 102), (103, 113), (114, 123), (124, 133), (134, 143), (144, 153),
    (154, 163), (164, 173), (174, 183), (184, 193), (194, 203), (204, 213),
    (214, 223), (224, 233), (234, 243), (244, 253), (254, 263), (264, 273),
    (274, 286), (287, 299), (300, 312), (313, 325), (326, 338), (339, 351),
    (352, 364), (365, 377), (378, 390), (391, 403), (404, 416), (417, 429),
    (430, 442), (443, 455), (456, 468), (469, 481), (482, 494), (495, 507),
    (508, 520), (521, 533), (534, 546), (547, 559), (560, 572), (573, 585),
    (586, 598), (599, 611), (612, 624), (625, 637), (638, 650), (651, 663),
    (664, 676), (677, 689), (690, 702), (703, 715), (716, 728), (729, 741),
    (742, 754), (755, 767), (768, 780), (781, 793), (794, 806), (807, 819),
    (820, 832), (833, 845), (846, 858), (859, 871), (872, 884), (885, 897),
    (898, 910), (911, 923), (924, 936), (937, 949), (950, 962), (963, 975),
    (976, 988), (989, 1001),
]

@dataclass(frozen=True)
class BrottTrackKey:
    m_init: int
    v_zams: int
    galaxy: str  # mw, lmc, smc


def _normalise_galaxy(galaxy: str) -> str:
    galaxy = galaxy.strip().lower()
    if galaxy not in {"mw", "lmc", "smc"}:
        raise ValueError(f"galaxy must be one of 'mw', 'lmc', 'smc' (got {galaxy!r})")
    return galaxy


def track_filename(key: BrottTrackKey) -> str:
    return f"f{key.m_init:d}-{key.v_zams:d}.{key.galaxy}.track.dat"


def read_brott2011_track_fwf(
    path: str | Path,
    *,
    columns: list[str] = TRACK_COLS,
    colspecs: list[tuple[int, int]] = TRACK_COLSPECS,
    comment: str | None = "#",
) -> pd.DataFrame:
    """
    Read a Brott+2011 evol/*.track.dat fixed-width file into a DataFrame.

    Parameters
    ----------
    path
        path to a single track file, e.g. f10-0.mw.track.dat
    columns, colspecs
        defaults match the Brott+2011 evol track layout (as pasted).
    comment
        comment character in the file (set to None to disable)

    Returns
    -------
    pandas.DataFrame
    """
    df = pd.read_fwf(
        Path(path),
        colspecs=colspecs,
        names=columns,
        header=None,
        comment=comment,
    )

    # best-effort numeric conversion
    for c in df.columns:
        df[c] = pd.to_numeric(df[c])

    return df


def read_track_dataframe(
    directory: str | Path,
    m_init: int,
    v_zams: int,
    galaxy: str,
) -> pd.DataFrame:
    """
    Convenience wrapper: locate a track file by (m_init, v_zams, galaxy) and read it.
    """
    directory = Path(directory)
    key = BrottTrackKey(int(m_init), int(v_zams), _normalise_galaxy(galaxy))
    fpath = directory / track_filename(key)

    if not fpath.exists():
        raise FileNotFoundError(f"missing track file at {fpath}")

    df = read_brott2011_track_fwf(fpath)

    # add metadata columns up front
    df.insert(0, "m_init", key.m_init)
    df.insert(1, "v_zams", key.v_zams)
    df.insert(2, "galaxy", key.galaxy)

    return df