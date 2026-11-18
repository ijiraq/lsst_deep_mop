from trippy import scamp
import os
from astropy.io import fits

root = '/arc/projects/NewHorizons'
year = '2024'
visit = '20240611'
diffs_dir = f'{root}/HSC_{year}/DIFFS/{visit}/'

if not os.path.isfile('default.conv'):
    print('Writing conv file.')
    scamp.makeParFiles.writeConv(overwrite=True)


for c in range(104):
    if c == 9: continue

    deep_coadd_fn = f'{diffs_dir}/{c}/injected_deepCoadd_small_{visit}_{c}_{c}..fits'

    with fits.open(deep_coadd_fn) as han:
        fits.writeto('junk.fits', han[1].data, han[1].header, overwrite=True)


    catalog_name = deep_coadd_fn.replace('.fits', '.cat')

    scamp.runSex('HSC_LDAC.sex', 'junk.fits', options={'CATALOG_NAME': catalog_name, 'SATUR_LEVEL': '10000'}, verbose=True)
    catalog = scamp.getCatalog(catalog_name, paramFile = 'sextract.param')
    os.remove('junk.fits')


    


