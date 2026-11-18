from lsst.daf.butler import Butler
import argparse, os, glob
import numpy as np
import pandas as pd
import matplotlib.path as mpltPath

parser = argparse.ArgumentParser()
parser.add_argument('butler_dir')
parser.add_argument('day_obs')
args = parser.parse_args()

print("Making Butler")

butler = Butler(args.butler_dir)
print('Querying Butler')

dates = []
visit_list = []
for ref in butler.registry.queryDimensionRecords('visit', datasets='raw', collections='HSC/raw/all', \
where="instrument='HSC' AND visit.day_obs={} AND visit.observation_reason='science'".format(args.day_obs)):
    begin = ref.timespan.begin.jd
    end = ref.timespan.end.jd
    dates.append(begin)
    dates.append(end)
    if (ref.id not in visit_list):
        visit_list.append(ref.id)

mean_date = np.mean(dates)

print('Generating fake KBO prositions')
os.system('/arc/projects/NewHorizons/PSFscripts/MakeFake3 1 {} 1000'.format(mean_date))

print('Converting the injection catalogue to the LSST format')
df = pd.read_fwf('NHF_{}_fk4.txt'.format(str(mean_date)))
df = df.rename(columns={'RA':'ra', 'DEC':'dec'})

#If someone can write this better PLEASE do
points = list(zip(df.ra, df.dec))
injection_cat = pd.DataFrame(columns=['visit', 'detector', 'ra', 'dec', 'mag'])
for index, visit in enumerate(visit_list):
    ccd_visit = butler.get('visitSummary', instrument='HSC', visit=visit, collections='u/NH/completeProcessing')

    for ccd in ccd_visit:
        detector = ccd['id']
        raCorners = ccd['raCorners']
        decCorners = ccd['decCorners']
        verts = [(raCorners[0], decCorners[0]), (raCorners[1], decCorners[1]), (raCorners[2], decCorners[2]), (raCorners[3], decCorners[3])]
        path = mpltPath.Path(verts)
        x = path.contains_points(points)

        for i, r in df.iterrows():
            if (x[i]):
                injection_cat.loc[len(injection_cat)] = [visit, detector, r['ra'], r['dec'], r['mag']]
    print(f"{index}/{len(visit_list)} ({100*index/len(visit_list):0.1f}%)", end="\r")

injection_cat.insert(0, 'injection_id', list(range(len(injection_cat))))
injection_cat.insert(5, 'source_type', 'Gaussian')
injection_cat['detector'] = injection_cat['detector'].astype('int64')

injection_cat.to_csv('injection_catalogue-{}.csv'.format(args.day_obs), index=False)

print('Injection file: injection_catalogue-{}.csv'.format(args.day_obs))