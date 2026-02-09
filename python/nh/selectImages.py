# Derived from lsst.pipe.tasks.selectImages

__all__ = ["MovingTargetSelectVisitsTask"]

import numpy as np
import lsst.pex.config as pexConfig
import lsst.pipe.base as pipeBase
from lsst.pipe.tasks.selectImages import BestSeeingSelectVisitsConnections
from lsst.pipe.tasks.selectImages import BestSeeingSelectVisitsTask
from lsst.daf.base import DateTime


def _meetsVisitSummaryMinValues(visit, visitSummary, visitSummaryMinValues,
                                logger=None):
    """Check if the visitSummary meets minimum values in visitSummaryMinValues.

    Parameters
    ----------
    visit : `int`
        Visit number.
    visitSummary : `lsst.afw.table.ExposureCatalog`
        Exposure catalog with per-detector summary information.
    visitSummaryMinValues : `dict`
        Dictionary with column names as keys and minimum allowed values as
        values.
    logger : `lsst.log.Logger`
        Logger to log debug and warning messages.

    Returns
    -------
    result : `bool`
        True if all columns in visitSummary meet the minimum values specified
        in visitSummaryMinValues, False otherwise.
    """
    for columnName, minThreshold in visitSummaryMinValues.items():
        # Get values for this column across all detectors with a valid WCS
        values = np.asarray([vs[columnName]
                             for vs in visitSummary if vs.getWcs()])
        meanValue = np.nanmean(values)
        if meanValue < minThreshold:
            if logger is not None:
                logger.info(f'Rejecting visit {visit}: mean {columnName} '
                            f'({meanValue:.3f})'
                            f'is below the minimum threshold '
                            f'({minThreshold:.3f}).')
            return False
    return True


def _extractKeyValue(dataList, keys=None):
    """Extract the keys and values from a list of dataIds.

    The input dataList is a list of objects that have 'dataId' members.
    This allows it to be used for both a list of data references and a
    list of ExposureInfo.

    Parameters
    ----------
    dataList : `Unknown`
    keys : `Unknown`

    Returns
    -------
    keys : `Unknown`
    values : `Unknown`

    Raises
    ------
    RuntimeError
        Raised if DataId keys are inconsistent.
    """
    assert len(dataList) > 0
    if keys is None:
        keys = sorted(dataList[0].dataId.keys())
    keySet = set(keys)
    values = list()
    for data in dataList:
        thisKeys = set(data.dataId.keys())
        if thisKeys != keySet:
            raise RuntimeError((f"DataId keys inconsistent: {keySet}"
                                f" vs {thisKeys}"))
        values.append(tuple(data.dataId[k] for k in keys))
    return keys, values


class MovingTargetSelectVisitsConfig(
     pipeBase.PipelineTaskConfig,
     pipelineConnections=BestSeeingSelectVisitsConnections):
    
    qMin = pexConfig.RangeField(
        doc="Lower bound of quantile range to select."
        " Sorts visits by seeing from narrow to wide, "
        "and select those in the interquantile range (qMin, qMax). "
        "Set qMin to 0 for Best Seeing. "
        "This config should be changed from zero only for exploratory "
        "diffIm testing.",
        dtype=float,
        default=0,
        min=0,
        max=1,
    )
    qMax = pexConfig.RangeField(
        doc="Upper bound of quantile range to select. Sorts visits by seeing from narrow to wide, "
            "and select those in the interquantile range (qMin, qMax). Set qMax to 1 for Worst Seeing.",
        dtype=float,
        default=0.33,
        min=0,
        max=1,
    )
    nVisitsMin = pexConfig.Field(
        doc="The minimum number of visits to select, if qMin and qMax alone would have "
            "selected fewer. In regimes with many visits, at least this number of visits will be "
            "selected, superceding quantile when necessary. "
            "For example, if 10 visits cover this patch, qMin=0, qMax=0.33, and nVisitsMin=5, "
            "the best 5 visits will be selected, even though 5 > 0.33*10. "
            "In regimes with few visits, all available visits will be selected. "
            "For example, if 2 visits cover this patch and nVisitsMin=12, "
            "both visits will be selected regardless of qMin and qMax.",
        dtype=int,
        default=6,
    )
    nGroups = pexConfig.Field(
        doc="The number of time span groups between first and last image in the selected quintile. "
            "The MovingTargetSelectVisit tasks groups the image along the timespan availble  "
            "and selects the best images in each group with a minimum of nVisitsMin per group.",
        dtype=int,
        default=3,
    )
    doConfirmOverlap = pexConfig.Field(
        dtype=bool,
        doc="Do remove visits that do not actually overlap the patch?",
        default=True,
    )
    minMJD = pexConfig.Field(
        dtype=float,
        doc="Minimum visit MJD to select",
        default=None,
        optional=True
    )
    maxMJD = pexConfig.Field(
        dtype=float,
        doc="Maximum visit MJD to select",
        default=None,
        optional=True
    )
    visitSummaryMinValues = pexConfig.DictField(
        keytype=str,
        itemtype=float,
        doc=("Optional thresholds for visit selection. Keys are visit_summary column names"
             "(e.g. 'effTimeZeroPointScale'), and values are minimum allowed values."),
        default=None,
        optional=True
    )


