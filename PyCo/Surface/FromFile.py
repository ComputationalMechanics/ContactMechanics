#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
@file   FromFile.py

@author Till Junge <till.junge@kit.edu>

@date   26 Jan 2015

@brief  Surface profile from file input

@section LICENCE

 Copyright (C) 2015 Till Junge

PyCo is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License as
published by the Free Software Foundation, either version 3, or (at
your option) any later version.

PyCo is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
General Public License for more details.

You should have received a copy of the GNU General Public License
along with GNU Emacs; see the file COPYING. If not, write to the
Free Software Foundation, Inc., 59 Temple Place - Suite 330,
Boston, MA 02111-1307, USA.
"""

import os
import re

import numpy as np

from .SurfaceDescription import NumpySurface


def read_matrix(fobj, size=None, factor=1.):
    """
    Reads a surface profile from a text file and presents in in a
    Surface-conformant manner. No additional parsing of meta-information is
    carried out.

    Keyword Arguments:
    fobj -- filename or file object
    """
    if not hasattr(fobj, 'read'):
        if not os.path.isfile(fobj):
            zfobj = fobj + ".gz"
            if os.path.isfile(zfobj):
                fobj = zfobj
            else:
                raise FileNotFoundError(
                    "No such file or directory: '{}(.gz)'".format(
                        fobj))
    return NumpySurface(factor*np.loadtxt(fobj), size=size)

NumpyTxtSurface = read_matrix  # pylint: disable=invalid-name


def read_asc(fobj, unit='m', x_factor=1.0, z_factor=1.0):
    # pylint: disable=too-many-branches,too-many-statements,invalid-name
    """
    Reads a surface profile from an generic asc file and presents it in a
    surface-conformant manner. Applies some heuristic to extract
    meta-information for different file formats. All units of the returned
    surface are in meters.

    Keyword Arguments:
    fobj -- filename or file object
    unit -- name of surface units, one of m, mm, μm/um, nm, A
    x_factor -- multiplication factor for size
    z_factor -- multiplication factor for height
    """
    _units = {'m': 1.0, 'mm': 1e-3, 'μm': 1e-6, 'um': 1e-6, 'nm': 1e-9,
              'A': 1e-10}

    if not hasattr(fobj, 'read'):
        if not os.path.isfile(fobj):
            raise FileNotFoundError(
                "No such file or directory: '{}(.gz)'".format(
                    fobj))
        fname = fobj
        fobj = open(fname)

    _float_regex = r'[-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?'

    checks = list()
    # Resolution keywords
    checks.append((re.compile(r"\b(?:x-pixels|h)\b\s*=\s*([0-9]+)"), int,
                   "xres"))
    checks.append((re.compile(r"\b(?:y-pixels|w)\b\s*=\s*([0-9]+)"), int,
                   "yres"))

    # Size keywords
    checks.append((re.compile(r"\b(?:x-length)\b\s*=\s*("+_float_regex+")"),
                   float, "xsiz"))
    checks.append((re.compile(r"\b(?:y-length)\b\s*=\s*("+_float_regex+")"),
                   float, "ysiz"))

    # Unit keywords
    checks.append((re.compile(r"\b(?:x-unit)\b\s*=\s*(\w+)"), str, "xunit"))
    checks.append((re.compile(r"\b(?:y-unit)\b\s*=\s*(\w+)"), str, "yunit"))
    checks.append((re.compile(r"\b(?:z-unit)\b\s*=\s*(\w+)"), str, "zunit"))

    # Scale factor keywords
    checks.append((re.compile(r"(?:pixel\s+size)\s*=\s*("+_float_regex+")"),
                   float, "xfac"))
    checks.append((re.compile(
        (r"(?:height\s+conversion\s+factor\s+\(->\s+m\))\s*=\s*(" +
         _float_regex+")")),
                   float, "zfac"))

    xres = yres = xsiz = ysiz = xunit = yunit = zunit = xfac = yfac = None
    zfac = None

    def process_comment(line):
        "Find and interpret known comments in the header of the asc file"
        def check(line, reg, fun):
            "Check whether line fits a known comment syntax"
            match = reg.search(line)
            if match is not None:
                return fun(match.group(1))
            return None
        nonlocal xres, yres, xsiz, ysiz, xunit, yunit, zunit, data, xfac, yfac
        nonlocal zfac
        matches = {key: check(line, reg, fun)
                   for (reg, fun, key) in checks}
        if matches['xres'] is not None:
            xres = matches['xres']
        if matches['yres'] is not None:
            yres = matches['yres']
        if matches['xsiz'] is not None:
            xsiz = matches['xsiz']
        if matches['ysiz'] is not None:
            ysiz = matches['ysiz']
        if matches['xunit'] is not None:
            xunit = matches['xunit']
        if matches['yunit'] is not None:
            yunit = matches['yunit']
        if matches['zunit'] is not None:
            zunit = matches['zunit']
        if matches['xfac'] is not None:
            xfac = matches['xfac']
        if matches['zfac'] is not None:
            zfac = matches['zfac']

    data = []
    with fobj as file_handle:
        for line in file_handle:
            line_elements = line.strip().split()
            if len(line) > 0:
                try:
                    dummy = float(line_elements[0])
                    data += [[float(strval) for strval in line_elements]]
                except ValueError:
                    process_comment(line)
    data = np.array(data)
    nx, ny = data.shape
    if xres is not None and xres != nx:
        raise Exception(
            "The number of rows (={}) read from the file '{}' does "
            "not match the resolution in the file's metadata (={})."
            .format(nx, fname, xres))
    if yres is not None and yres != ny:
        raise Exception("The number of columns (={}) read from the file '{}' "
                        "does not match the resolution in the file's metadata "
                        "(={}).".format(ny, fname, yres))

    # Handle scale factors
    if xfac is not None and yfac is None:
        yfac = xfac
    elif xfac is None and yfac is not None:
        xfac = yfac
    if xfac is not None:
        if xsiz is None:
            xsiz = xfac*nx
        else:
            xsiz *= xfac
    if yfac is not None:
        if ysiz is None:
            ysiz = yfac*ny
        else:
            ysiz *= yfac
    if zfac is not None:
        data *= zfac

    # Handle units -> convert to target unit
    if xunit is None and zunit is not None:
        xunit = zunit
    if yunit is None and zunit is not None:
        yunit = zunit

    if xunit is not None:
        xsiz *= _units[xunit]/_units[unit]
    if yunit is not None:
        ysiz *= _units[yunit]/_units[unit]
    if zunit is not None:
        data *= _units[zunit]/_units[unit]

    if xsiz is None or ysiz is None:
        return NumpySurface(z_factor*data)
    else:
        return NumpySurface(z_factor*data, size=(x_factor*xsiz, x_factor*ysiz))

NumpyAscSurface = read_asc  # pylint: disable=invalid-name


def read_xyz(fn):
    """
    Load xyz-file
    TODO: LARS_DOC
    Keyword Arguments:
    fn -- filename
    """
    # pylint: disable=invalid-name
    x, y, z = np.loadtxt(fn, unpack=True)  # pylint: disable=invalid-name

    # Sort x-values into bins. Assume points on surface are equally spaced.
    dx = x[1]-x[0]
    binx = np.array(x/dx+0.5, dtype=int)
    n = np.bincount(binx)
    ny = n[0]
    assert np.all(n == ny)

    # Sort y-values into bins.
    dy = y[binx == 0][1]-y[binx == 0][0]
    biny = np.array(y/dy+0.5, dtype=int)
    n = np.bincount(biny)
    nx = n[0]
    assert np.all(n == nx)

    # Sort data into bins.
    data = np.zeros((nx, ny))
    data[binx, biny] = z

    # Sanity check. Should be covered by above asserts.
    value_present = np.zeros((nx, ny), dtype=bool)
    value_present[binx, biny] = True
    assert np.all(value_present)

    return NumpySurface(data, size=(dx*nx, dy*ny))