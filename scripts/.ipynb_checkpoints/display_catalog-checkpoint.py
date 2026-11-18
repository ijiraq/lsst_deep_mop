#I'm tired of opening python shells for this
from lsst.daf.butler import Butler
import lsst.afw.display as afwDisplay
import sys
import matplotlib.pyplot as plt

if len(sys.argv) != 2:
    print("Usage: python display_catalog.py <collection/path>")
    sys.exit(1)

butler_dir = "/arc/projects/NewHorizons/HSC_2024/PG2_BUTLER"
collection = sys.argv[1] #input collection to be displayed

butler = Butler(butler_dir, collections=collection, instrument='HSC')
pic = butler.get('injection_catalog',band='r',htm7=183471) #make more customizable or iterative
print('graphing')

ra = pic["ra"]  
dec = pic["dec"]

plt.figure(figsize=(8, 6))
plt.scatter(ra, dec, s=5, alpha=0.5)
plt.xlabel("RA (deg)")
plt.ylabel("Dec (deg)")
plt.title("Injected Sources")
plt.gca().invert_xaxis()
plt.show()