class MovingTargetSelectVisitsTask(BestSeeingSelectVisitsTask):
    """Select a quantile of the best-seeing visits.

    Selects the best (for example, third) full visits based on the average
    PSF width in the entire visit. It can also be used for difference imaging
    experiments that require templates with the worst seeing visits.
    For example, selecting the worst third can be acheived by
    changing the config parameters qMin to 0.66 and qMax to 1.
    """
    ConfigClass = MovingTargetSelectVisitsConfig
    _DefaultName = 'movingTargetSeeingQuantileSelectVisits'

    def run(self, visitSummaries, skyMap, dataId):
        if self.config.doConfirmOverlap:
            patchPolygon = self.makePatchPolygon(skyMap, dataId)
        visits = np.array([visitSummary.ref.dataId['visit']
                           for visitSummary in visitSummaries])
        number_of_visits = len(visits)
        number_of_visits_per_group = number_of_visits/self.config.nGroups
        visits_group = np.floor(np.arange(number_of_visits) /
                                number_of_visits_per_group)
        visits_group = visits_group.astype('int')
        radius = np.empty(number_of_visits)
        intersects = np.full(number_of_visits, True)
        for i, visitSummary in enumerate(visitSummaries):
            # read in one-by-one and only once. There may be hundreds
            visitSummary = visitSummary.get()
            # psfSigma is PSF model determinant radius at chip center in pixels
            psfSigma = np.nanmedian([vs['psfSigma'] for vs in visitSummary])
            radius[i] = psfSigma
            if self.config.doConfirmOverlap:
                intersects[i] = self.doesIntersectPolygon(visitSummary,
                                                          patchPolygon)
            if self.config.minMJD or self.config.maxMJD:
                # mjd is guaranteed to be the same for every detector in the
                # visitSummary.
                mjd = visitSummary[0].getVisitInfo().getDate().get(system=DateTime.MJD)
                aboveMin = mjd > self.config.minMJD if self.config.minMJD else True
                belowMax = mjd < self.config.maxMJD if self.config.maxMJD else True
                intersects[i] = intersects[i] and aboveMin and belowMax
            if (self.config.visitSummaryMinValues
                and not _meetsVisitSummaryMinValues(
                    visits[i], 
                    visitSummary, 
                    self.config.visitSummaryMinValues, 
                    self.log)):
                intersects[i] = False

        goodVisits = []
        for i in range(self.config.nGroups):
            intersects_group = (intersects) & (visits_group == i)
            sortedVisits = [v for rad, v in sorted(
                zip(radius[intersects_group], visits[intersects_group])
                )]
            lowerBound = min(
                int(np.round(self.config.qMin*len(visits[intersects_group]))),
                max(0, len(visits[intersects_group]) - self.config.nVisitsMin))
            upperBound = max(
                int(np.round(self.config.qMax*len(visits[intersects_group]))), 
                self.config.nVisitsMin)
            goodVisits.extend(sortedVisits[lowerBound:upperBound])
        # In order to store as a StructuredDataDict, convert list to dict
        goodVisits = {int(visit): True for visit in goodVisits}
        return pipeBase.Struct(goodVisits=goodVisits)
