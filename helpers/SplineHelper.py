#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
@file   SplineHelper.py

@author Till Junge <till.junge@kit.edu>

@date   27 Feb 2015

@brief  symbolic calculations for splines

@section LICENCE

 Copyright (C) 2015 Till Junge

PyPyContact is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License as
published by the Free Software Foundation, either version 3, or (at
your option) any later version.

PyPyContact is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
General Public License for more details.

You should have received a copy of the GNU General Public License
along with GNU Emacs; see the file COPYING. If not, write to the
Free Software Foundation, Inc., 59 Temple Place - Suite 330,
Boston, MA 02111-1307, USA.
"""

from PyPyContact.ContactMechanics import LJ93smooth
from sympy import Symbol, pprint, solve_poly_system, Matrix, zeros
import sympy
from copy import deepcopy

# free variable
dr = Symbol('Δr')

# spline parameters
c0 = Symbol('C0', real=True)
c1 = Symbol('C1', real=True)
c2 = Symbol('C2', real=True)
c3 = Symbol('C3', real=True)
c4 = Symbol('C4', real=True)
dr_c = Symbol('Δrc', real=True)
dr_t = Symbol('Δrt', real=True)
dr_m = Symbol('Δrm', real=True)

# boundary parameters
gam = Symbol('γ', positive=True)
dV_t = Symbol('dV_t', real=True)
ddV_t = Symbol('ddV_t', real=True)
ddV_m = Symbol('ddV_M', real=True)

fun = c0 - c1*dr - c2/2*dr**2 - c3/3*dr**3 - c4/4*dr**4
dfun = sympy.diff(fun, dr)
ddfun = sympy.diff(dfun, dr)
print("Spline:")
pprint(fun)
print("Slope:")
pprint(dfun)
print("Curvature:")
pprint(ddfun)

# boundary conditions (satisfied if equal to zero)
bnds = dict()
bnds[1] = dfun.subs(dr, dr_t) - dV_t
bnds[2] = ddfun.subs(dr, dr_t) - ddV_t
bnds[3] = fun.subs(dr, dr_c)
bnds[4] = dfun.subs(dr, dr_c)
bnds[5] = ddfun.subs(dr, dr_c)

stored_bnds = deepcopy(bnds)

def pbnd(boundaries):
    print("\n")
    for key, bnd in boundaries.items():
        print("Boundary condition {}:".format(key))
        pprint(bnd)

# assuming the origin for Δr is at the cutoff (Δrc):
bnds[3] = bnds[3].subs(dr_c, 0.)  # everything is zero at r_cut
bnds[4] = bnds[4].subs(dr_c, 0.)  # everything is zero at r_cut
bnds[5] = bnds[5].subs(dr_c, 0.)  # everything is zero at r_cut


# all at once?
coeff_sol = sympy.solve(bnds.values(), [c0, c1, c2, c3, c4])
print('\nCoefficients')
pprint(coeff_sol)

# solving for Δrt
print('substituted polynomial')
polynomial = fun.subs(coeff_sol)
pprint(polynomial)
# Δrm is a minimum (actually, the global minimum), the one not at zero
dpolynomial = sympy.diff(polynomial, dr)
print("substituted polynomial's derivative:")
pprint(dpolynomial)
sols = sympy.solve(dpolynomial, dr)
for sol in sols:
    if sol != 0:
        sol_drm = sol

print("\nsolution for Δr_m")
pprint(sol_drm)

# γ-condition:
fun = sympy.simplify(polynomial.subs(dr, sol_drm) + gam)

print('\nγ-condition is not solvable analytically.')
print('objective function:')
pprint(fun)
dfun = sympy.simplify(sympy.diff(fun, dr_t))
print('\nobjective function derivative:')
pprint(dfun)

# not solvable in sympy, but good initial guess for optimisation can be
# obtained for case where r_min = r_t (the default case)
guess_fun = fun.subs({"dV_t": 0, "ddV_t": ddV_m})
guess_sol = sympy.solve(guess_fun, dr_t)[0]


print('\ninitial guess: note that you need to evaluate the curvature at r_min '
      'for the square root te be guaranteed to be real (i.e, than the '
      'curvature and γ have the same sign')
pprint(guess_sol)


print()
print("for usage in code:")
print("\nCoefficients: ", [coeff_sol[c0], coeff_sol[c1], coeff_sol[c2], coeff_sol[c3], coeff_sol[c4]])
print("\nobjective_fun: ", fun)
print("\nobjective_derivative: ", dfun)
print("\ninitial guess for Δr_t: ", guess_sol)
print("\nsol for Δr_m: ", sol_drm)