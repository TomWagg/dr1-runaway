#!/bin/bash
## Job Name
#SBATCH --job-name=dr1-ejection_min1
#SBATCH --partition=cca,gen
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=96
#SBATCH --time=2:00:00
#SBATCH -o /mnt/home/twagg/projects/dr1-runaway/backpop-runs/slurm-logs/logs_ejection_min1_%a_%A.out
#SBATCH --mail-type=ALL
#SBATCH --mail-user=twagg@flatironinstitute.org
#SBATCH --export=all

source /mnt/home/twagg/.bashrc
conda activate backpop

echo "Starting backpop simulation for ejection_min1"

backpop -i /mnt/home/twagg/projects/dr1-runaway/backpop-runs/ini-files/ejection_min1.ini -t

echo "Backpop simulation complete"
