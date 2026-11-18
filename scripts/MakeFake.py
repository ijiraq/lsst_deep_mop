#!/usr/bin/env python
# coding: utf-8

# In[1]:


import rebound
from astropy.time import Time
from astropy import units
from astropy.units import Quantity
from astropy.coordinates import SkyCoord, GCRS
from astropy.coordinates import EarthLocation
from astropy.coordinates import solar_system_ephemeris
from astropy.io import fits
from astropy.wcs import WCS
from astropy.table import Table, vstack
import numpy as np
from matplotlib import pyplot as plt
from matplotlib.patches import Polygon
import sys
import os

random_seed = 123456789
rng = np.random.default_rng(seed=random_seed)

DEFAULT_LIMITS = [ 
            {'a': (30, 50), 
             'e':  (0, 0.9),
             'inc': (0, np.pi),
            },
            {'a': (50, 100), 
             'e':  (0, 0.9),
             'inc': (0, np.pi),
            },
            {'a': (100, 250), 
             'e':  (0, 0.9),
             'inc': (0, np.pi),
            }]
EXAMPLE_IMAGE="/arc/projects/NewHorizons/HSC_2024/BUTLER/u/NH/processCCD/run1/calexp/20240731/gri/EB-GRI/332136/calexp_HSC_gri_EB-GRI_332136_1_53_u_NH_processCCD_run1.fits"


def app_mag(r, delta, robs, h, g=-0.12):
    """Compute the apparent magnitude given the observing circumstances and h

    Args:
        r (float): Sun-object distance
        delta (float): Observer-object distance
        robs (float): Sun-Observer distance
        h (float): absolute magnitude
        
    """
    denom = 2*r*delta
    cos_alpha = (-robs**2 + delta**2 + r**2)/denom
    cos_alpha[cos_alpha>1] = 1
    alpha = np.arccos(cos_alpha)
    phi1 = np.exp(-3.33*(np.tan(alpha/2.0))**0.63)
    phi2 = np.exp(-1.87*(np.tan(alpha/2.0))**1.22)
    mag = 5.0*np.log10(r*delta) + h - 2.5*np.log10((1.0 - g)*phi1 + g*phi2)
    return mag

def pos_cart(a: np.array, e: np.array, 
             inc: np.array, Omega: np.array, 
             omega: np.array, M: np.array) -> np.array:
    """
    This routine transforms delaunay variables into cartesian variables, positions only.

    Parameters
    a: semi-major axis (AU)
    e: eccentricity
    inc: inclination (radians)
    Omega: longitude of the ascending node (radians)
    omega: argument of the pericentre (radians)
    M: mean anomaly (radians)

    """
    M = M % (2 * np.pi)
    signe = np.sign(a)
    cos_i = np.cos(inc)
    sin_i = np.sqrt(1 - cos_i ** 2)
    delau1 = M
    delau2 = np.cos(omega)
    delau3 = np.sin(omega)
    delau4 = np.cos(Omega)
    delau5 = np.sin(Omega)
    delau6 = signe * np.sqrt(a * signe)
    delau7 = np.abs(delau6) * np.sqrt((1 - e ** 2) * signe)

    E = compute_E(e, M)

    cos_E = np.cos(E)
    sin_E = np.sin(E)
    q_vec = np.zeros_like(cos_E, shape=(2, cos_E.shape[0]))
    q_vec[0,:] = (cos_E - e) * (delau6**2)
    q_vec[1,:] = delau7 * delau6 * sin_E

    mat = np.zeros_like(cos_i, shape=(3, 2, cos_i.shape[0]))
    d53 = delau5 * delau3
    d42 = delau4 * delau2
    d52 = delau5 * delau2
    d43 = delau4 * delau3
    mat[0, 0, :] = d42 - cos_i * d53
    mat[0, 1, :] = -d43 - cos_i * d52
    mat[1, 0, :] = d52 + cos_i * d43
    mat[1, 1, :] = -d53 + cos_i * d42
    mat[2, 0, :] = sin_i * delau3
    mat[2, 1, :] = sin_i * delau2

    # Cartesian coordinates
    p = (mat * q_vec).sum(axis=1)
    # p = np.zeros(3)
    # p[0] = mat[0, 0] * q_vec[0] + mat[0, 1] * q_vec[1]
    # p[1] = mat[1, 0] * q_vec[0] + mat[1, 1] * q_vec[1]
    # p[2] = mat[2, 0] * q_vec[0] + mat[2, 1] * q_vec[1]

    return p


