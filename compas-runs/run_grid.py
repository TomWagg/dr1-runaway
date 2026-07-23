from runner import pythonProgramOptions as COMPASRunner

import numpy as np
from cogsworth.interop.compas.pop import _stringify_initC
import subprocess
import os

import sys
sys.path.append("../helpers")
import corners

print("Imports done")

grid_filename = f"temp_grid_file.txt"

if not os.path.isfile(grid_filename):
    from backpop import BackPopsteriors
    from cosmic.sample import InitialBinaryTable
    p = corners.prepare_posteriors_for_corner(
        BackPopsteriors(file="/mnt/home/twagg/ceph/dr1/ejection/posteriors.h5",
                        var_labels=np.array([r"$m_{1, i}$ [M$_\odot$]", r"$m_{2, i}$ [M$_\odot$]", r"$\log_{\rm 10}(P_i / {\rm days})$",
                                            r"$e_i$", r"$v_{\rm kick}$ [km/s]", r"$\phi_{\rm kick}$ [rad]",
                                            r"$\theta_{\rm kick}$ [rad]", r"$\omega$ [rad]"])),
    )

    print("Posteriors prepared")

    examples = p.bcm_row.iloc[np.argsort(p.log_l)[-5:]]["bin_num"].values
    example = examples[-1]
    initC = p.bpp.loc[example].iloc[[0]]
    ibt = InitialBinaryTable.InitialBinaries(
        m1=initC["mass_1"].values[0],
        m2=initC["mass_2"].values[0],
        porb=initC["porb"].values[0],
        ecc=initC["ecc"].values[0],
        tphysf=8.5,
        metallicity=0.00284,
        kstar1=initC["kstar_1"].values[0],
        kstar2=initC["kstar_2"].values[0]
    )
    ibt["bin_num"] = example

    print("Initial binary table prepared")


    with open(grid_filename, "w") as f:
        f.write('\n'.join(ibt.apply(_stringify_initC, axis=1).values))

    print("Grid file written to", grid_filename)

command = COMPASRunner(grid_filename=grid_filename, logfile_definitions="switchdefs.txt", output_directory="COMPAS_Output").shellCommand

print("Running command:", command)

subprocess.call(command, shell=True)