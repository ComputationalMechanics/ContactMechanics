#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
@file   PlasticSystemSpecialisations.py

@author Lars Pastewka <lars.pastewka@kit.edu>

@date   30 Jan 2017

@brief  implements plastic mapping algorithms for contact systems

@section LICENCE

 Copyright (C) 2017 Lars Pastewka

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

import numpy as np

from .. import ContactMechanics, SolidMechanics, Surface
from .Systems import NonSmoothContactSystem

class PlasticNonSmoothContactSystem(NonSmoothContactSystem):
    """
    This system implements a simple penetration hardness model.
    """

    @staticmethod
    def handles(substrate_type, interaction_type, surface_type):
        """
        determines whether this class can handle the proposed system
        composition
        Keyword Arguments:
        substrate_type   -- instance of ElasticSubstrate subclass
        interaction_type -- instance of Interaction
        surface_type     --
        """
        is_ok = True
        # any type of substrate formulation should do
        is_ok &= issubclass(substrate_type,
                            SolidMechanics.ElasticSubstrate)
        # only hard interactions allowed
        is_ok &= issubclass(interaction_type,
                            ContactMechanics.HardWall)

        # any surface should do
        is_ok &= issubclass(surface_type,
                            Surface.PlasticSurface)
        return is_ok

    def minimize_proxy(self, pltol=1e-5, logger=None, **kwargs):
        """
        """
        u_r = None
        maxdpl = pltol+1.0
        while maxdpl > pltol:
            result = super().minimize_proxy(disp0=u_r, logger=logger, **kwargs)
            p_r = result.jac
            mask = p_r > self.surface.hardness

            # Evaluate displacements with pressure distribution cut-off by
            # hardness
            p_r[mask] = self.surface.hardness
            u_r = self.substrate.evaluate_disp(-p_r)

            # Get undeformed profile and check where it penetrates the surface
            h_r = self.surface._profile()
            mask = np.logical_and(mask, h_r > u_r)

            # Compute new plastic displacement
            plastic_displ = self.surface.undeformed_profile()[mask] - u_r[mask]
            maxdpl = abs(plastic_displ - self.surface.plastic_displ[mask]).max()
            if logger is not None:
                logger.pr('Max. difference in plastic displacement = {}'.format(maxdpl))

            # Set offset (for calculation at external pressure) and plastic
            # displacement
            kwargs['offset'] = result.offset
            self.surface.plastic_displ[mask] = plastic_displ

        return result