def compute_E(e: np.array, M: np.array) -> np.array:
    """
    Compute the eccentric anomaly E from the mean anomaly M and the eccentricity e.

    """
    E = M + 0.85 * np.sign(np.sin(M)) * e
    i = 0
    while True:
        sin_e = e * np.sin(E)
        f = E - sin_e - M
        iterate = np.fabs(f) > 1e-14
        if iterate.sum() > 0:
            cos_e = e[iterate] * np.cos(E[iterate])
            fp = 1 - cos_e
            fpp = sin_e[iterate]
            fppp = cos_e
            de = -f[iterate] / fp
            de = -f[iterate] / (fp + de * fpp / 2)
            de = -f[iterate] / (fp + de * fpp / 2 + de * de * fppp / 6)
            E[iterate] = E[iterate] + de
            i += 1
            if i < 20:
                continue
            raise ValueError('POS_CART: No convergence after {i} iterations')
        break
    return E


def get_field_wcs(ra: Quantity = 287.0*units.degree,
                  dec: Quantity = -20.8*units.degree,
                  width=10*units.degree,
                  height=10*units.degree) -> WCS:
    """
    returns a WCS object that represents the a field of width x height centred on the RA/DEC given
    """
    
    cd11 = cd22 = 1.0*units.arcsec
    fov_wcs = {
        'CD1_1': cd11.to('degree').value,
        'CD2_2': cd22.to('degree').value,
        'CD1_2': 0.0,
        'CD2_1': 0.0,
        'NAXIS': 2,
        'NAXIS1': int(width/cd11),
        'NAXIS2': int(height/cd22),
        'CTYPE1': "RA---TAN",
        'CTYPE2': "DEC--TAN",
        'CRVAL1': field_centre.ra.degree,
        'CRVAL2': field_centre.dec.degree,
        'CRPIX1': int(width/cd11/2),
        'CRPIX2': int(height/cd22/2),
        'RADESYS': "ICRS",
    }
    
    return WCS(fov_wcs)


def generate_orbit_distribution(number_of_orbits_to_generate:int, 
                                limit_sets: list=DEFAULT_LIMITS) -> Table:
    """
    generate a sets of orbital elements based on ranges set in limits, 
    see DEFAULT_LIMITS for the format of the limits parameter.
    """


    # build Table of orbit randomly selected from within the limits.

    particles = {}
    for limits in limit_sets:
        for element in ['a', 'e', 'inc', 'Omega', 'omega', 'M']:
            if element not in particles:
                particles[element] = []
            min, max = limits.get(element, (0, 2*np.pi))
            particles[element].extend(rng.uniform(min, max, number_of_orbits_to_generate))

    # set a range of magnitudes
    mags = []
    mags.extend(rng.uniform(21, 24, number_of_orbits_to_generate))
    mags.extend(rng.uniform(24, 26, number_of_orbits_to_generate))
    mags.extend(rng.uniform(26, 28, number_of_orbits_to_generate))
    particles['mag'] = np.array(mags)

    orbits = Table(particles)
    # orbits.meta['obstime'] = Time('J2000')

    return orbits

def get_particle_coordinates(orbits) -> Table:
    """
    Given a set of keplarian orbital elements with M propogated to the desired epoch 
    provide the RA/Dec/Distance/Delta of those orbits as they would appear in the given image_wcs
    """
    xyz = pos_cart(**orbits['a','e','inc','Omega','omega','M'])
    
    coords = SkyCoord(x=xyz[0], y=xyz[1], z=xyz[2],
         unit='au', obstime=orbits.meta['obstime'], 
         frame='heliocentrictrueecliptic', 
         representation_type='cartesian')
    return coords

def propogate_orbits(orbits, obstime) -> Table:
    """
    Propogate the given table of orbits from orbit.meta['epoch'] to 'obstime'
    """
    delta_time = obstime - orbits.meta['obstime']
    
    orbits['M'] = orbits['M'] + delta_time * 2*np.pi/(orbits['a']**(3/2)*units.year)
    orbits.meta['obstime'] = obstime
    return orbits

def get_reference_frame(telescope: str, obstime: Time) -> GCRS:
    """
    Provides an astropy.coordinates reference_frame of the observer
    """
    location = EarthLocation.of_site(telescope)
    obsgeoloc, obsgeovel = location.get_gcrs_posvel(obstime)
    with solar_system_ephemeris.set('builtin'):
        reference_frame = GCRS(obstime=obstime, 
                               obsgeoloc=obsgeoloc, 
                               obsgeovel=obsgeovel)
    return reference_frame

