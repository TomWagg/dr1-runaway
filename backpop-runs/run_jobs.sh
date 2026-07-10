# run every .slurm file in directory, spacing by 1 second to avoid overloading the scheduler
for f in *.slurm; do
    sbatch $f
    sleep 1
done