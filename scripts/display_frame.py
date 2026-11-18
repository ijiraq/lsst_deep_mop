#I'm tired of opening python shells for this
from lsst.daf.butler import Butler
import lsst.afw.display as afwDisplay
import sys
import matplotlib.pyplot as plt

display = afwDisplay.getDisplay()

if len(sys.argv) != 6:
    print("Usage: python display_calib.py <frame_type> <collection/path> <detector> <extra_option> <on/off>")
    print("frame type can be bias, flat, raw, injected_calexp or subtraction")
    print("The extra is nothing for bias, type whatever. For flat, it is the filter of interest (e.g. HSC-R2). For raw, injected_calexp or subtraction it is the exposure/visit number you want to look at.")
    print("Mask details print out when 'on' is passed.")
    sys.exit(1)

butler_dir = "/arc/projects/NewHorizons/HSC_2024/PG2_BUTLER"
frame_type = sys.argv[1]
collection = sys.argv[2] #input collection to be displayed
det = int(sys.argv[3])
extra = sys.argv[4] #extra option, varies with frame type
flag = sys.argv[5]

if frame_type=='raw' or frame_type=='injected_calexp':
    extra = int(extra)

butler = Butler(butler_dir, collections=collection, instrument='HSC')

if frame_type=='bias':
    pic = butler.get(frame_type,detector=det)
elif frame_type=='flat':
    pic = butler.get(frame_type,detector=det,physical_filter=extra) 
elif frame_type=='raw':
    pic = butler.get(frame_type,detector=det,exposure=extra)
elif frame_type=='injected_calexp':
    pic = butler.get(frame_type,detector=det,visit=extra)
elif frame_type=='subtraction':
    pic = butler.get("injected_goodSeeingDiff_differenceTempExp",detector=det,visit=f"HSCE00{extra}")
print('graphing')

display.image(pic)

if flag=='on':
    mask = pic.getMask()
    for maskName, maskBit in mask.getMaskPlaneDict().items():
        print('{}: {}'.format(maskName, display.getMaskPlaneColor(maskName)))