def generate_master_orbit_table(fov_wcs, number_of_sources):
    """
    Generate a list of orbits from a random sample set by the default seed
    and then select out those that are at least 'near' the location of sky 
    pointed to by NH search

    """
    orbits = generate_orbit_distribution(number_of_sources)
    orbits.meta['obstime'] = reference_frame.obstime
    coords = get_particle_coordinates(orbits)
    orbits['r'] = np.sqrt(coords.x*coords.x + coords.y*coords.y + coords.z*coords.z)
    coords = coords.transform_to('icrs')
    orbits['RA2000'] = coords.ra.to('degree')
    orbits['DEC2000'] = coords.dec.to('degree')
    x, y = fov_wcs.wcs_world2pix(orbits['RA2000'], orbits['DEC2000'], 0)
    source_in_field = (x>0) & (x<fov_wcs._naxis[0]) & (y>0) & (y<fov_wcs._naxis[1])
    coords = coords.transform_to('icrs')
    orbits['delta'] = coords.distance.to('au')
    dmag = app_mag(orbits['r'], orbits['delta'], 1, 0)
    orbits['H'] = orbits['mag'] - dmag
    
    return orbits[source_in_field]

def get_image_wcs(image_filename):
    with fits.open(image_filename) as hdulist:
        return WCS(hdulist[1].header)

    
def generate_injection_table(orbits, reference_frame):
    orbits = propogate_orbits(orbits, reference_frame.obstime)
    coords = get_particle_coordinates(orbits)
    orbits['r'] = np.sqrt(coords.x*coords.x + coords.y*coords.y + coords.z*coords.z)
    coords = coords.transform_to(reference_frame)
    # x, y = image_wcs.wcs_world2pix(orbits['RA2000'], orbits['DEC2000'], 0)
    # source_in_field = (x>0) & (x<image_wcs._naxis[0]) & (y>0) & (y<image_wcs._naxis[1])
    orbits['delta'] = coords.distance.to('au')
    orbits['RA2000'] = coords.ra.to('degree')
    orbits['DEC2000'] = coords.dec.to('degree')
    orbits['mag'] = app_mag(orbits['r'],
                            orbits['delta'],
                            1,
                            orbits['H'])
    orbits.meta['obstime'] = reference_frame.obstime
    # coords = coords[selected_sources]
    # orbits = orbits[selected_sources]
    return orbits



def generate_visit_orbit_table(orbits, reference_frame, image_wcs):
    """Given a set of 'orbits' (see generate_master_orbit_table
    for a routine to create the master orbit Table which is then 
    saved to disk) we propogate to the time of this image
    and select those that might be on the FOV of the image.

    Expects data that has been through the LSST Science Pipeline"""

    orbits = propogate_orbits(orbits, reference_frame.obstime)
    coords = get_particle_coordinates(orbits)
    orbits['r'] = np.sqrt(coords.x*coords.x + coords.y*coords.y + coords.z*coords.z)
    coords = coords.transform_to(reference_frame)
    x, y = image_wcs.wcs_world2pix(orbits['RA2000'], orbits['DEC2000'], 0)
    source_in_field = (x>0) & (x<image_wcs._naxis[0]) & (y>0) & (y<image_wcs._naxis[1])
    orbits['delta'] = coords.distance.to('au')
    orbits['RA2000'] = coords.ra.to('degree')
    orbits['DEC2000'] = coords.dec.to('degree')
    orbits['mag'] = app_mag(orbits['r'],
                            orbits['delta'],
                            1,
                            orbits['H'])
    orbits.meta['obstime'] = reference_frame.obstime
    # coords = coords[selected_sources]
    # orbits = orbits[selected_sources]
    return orbits[source_in_field]

def make_sky_plot(orbits, reference_frame, footprint=None):
    orbits = propogate_orbits(orbits, reference_frame.obstime)
    coords = get_particle_coordinates(orbits).transform_to(reference_frame)
    fig = plt.figure()
    ax = fig.add_subplot()
    ax.plot(coords.ra.degree, coords.dec.degree, '.')
    if footprint is not None:
        ax.add_patch(Polygon(footprint, facecolor='k', alpha=0.1))
    # ax.set_xlim(centre.ra.degree+10,centre.ra.degree-10)
    # ax.set_ylim(centre.dec.degree-10, centre.dec.degree+10)
    ax.set_xlabel('RA')
    ax.set_ylabel('DEC')

if __name__ == '__main__':
    for i in range(10):
        fov_wcs = get_field_wcs()
        orbits = generate_master_orbit_table(fov_wcs, 5000000)
        orbits.write(f'NH_makefake_orbits_{i}.parquet', overwrite=True)
