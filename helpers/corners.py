import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import AutoMinorLocator
import astropy.units as u

def calculate_mass_accreted(bpp):
    """total change in mass_2 across all mass-transfer episodes, per binary.

    Parameters
    ----------
    bpp : `pandas.DataFrame`
        COSMIC bpp table. must contain "bin_num", "evol_type" and "mass_2".
        mass-transfer episodes are bracketed by evol_type == 3 (RLOF start)
        and evol_type == 4 (RLOF end). rows are assumed to be in
        chronological order within each bin_num, as COSMIC outputs them.

    Returns
    -------
    mass_accreted : `pandas.Series`
        indexed by sorted bin_num, one entry per unique binary. each value
        is the summed (mass_2_end - mass_2_start) over that binary's
        mass-transfer episodes, or 0.0 if it has no evol_type 3/4 rows.
    """
    # sorted unique binaries, this fixes the output ordering
    unique_bin_nums = np.sort(bpp["bin_num"].unique())
    mass_accreted = pd.Series(0.0, index=pd.Index(unique_bin_nums, name="bin_num"),
                              name="mass_accreted")

    # only the RLOF boundary rows matter, drop everything else
    mt_rows = bpp[bpp["evol_type"].isin([3, 4])]

    # process each binary independently, preserving chronological row order
    for bin_num, group in mt_rows.groupby("bin_num", sort=False):
        total = 0.0
        start_mass = None
        for evol_type, mass_2 in zip(group["evol_type"], group["mass_2"]):
            if evol_type == 3:
                # episode begins, record the secondary mass at onset
                start_mass = mass_2
            elif evol_type == 4 and start_mass is not None:
                # episode ends, accumulate the change over this episode
                total += mass_2 - start_mass
                start_mass = None
        mass_accreted.loc[bin_num] = total

    return mass_accreted

def prepare_posteriors_for_corner(p):
    p.bcm_row["log_lum_2"] = np.log10(p.bcm_row["lum_2"])
    
    t_travel = p.bcm_row["tphys"] - p.bpp[p.bpp["evol_type"] == 15]["tphys"]
    p.bcm_row["travel_time"] = np.where(np.isfinite(t_travel), t_travel, 0.0)
    p.bcm_row["travel_distance"] = ((p.bcm_row["vsys_2_total"].values) * u.km/u.s * p.bcm_row["travel_time"].values * u.Myr).to(u.pc).value

    p.bcm_row["time_to_explode"] = p.bpp[p.bpp["evol_type"] == 16]["tphys"] - p.bcm_row["tphys"]

    p.bpp["bin_num"] = p.bpp.index
    p.bcm_row["mass_accreted"] = np.zeros(len(p.bcm_row))
    macc = calculate_mass_accreted(p.bpp)
    p.bcm_row.loc[macc.index, "mass_accreted"] = macc.values

    p.bcm_row["log_init_sep"] = np.full(len(p.bcm_row), np.nan)
    init_sep = p.bpp.drop_duplicates(subset="bin_num", keep="first")["sep"]
    p.bcm_row.loc[init_sep.index, "log_init_sep"] = np.log10(init_sep.values)

    p.bcm_row["log_sn_sep"] = np.full(len(p.bcm_row), 0.0)
    sn_sep = p.bpp[p.bpp["evol_type"] == 15].drop_duplicates(subset="bin_num", keep="first")["sep"]
    p.bcm_row.loc[sn_sep.index, "log_sn_sep"] = np.log10(sn_sep.values)

    p.bcm_row["m1_at_sn"] = np.full(len(p.bcm_row), np.nan)
    m1_at_sn = p.bpp[p.bpp["evol_type"] == 15].drop_duplicates(subset="bin_num", keep="first")['mass_1']
    p.bcm_row.loc[m1_at_sn.index, "m1_at_sn"] = m1_at_sn.values

    p.bcm_row["m2_at_sn"] = np.full(len(p.bcm_row), np.nan)
    m2_at_sn = p.bpp[p.bpp["evol_type"] == 15].drop_duplicates(subset="bin_num", keep="first")['mass_2']
    p.bcm_row.loc[m2_at_sn.index, "m2_at_sn"] = m2_at_sn.values

    p.bcm_row["he_core_mass"] = np.full(len(p.bcm_row), np.nan)
    he_zams_rows = p.bpp[p.bpp["kstar_2"] == 7].drop_duplicates(subset="bin_num", keep="first")
    he_core_mass = he_zams_rows["massc_he_layer_2"].values + he_zams_rows["massc_co_layer_2"].values
    p.bcm_row.loc[he_zams_rows.index, "he_core_mass"] = he_core_mass
    # p.bcm_row["he_core_mass"] = p.bcm_row["massc_he_layer_2"].values + p.bcm_row["massc_co_layer_2"].values

    return p

