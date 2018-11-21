#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
@file   FFTElasticHalfSpace.py

@author Till Junge <till.junge@kit.edu>

@date   26 Jan 2015

@brief  Implement the FFT-based elasticity solver of pycontact

@section LICENCE

Copyright 2015-2017 Till Junge, Lars Pastewka

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

from collections import namedtuple
import numpy as np
import sys
#from ..Tools.fftext import rfftn, irfftn


from .Substrates import ElasticSubstrate

# Decide what is default FFTEngine:
try:
    from mpi4py import MPI
    _with_MPI = MPI.COMM_WORLD.Get_size() > 1
except:
    _with_MPI = False #TODO: This maybe uselesss

# I will never take the parallel as default because most of the tests will fail because of this

if 'darwin' in sys.platform:
    # print("FFTWEngine causes failure on darwin, will not be tested")
    from FFTEngine import NumpyFFTEngine
    DEFAULTENGINE = NumpyFFTEngine
else:
    from FFTEngine import FFTWEngine
    DEFAULTENGINE = FFTWEngine

class PeriodicFFTElasticHalfSpace(ElasticSubstrate):
    """ Uses the FFT to solve the displacements and stresses in an elastic
        Halfspace due to a given array of point forces. This halfspace
        implementation cheats somewhat: since a net pressure would result in
        infinite displacement, the first term of the FFT is systematically
        dropped.
        The implementation follows the description in Stanley & Kato J. Tribol.
        119(3), 481-485 (Jul 01, 1997)
    """
    # pylint: disable=too-many-instance-attributes

    name = "periodic_fft_elastic_halfspace"
    _periodic = True

    def __init__(self, resolution, young, size=2*np.pi, stiffness_q0=None,
                 thickness=None, poisson=0.0, superclass=True, fftengine=None, pnp = np):
        """
        Keyword Arguments:
        resolution   -- Tuple containing number of points in spatial directions.
                        The length of the tuple determines the spatial dimension
                        of the problem.
        young        -- Young's modulus
        size         -- (default 2π) domain size. For multidimensional problems,
                        a tuple can be provided to specify the lenths per
                        dimension. If the tuple has less entries than dimensions,
                        the last value in repeated.
        stiffness_q0 -- Substrate stiffness at the Gamma-point (wavevector q=0).
                        If None, this is taken equal to the lowest nonvanishing
                        stiffness. Cannot be used in combination with height.
        thickness    -- Thickness of the elastic half-space. If None, this
                        models an infinitely deep half-space. Cannot be used in
                        combination with stiffness_q0.
        poisson      -- Poisson number. Need only be specified for substrates
                        of finite thickness. If left unspecified for substrates
                        of infinite thickness, then young is the contact
                        modulus.
        superclass   -- (default True) client software never uses this. Only
                        inheriting subclasses use this.
        """
        super().__init__()
        if not hasattr(resolution, "__iter__"):
            resolution = (resolution, )
        if not hasattr(size, "__iter__"):
            size = (size, )
        self.__dim = len(resolution)
        if self.dim not in (1, 2):
            raise self.Error(
                ("Dimension of this problem is {}. Only 1 and 2-dimensional "
                 "problems are supported").format(self.dim))
        if stiffness_q0 is not None and thickness is not None:
            raise self.Error("Please specify either stiffness_q0 or thickness "
                             "or neither.")
        self.resolution = resolution
        tmpsize = list()
        for i in range(self.dim):
            tmpsize.append(size[min(i, len(size)-1)])
        self.size = tuple(tmpsize)
        self.nb_pts = np.prod(self.resolution)
        self.area_per_pt = np.prod(self.size)/self.nb_pts
        try:
            self.steps = tuple(
                float(size)/res for size, res in
                zip(self.size, self.resolution))
        except ZeroDivisionError as err:
            raise ZeroDivisionError(
                ("{}, when trying to handle "
                 "    self.steps = tuple("
                 "        float(size)/res for size, res in"
                 "        zip(self.size, self.resolution))"
                 "Parameters: self.size = {}, self.resolution = {}"
                 "").format(err, self.size, self.resolution))
        self.young = young
        self.poisson = poisson
        self.contact_modulus = young/(1-poisson**2)
        self.stiffness_q0 = stiffness_q0
        self.thickness = thickness

        if fftengine is not None:
            self.fftengine = fftengine
        else:
            self.fftengine = DEFAULTENGINE(self.domain_resolution)

        self.pnp = pnp

        #self.fftengine = fftengine(self.domain_resolution)  # because when called in subclass,
                                                            # the computational resolution isn't known already
        if superclass:
            self._compute_fourier_coeffs()
            self._compute_i_fourier_coeffs()


    @property
    def dim(self, ):
        "return the substrate's physical dimension"
        return self.__dim

    @property
    def domain_resolution(self, ):
        """
        usually, the resolution of the system is equal to the geometric
        resolution (of the surface). For example free boundary conditions,
        require the computational resolution to differ from the geometric one,
        see FreeFFTElasticHalfSpace.
        """
        return self.resolution

    @property
    def subdomain_resolution(self):
        """
        When working in Parallel one processor holds only Part of the Data

        :return:
        """
        return self.fftengine.subdomain_resolution

    @property
    def subdomain_location(self):
        """
        When working in Parallel one processor holds only Part of the Data

        :return:
        """
        return self.fftengine.subdomain_location

    @property
    def subdomain_slice(self):
        """
        When working in Parallel one processor holds only Part of the Data

        :return:
        """
        return self.fftengine.subdomain_slice

    @property
    def fourier_resolution(self):
        """
        When working in Parallel one processor holds only Part of the Data

        :return:
        """
        return self.fftengine.fourier_resolution

    @property
    def fourier_location(self):
        """
        When working in Parallel one processor holds only Part of the Data

        :return:
        """
        return self.fftengine.fourier_location

    @property
    def fourier_slice(self):
        """
        When working in Parallel one processor holds only Part of the Data

        :return:
        """
        return self.fftengine.fourier_slice


    def __repr__(self):
        dims = 'x', 'y', 'z'
        size_str = ', '.join('{}: {}({})'.format(dim, size, resolution) for
                             dim, size, resolution in zip(dims, self.size,
                                                          self.resolution))
        return ("{0.dim}-dimensional halfspace '{0.name}', size(resolution) in"
                " {1}, E' = {0.young}").format(self, size_str)

    def _compute_fourier_coeffs(self):
        """
        Compute the weights w relating fft(displacement) to fft(pressure):
        fft(u) = w*fft(p), see (6) Stanley & Kato J. Tribol. 119(3), 481-485
        (Jul 01, 1997).
        WARNING: the paper is dimensionally *incorrect*. see for the correct
        1D formulation: Section 13.2 in
            K. L. Johnson. (1985). Contact Mechanics. [Online]. Cambridge:
            Cambridge  University Press. Available from: Cambridge Books Online
            <http://dx.doi.org/10.1017/CBO9781139171731> [Accessed 16 February
            2015]
        for correct 2D formulation: Appendix 1, eq A.2 in
            Johnson, Greenwood and Higginson, "The Contact of Elastic Regular
            Wavy surfaces", Int. J. Mech. Sci. Vol. 27 No. 6, pp. 383-396, 1985
            <http://dx.doi.org/10.1016/0020-7403(85)90029-3> [Accessed 18 March
            2015]
        """
        if self.dim == 1:
            facts = np.zeros(self.fourier_resolution)
            for index in range(self.fourier_location[0]+2, self.fourier_resolution[0]+1):
                 facts[index - 1] = \
                    self.size[0]/(self.contact_modulus*index*np.pi)
            self.weights= facts
        elif self.dim == 2:  # TODO: compute facts only on the fourier slice
            nx, ny = self.resolution
            sx, sy = self.size
            # Note: q-values from 0 to 1, not from 0 to 2*pi
            qx = np.arange(nx, dtype=np.float64)
            qx = np.where(qx <= nx//2, qx/sx, (nx-qx)/sx)
            qy = np.arange(ny, dtype=np.float64)
            qy = np.where(qy <= ny//2, qy/sy, (ny-qy)/sy)
            q = np.sqrt((qx*qx).reshape(-1, 1) + (qy*qy).reshape(1, -1))
            q[0,0] = np.NaN; #q[0,0] has no Impact on the end result, but q[0,0] =  0 produces runtime Warnings (because corr[0,0]=inf)
            facts = np.pi*self.contact_modulus*q
            if self.thickness is not None: #TODO: parallel test for this case
                # Compute correction for finite thickness
                q *= 2*np.pi*self.thickness
                fac = 3 - 4*self.poisson
                off = 4*self.poisson*(2*self.poisson - 3) + 5
                with np.errstate(over="ignore",invalid="ignore",divide="ignore"):
                    corr = (fac*np.cosh(2*q) + 2*q**2 + off)/ \
                        (fac*np.sinh(2*q) - 2*q)
                # The expression easily overflows numerically. These are then
                # q-values that are converged to the infinite system expression.
                corr[np.isnan(corr)] = 1.0
                facts *= corr
                facts[0, 0] = self.young/self.thickness * \
                    (1 - self.poisson)/((1 - 2*self.poisson)*(1 + self.poisson))
            else:
                if self.stiffness_q0 is None:
                    facts[0, 0] = (facts[1, 0].real + facts[0, 1].real)/2
                elif self.stiffness_q0 == 0.0:
                    facts[0, 0] = 1.0
                else:
                    facts[0, 0] = self.stiffness_q0

            self.weights = 1/facts[self.fourier_slice]

            if self.stiffness_q0 == 0.0:
                self.weights[0, 0] = 0.0

    def _compute_i_fourier_coeffs(self):
        """Invert the weights w relating fft(displacement) to fft(pressure):
        """
        self.iweights = np.zeros_like(self.weights)
        self.iweights[self.weights != 0] = 1./self.weights[self.weights != 0]

    def evaluate_disp(self, forces):
        """ Computes the displacement due to a given force array
        Keyword Arguments:
        forces   -- a numpy array containing point forces (*not* pressures)
        """
        if forces.shape != self.subdomain_resolution:
            raise self.Error(
                ("force array has a different shape ({0}) than this halfspace'"
                 "s resolution ({1})").format(
                     forces.shape, self.subdomain_resolution))  # nopep8
        return self.fftengine.irfftn(self.weights * self.fftengine.rfftn(-forces)).real / self.area_per_pt

    def evaluate_force(self, disp):
        """ Computes the force (*not* pressures) due to a given displacement array
        Keyword Arguments:
        disp   -- a numpy array containing point displacements
        """
        if disp.shape != self.subdomain_resolution:
            raise self.Error(
                ("displacements array has a different shape ({0}) than this "
                 "halfspace's resolution ({1})").format(
                     disp.shape, self.subdomain_resolution))  # nopep8
        return -self.fftengine.irfftn(self.iweights * self.fftengine.rfftn(disp)).real * self.area_per_pt

    def evaluate_k_disp(self, forces):
        """ Computes the K-space displacement due to a given force array
        Keyword Arguments:
        forces   -- a numpy array containing point forces (*not* pressures)
        """
        if forces.shape != self.subdomain_resolution:
            raise self.Error(
                ("force array has a different shape ({0}) than this halfspace'"
                 "s resolution ({1})").format(
                     forces.shape, self.subdomain_resolution))  # nopep8
        return self.weights * self.fftengine.rfftn(-forces)/self.area_per_pt

    def evaluate_k_force(self, disp):
        """ Computes the K-space forces (*not* pressures) due to a given displacement array
        Keyword Arguments:
        disp   -- a numpy array containing point displacements
        """
        if disp.shape != self.subdomain_resolution:
            raise self.Error(
                ("displacements array has a different shape ({0}) than this "
                 "halfspace's resolution ({1})").format(
                     disp.shape, self.subdomain_resolution))  # nopep8
        return -self.iweights*self.fftengine.rfftn(disp)*self.area_per_pt

    def evaluate_elastic_energy(self, forces, disp):
        """
        computes and returns the elastic energy due to forces and displacements
        Arguments:
        forces -- array of forces
        disp   -- array of displacements
        """
        # pylint: disable=no-self-use
        return .5*np.dot(np.ravel(disp), np.ravel(-forces))

    def evaluate_elastic_energy_k_space(self, kforces, kdisp):
        """
        computes and returns the elastic energy due to forces and displacement
        in Fourier space
        Arguments:
        forces -- array of forces
        disp   -- array of displacements
        """
        # pylint: disable=no-self-use
        # using vdot instead of dot because of conjugate
        # The 2nd term at the end comes from the fact that we use a reduced
        # rfft transform

        # This will not work in parallel, because not all Processors pocess the line of data that should not be symetrized
        #return .5*(np.vdot(kdisp, -kforces).real +
        #           np.vdot(kdisp[..., 1:-1], -kforces[..., 1:-1]).real)/self.nb_pts

        # Now compatible with parallel code
        # The inner part of the fourier data should always be symetrized (i.e. multiplied by 2)
        # When the fourier subdomain contains boundary values (wavevector 0 and ny//2) these values should only be added once
        if kdisp.shape[-1] > 0: # TODO: also handle the case with odd number of points
            return .5 * (2 * np.vdot(kdisp[..., 1:-1], -kforces[..., 1:-1]).real
                         +
                         np.vdot(kdisp[..., -1], -kforces[..., -1]).real *
                         (2 if self.fourier_location[-1] + self.fourier_resolution[-1]
                               != self.domain_resolution[-1] // 2 + 1
                          else 1)
                         +
                         np.vdot(kdisp[..., 0], -kforces[..., 0]).real *
                         (2 if self.fourier_location[-1] != 0
                          else 1)
                         ) / self.nb_pts
        else:
            return 0


    def evaluate(self, disp, pot=True, forces=False):
        """Evaluates the elastic energy and the point forces
        Keyword Arguments:
        disp   -- array of distances
        pot    -- (default True) if true, returns potential energy
        forces -- (default False) if true, returns forces
        """
        force = potential = None
        if forces:
            force = self.evaluate_force(disp)

            if pot:
                potential = self.evaluate_elastic_energy(force, disp)
        elif pot:
            kforce = self.evaluate_k_force(disp)
            potential = self.evaluate_elastic_energy_k_space(
                kforce, self.fftengine.rfftn(disp)) # TODO: OPTIMISATION: here kdisp is computed twice, because it's needed in kforce
        return potential, force


class FreeFFTElasticHalfSpace(PeriodicFFTElasticHalfSpace):
    """
    Uses the FFT to solve the displacements and stresses in an non-periodic
    elastic Halfspace due to a given array of point forces. Uses the Green's
    functions formulaiton of Johnson (1985, p. 54). The application of the FFT
    to a nonperiodic domain is explained in Hockney (1969, p. 178.)

    K. L. Johnson. (1985). Contact Mechanics. [Online]. Cambridge: Cambridge
    University Press. Available from: Cambridge Books Online
    <http://dx.doi.org/10.1017/CBO9781139171731> [Accessed 16 February 2015]

    R. W. HOCKNEY, "The potential calculation and some applications," Methods
    of Computational Physics, B. Adler, S. Fernback and M. Rotenberg (Eds.),
    Academic Press, New York, 1969, pp. 136-211.
    """
    name = "free_fft_elastic_halfspace"
    _periodic = False

    def __init__(self, resolution, young, size=2*np.pi,fftengine=None, pnp = np):
        """
        Keyword Arguments:
        resolution  -- Tuple containing number of points in spatial directions.
                       The length of the tuple determines the spatial dimension
                       of the problem. Warning: internally, the free boundary
                       conditions require the system so store a system of
                       2*resolution.x by 2*resolution.y. Keep in mind that if
                       your surface is nx by ny, the forces and displacements
                       will still be 2nx by 2ny.
        young       -- Equiv. Young's modulus E'
                       1/E' = (i-ν_1**2)/E'_1 + (i-ν_2**2)/E'_2
        size        -- (default 2π) domain size. For multidimensional problems,
                       a tuple can be provided to specify the lenths per
                       dimension. If the tuple has less entries than
                       dimensions, the last value in repeated.
        """
        self._comp_resolution = tuple((2 * r for r in resolution))
        super().__init__(resolution, young, size, superclass=False,fftengine=fftengine,pnp=pnp)
        self._compute_fourier_coeffs()
        self._compute_i_fourier_coeffs()


    def spawn_child(self, resolution):
        """
        returns an instance with same physical properties with a smaller
        computational grid
        """
        size = tuple((resolution[i]/float(self.resolution[i])*self.size[i] for
                      i in range(self.dim)))
        return type(self)(resolution, self.young, size)

    @property
    def domain_resolution(self, ):
        """
        usually, the resolution of the system is equal to the geometric
        resolution (of the surface). For example free boundary conditions,
        require the computational resolution to differ from the geometric one,
        see FreeFFTElasticHalfSpace.
        """
        return self._comp_resolution

    def _compute_fourier_coeffs(self):
        """Compute the weights w relating fft(displacement) to fft(pressure):
           fft(u) = w*fft(p), Johnson, p. 54, and Hockney, p. 178

           This version is less is copied from matscipy, use if memory is a
           concern
        """
        # pylint: disable=invalid-name
        facts = np.zeros(tuple((res*2 for res in self.subdomain_resolution)))
        a = self.steps[0]*.5
        if self.dim == 1:
            pass
        else:
            b = self.steps[1]*.5
            x_s = np.arange(self.subdomain_location[0],self.subdomain_location[0] + self.subdomain_resolution[0])
            x_s = np.where(x_s <= self.resolution[0], x_s,
                           x_s-self.resolution[0] * 2) * self.steps[0]
            x_s.shape = (-1, 1)
            y_s = np.arange(self.subdomain_location[1],self.subdomain_location[1] + self.subdomain_resolution[1])
            y_s = np.where(y_s <= self.resolution[1], y_s,
                           y_s-self.resolution[1]*2) * self.steps[1]
            y_s.shape = (1, -1)
            facts = 1/(np.pi*self.young) * (
                (x_s+a)*np.log(((y_s+b)+np.sqrt((y_s+b)*(y_s+b) +
                                                (x_s+a)*(x_s+a))) /
                               ((y_s-b)+np.sqrt((y_s-b)*(y_s-b) +
                                                (x_s+a)*(x_s+a)))) +
                (y_s+b)*np.log(((x_s+a)+np.sqrt((y_s+b)*(y_s+b) +
                                                (x_s+a)*(x_s+a))) /
                               ((x_s-a)+np.sqrt((y_s+b)*(y_s+b) +
                                                (x_s-a)*(x_s-a)))) +
                (x_s-a)*np.log(((y_s-b)+np.sqrt((y_s-b)*(y_s-b) +
                                                (x_s-a)*(x_s-a))) /
                               ((y_s+b)+np.sqrt((y_s+b)*(y_s+b) +
                                                (x_s-a)*(x_s-a)))) +
                (y_s-b)*np.log(((x_s-a)+np.sqrt((y_s-b)*(y_s-b) +
                                                (x_s-a)*(x_s-a))) /
                               ((x_s+a)+np.sqrt((y_s-b)*(y_s-b) +
                                                (x_s+a)*(x_s+a)))))
        self.weights = self.fftengine.rfftn(facts)
        return self.weights, facts

    def evaluate_disp(self, forces):
        """ Computes the displacement due to a given force array
        Keyword Arguments:
        forces   -- a numpy array containing point forces (*not* pressures)

        if running in MPI this should be only the forces in the Subdomain

        if running in serial one can give the force array with or without the padded region

        """
        if forces.shape == self.subdomain_resolution:
            return super().evaluate_disp(forces)

        elif not self.fftengine.is_MPI:
            if forces.shape == self.resolution:
                # Automatically pad forces if force array is half of subdomain
                # resolution
                padded_forces = np.zeros(self.computational_resolution)
                s = [slice(0, forces.shape[i])
                     for i in range(len(forces.shape))]
                padded_forces[s] = forces
                return super().evaluate_disp(padded_forces)[s]
        else:
            raise self.Error("forces should be of subdomain resolution when using MPI")

        raise self.Error("force array has a different shape ({0}) "
                         "than the subdomain resolution ({1}), this halfspace's resolution ({2}) or "
                         "half of it.".format(forces.shape,self.subdomain_resolution,
                                             self.domain_resolution))

        # possible implementation in parallel with adding gather
        #padded_forces = np.zeros(self.domain_resolution)
        #s = [slice(0, max(0, min(self.resolution[i] - self.subdomain_location[i], self.subdomain_resolution[i])))
        #     for i in range(self.dim)]
        #padded_forces[s] = forces
        #return super().evaluate_disp(padded_forces)[s]


# convenient container for storing correspondences betwees small and large
# system
BndSet = namedtuple('BndSet', ('large', 'small'))
