#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
@file   AutocorrelationTest.py

@author Lars Pastewka <lars.pastewka@imtek.uni-freiburg.de>

@date   17 Dec 2018

@brief  Tests for autocorrelation function analysis

@section LICENCE

Copyright 2018 Lars Pastewka

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

import numpy as np

from PyCo.Topography import Topography, UniformLineScan, NonuniformLineScan
from PyCo.Topography.Generation import fourier_synthesis
from PyCo.Topography.Nonuniform.Autocorrelation import _bare_autocorrelation_1D

from tests.PyCoTest import PyCoTestCase


class AutocorrelationTest(PyCoTestCase):
    def test_uniform_impulse_autocorrelation(self):
        nx = 16
        for x, w, h, p in [(nx // 2, 3, 1, True), (nx // 3, 2, 2, True),
                           (nx // 2, 5, 1, False), (nx // 3, 6, 2.5, False)]:
            y = np.zeros(nx)
            y[x - w // 2:x + (w + 1) // 2] = h
            r, A = UniformLineScan(y, nx, periodic=True).autocorrelation_1D()

            A_ana = np.zeros_like(A)
            A_ana[:w] = h ** 2 * np.linspace(w / nx, 1 / nx, w)
            A_ana = A_ana[0] - A_ana
            self.assertTrue(np.allclose(A, A_ana))

    def test_uniform_brute_force_autocorrelation_1D(self):
        n = 10
        for surf in [UniformLineScan(np.ones(n), n, periodic=False),
                     UniformLineScan(np.arange(n), n, periodic=False),
                     Topography(np.random.random(n).reshape(n, 1), (n, 1), periodic=False)]:
            r, A = surf.autocorrelation_1D()

            n = len(A)
            dir_A = np.zeros(n)
            for d in range(n):
                for i in range(n - d):
                    dir_A[d] += (surf.heights()[i] - surf.heights()[i + d]) ** 2 / 2
                dir_A[d] /= (n - d)
            self.assertArrayAlmostEqual(A, dir_A)

    def test_uniform_brute_force_autocorrelation_2D(self):
        n = 10
        m = 11
        for surf in [Topography(np.ones([n, m]), (n, m), periodic=False),
                     Topography(np.random.random([n, m]), (n, m), periodic=False)]:
            r, A, A_xy = surf.autocorrelation_2D(return_map=True)

            nx, ny = surf.resolution
            dir_A_xy = np.zeros([n, m])
            dir_A = np.zeros_like(A)
            dir_n = np.zeros_like(A)
            for dx in range(n):
                for dy in range(m):
                    for i in range(nx - dx):
                        for j in range(ny - dy):
                            dir_A_xy[dx, dy] += (surf.heights()[i, j] - surf.heights()[i + dx, j + dy]) ** 2 / 2
                    dir_A_xy[dx, dy] /= (nx - dx) * (ny - dy)
                    d = np.sqrt(dx ** 2 + dy ** 2)
                    i = np.argmin(np.abs(r - d))
                    dir_A[i] += dir_A_xy[dx, dy]
                    dir_n[i] += 1
            dir_n[dir_n == 0] = 1
            dir_A /= dir_n
            self.assertArrayAlmostEqual(A_xy, dir_A_xy)
            self.assertArrayAlmostEqual(A[:-2], dir_A[:-2])

    def test_nonuniform_impulse_autocorrelation(self):
        x = np.array([0, 3.])
        t = NonuniformLineScan(x, 2 * np.ones_like(x))
        r, A = _bare_autocorrelation_1D(t, distances=np.linspace(-4, 4, 101))

    def test_nonuniform_triangle_autocorrelation(self):
        a = 0.7
        b = 3
        x = np.array([0, b])
        t = NonuniformLineScan(x, a * x)
        r, A = _bare_autocorrelation_1D(t, distances=np.linspace(-4, 4, 101))

        self.assertAlmostEqual(A[np.abs(r) < 1e-6][0], a ** 2 * b ** 3 / 3)

        x = np.array([0, 1., 1.3, 1.7, 2.0, 2.5, 3.0])
        t = NonuniformLineScan(x, 0.7 * x)
        r2, A2 = _bare_autocorrelation_1D(t, distances=np.linspace(-4, 4, 101))

        self.assertArrayAlmostEqual(A, A2)

    def test_self_affine_uniform_autocorrelation(self):
        r = 2048
        s = 1
        H = 0.8
        slope = 0.1
        t = fourier_synthesis((r,), (s,), H, rms_slope=slope, amplitude_distribution=lambda n: 1.0)

        r, A = t.autocorrelation_1D()

        m  = np.logical_and(r > 1e-3, r < 10**(-1.5))
        b, a = np.polyfit(np.log(r[m]), np.log(A[m]), 1)
        self.assertTrue(abs(b/2 - H) < 0.1)

    def test_self_affine_nonuniform_autocorrelation(self):
        r = 128
        s = 1
        H = 0.8
        slope = 0.1
        t = fourier_synthesis((r,), (s,), H, rms_slope=slope, amplitude_distribution=lambda n: 1.0)
        r, A = t.autocorrelation_1D()
        r2, A2 = t.to_nonuniform().autocorrelation_1D()

        import matplotlib.pyplot as plt
        plt.figure()
        plt.loglog(r, A, 'r-')
        plt.loglog(r2, A2, 'k-')
        plt.show()
