#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
@file   __init__.py

@author Till Junge <till.junge@kit.edu>

@date   26 Jan 2015

@brief  Defines all solid mechanics model used in PyCo

@section LICENCE

 Copyright (C) 2015 Till Junge

This project is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License as
published by the Free Software Foundation, either version 3, or (at
your option) any later version.

This project is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
General Public License for more details.

You should have received a copy of the GNU General Public License
along with GNU Emacs; see the file COPYING. If not, write to the
Free Software Foundation, Inc., 59 Temple Place - Suite 330,
Boston, MA 02111-1307, USA.
"""

from .Substrates import Substrate, ElasticSubstrate, PlasticSubstrate
from .FFTElasticHalfSpace import PeriodicFFTElasticHalfSpace
from .FFTElasticHalfSpace import FreeFFTElasticHalfSpace