def plot_corner(p, which_vars, extra_vars, extra_labels, label_meanings, main_title=None, constraints=None,
                cartoon_path=None, dark_colour=None, colour=None, ranges=None, percentiles_colour="red",
                truths=None, save=None, show=True):

    N_PANELS = len(which_vars) + extra_vars.shape[1]

    if ranges is None:
        ranges = list(np.repeat(0.99, N_PANELS))

    corner_kwargs = {
        "hist_kwargs": {"histtype": "stepfilled"},
        "label_kwargs": {"fontsize": 15},
        "bins": 25,
        "truth_color": '#e74dcd',
    }
    if dark_colour is not None:
        corner_kwargs["color"] = dark_colour
    if colour is not None:
        corner_kwargs["hist_kwargs"]["color"] = colour

    fig = p.cornerplot(
        which_vars=which_vars,
        show=False,
        extra_vars=extra_vars,
        extra_labels=extra_labels,
        truths=truths,
        **corner_kwargs,
        range=ranges,
    )

    point_inds = [i for i, var in enumerate(p.var_names) if var in which_vars]

    hist_vals = np.vstack(
        [p.points[:, point_inds].T, extra_vars.T]
    ).T

    axes = np.array(fig.get_axes()).reshape((N_PANELS, N_PANELS))

    labels = list(p.labels[point_inds]) + extra_labels
    for i in range(N_PANELS):
        axes[i, i].annotate(labels[i], xy=(0.5, 1.01 if label_meanings[i] is None else 1.08), xycoords="axes fraction", ha="center", va="bottom", fontsize=15)
        if label_meanings[i] is not None:
            axes[i, i].annotate(label_meanings[i], xy=(0.5, 1.01), xycoords="axes fraction", ha="center", va="bottom", fontsize=10)
        percs = np.nanpercentile(hist_vals[:, i], [10, 25, 75, 90], weights=np.exp(p.log_w), method="inverted_cdf")

        for perc_ind, style in zip([0, 1, 2, 3], ["--", "-", "-", "--"]):
            axes[i, i].axvline(percs[perc_ind], color=percentiles_colour, linestyle=style)

    if main_title is not None:
        axes[0, 5].annotate(main_title, xy=(0.5, 0.5), xycoords="axes fraction", ha="center", va="center", fontsize=50)

    if constraints is not None:
        axes[0, 5].annotate("Constraints assumed:", xy=(-1.0, 0.2), xycoords="axes fraction", ha="left", va="top", fontsize=30)
        for i, constraint in enumerate(constraints):
            axes[0, 5].annotate('• ' + constraint, xy=(-0.7, 0.15 - (i + 1) * 0.2), xycoords="axes fraction", ha="left", va="top", fontsize=20)

    if cartoon_path is not None:
        inset_ax = fig.add_axes([0.6, 0.46, 0.35, 0.45])
        im = plt.imread(cartoon_path)
        inset_ax.imshow(im)
        inset_ax.axis("off")

    for ax in np.ravel(fig.axes):
        ax.xaxis.set_minor_locator(AutoMinorLocator())
        ax.yaxis.set_minor_locator(AutoMinorLocator())

    if save is not None:
        plt.savefig(save, bbox_inches="tight", format="pdf", dpi=300)

    if show:
        plt.show()

    return fig, axes