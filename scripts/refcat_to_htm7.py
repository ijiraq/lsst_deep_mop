import glob
import astropy.table
import os

refcat_dir = "/arc/projects/LSST/tigress-web.princeton.edu/~HSC/refcats/gaia_dr3_20230707"
out_dir = "/arc/projects/NewHorizons/HSC_2024"

out_file = f"{out_dir}/{os.path.basename(refcat_dir)}.ecsv"

table = astropy.table.Table(names=("filename", "htm7"), dtype=("str", "int"))
files = glob.glob(f"{refcat_dir}/[0-9]*.fits")

for i, file in enumerate(files):
    # running status, overwriting each print statement as it proceeds
    print(f"{i}/{len(files)} ({100*i/len(files):0.1f}%)", end="\r")

    # extract file index; add row to table
    file_index = int(os.path.basename(os.path.splitext(file)[0]))
    table.add_row((file, file_index))

table.write(out_file, overwrite=True)
print(f"Output written to: {out_file}")
