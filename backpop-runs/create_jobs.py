TEMPLATE = """#!/bin/bash
## Job Name
#SBATCH --job-name=dr1-JOBNAME
#SBATCH --partition=cca,gen
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=96
#SBATCH --time=2:00:00
#SBATCH -o /mnt/home/twagg/projects/dr1-runaway/backpop-runs/slurm-logs/logs_JOBNAME_%a_%A.out
#SBATCH --mail-type=ALL
#SBATCH --mail-user=twagg@flatironinstitute.org
#SBATCH --export=all

source /mnt/home/twagg/.bashrc
conda activate backpop

echo "Starting backpop simulation for JOBNAME"

backpop -i /mnt/home/twagg/projects/dr1-runaway/backpop-runs/ini-files/JOBNAME.ini -t

echo "Backpop simulation complete"
"""

# find every .ini file in the current directory and create a slurm job for each one
import os

def create_jobs():
    ini_files = [f for f in os.listdir("ini-files") if f.endswith(".ini")]
    for ini in ini_files:
        job_name = ini.split(".")[0]
        print(job_name)
        with open(f"{job_name}.slurm", "w") as f:
            f.write(TEMPLATE.replace("JOBNAME", job_name))

if __name__ == "__main__":
    create_jobs()