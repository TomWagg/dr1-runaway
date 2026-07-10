import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import astropy.units as u

import cogsworth
from cosmic.evolve import Evolve
from cosmic.sample import InitialBinaryTable
from cosmic.utils import parse_inifile

DISTANCE_MODULUS = 24.39


def get_ZAMS_he_relations(stellar_engine, metallicity, ibt):

    ibt_run = ibt.copy()
    SSEDict["stellar_engine"] = stellar_engine
    ibt_run.metallicity = np.ones_like(zams_mass) * metallicity
    
    bpp, bcm, initC, kick_info = Evolve.evolve(
        ibt_run, BSEDict=BSEDict, SSEDict=SSEDict, nproc=28, progress=True, dtp=0.0
    )

    # find He-ZAMS rows
    he_zams_row = bcm[bcm["kstar_1"] >= 4].drop_duplicates(subset="bin_num", keep="first")
    last_ms_row = bcm[bcm["kstar_1"] <= 1].drop_duplicates(subset="bin_num", keep="last")

    last_ms_row["metallicity"] = np.ones_like(last_ms_row["bin_num"]) * metallicity
    phot = cogsworth.obs.observables.get_photometry(
        filters=["WFC3_UVIS_F336W"], final_bpp=last_ms_row,
        final_pos=np.zeros((len(last_ms_row), 3)) * u.pc,
        distances=np.ones_like(last_ms_row["bin_num"]) * 10 * u.kpc, ignore_extinction=True
    )

    stats = pd.DataFrame({
        "zams_mass": initC["mass_1"],
        "he_zams_mass": np.zeros_like(initC["mass_1"]),
        "ms_lifetime": np.zeros_like(initC["mass_1"]),
        "f336w_mag": np.zeros_like(initC["mass_1"]),
    }, index=initC["bin_num"])
    stats.loc[he_zams_row["bin_num"], "he_zams_mass"] = (he_zams_row["massc_he_layer_1"].values + he_zams_row["massc_co_layer_1"].values)
    stats.loc[last_ms_row["bin_num"], "ms_lifetime"] = last_ms_row["tphys"].values
    stats.loc[last_ms_row["bin_num"], "f336w_mag"] = phot["WFC3_UVIS_F336W_abs_1"].values + DISTANCE_MODULUS

    return stats

if __name__ == "__main__":

    zams_mass = np.geomspace(6, 150, 1000)

    metallicities = [0.00284]#, 0.003039]
    stellar_engines = ["sse"]#, "metisse"]

    ibt = InitialBinaryTable.InitialBinaries(
        m1=zams_mass,
        m2=np.zeros_like(zams_mass),
        kstar1=np.ones_like(zams_mass) * 1,
        kstar2=np.ones_like(zams_mass) * 0,
        porb=np.ones_like(zams_mass) * -1,
        ecc=np.ones_like(zams_mass) * -1,
        metallicity=np.ones_like(zams_mass) * -1,
        tphysf=np.ones_like(zams_mass) * 500,
    )

    BSEDict, SSEDict, seed_int, filters, convergence, sampling = parse_inifile("params.ini")

    stats = {
        se: get_ZAMS_he_relations(se, met, ibt) for se, met in zip(stellar_engines, metallicities)
    }

    for key in stats:
        stats[key].to_hdf(f"zams_he_relations.h5", key=key, mode="a")
