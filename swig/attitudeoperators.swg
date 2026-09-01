/******************************************************************************
* Copyright (c) ATTX INC 2026. All Rights Reserved.
*
* This software and associated documentation (the "Software") are the
* proprietary and confidential information of ATTX, INC. The Software is
* furnished under a license agreement between ATTX and the user organization
* and may be used or copied only in accordance with the terms of the agreement.
* Refer to 'license/attx_license.adoc' for standard license terms.
*
* EXPORT CONTROL NOTICE: THIS SOFTWARE MAY INCLUDE CONTENT CONTROLLED UNDER THE
* INTERNATIONAL TRAFFIC IN ARMS REGULATIONS (ITAR) OR THE EXPORT ADMINISTRATION
* REGULATIONS (EAR99). No part of the Software may be used, reproduced, or
* transmitted in any form or by any means, for any purpose, without the express
* written permission of ATTX, INC.
******************************************************************************/
/*
Python operator support for the attitude types.

Included after the dynamics headers, because these classes derive from the matrix and vector
templates and so cannot be extended until those are instantiated.

Most of what these types need they already inherit. DCM derives from Matrix<3,3> and Euler321
and MRP derive from CartesianVector<3>, so indexing, arithmetic, comparison and repr all arrive
from mathoperators.i, and the results match C++ exactly -- dcm_a*dcm_b is a Matrix3 in Python
because operator*(Matrix<3,3>, Matrix<3,3>) is what C++ resolves it to as well.

Quaternion is the exception. It declares its own operator*, for composing two rotations and for
rotating a vector, and a class that declares an operator hides the inherited ones. The scalar
forms are restored here so that a quaternion is still usable as the four-vector it is.
*/

%extend clockwerk::Quaternion {
    /* Composition and vector rotation come from the class itself. These put back the
     * element-wise arithmetic that declaring operator* hid, and are the same operations
     * CartesianVector<4> offers.
     *
     * Each of these binds the quaternion to a reference of its base type before doing the
     * arithmetic. Written as `*$self * b` the call is ambiguous: CartesianVector has a
     * converting constructor from a single scalar, so a double is a viable argument to both
     * operator*(CartesianVector<4>, double) and Quaternion::operator*(CartesianVector<3>).
     * Naming the base type takes the member operator out of the candidate set. The same
     * ambiguity is reachable from C++ -- `quat*2.0` compiles, with a warning, and rotates a
     * vector of twos rather than scaling the quaternion. */
    clockwerk::CartesianVector<4> __mul__(double b) const {
        const clockwerk::CartesianVector<4> &v = *$self;
        return v*b;
    }
    clockwerk::CartesianVector<4> __rmul__(double b) const {
        const clockwerk::CartesianVector<4> &v = *$self;
        return b*v;
    }
    clockwerk::CartesianVector<4> __add__(const clockwerk::CartesianVector<4> &b) const {
        const clockwerk::CartesianVector<4> &v = *$self;
        return v + b;
    }
    clockwerk::CartesianVector<4> __sub__(const clockwerk::CartesianVector<4> &b) const {
        const clockwerk::CartesianVector<4> &v = *$self;
        return v - b;
    }
    clockwerk::CartesianVector<4> __neg__() const {
        const clockwerk::CartesianVector<4> &v = *$self;
        return (-1.0)*v;
    }

    %pythoncode %{
    def __truediv__(self, b):
        b = float(b)
        if b == 0.0:
            raise ZeroDivisionError("division of a quaternion by zero")
        return self*(1.0/b)

    def __repr__(self):
        return "%s(%r)" % (type(self).__name__, self.tolist())

    __hash__ = object.__hash__
    %}
}

/* The remaining attitude types get a repr that names them, since the inherited one would report
 * the base class. Everything else about them is inherited and already correct. */
%extend clockwerk::DCM {
    %pythoncode %{
    def __repr__(self):
        return "%s(%r)" % (type(self).__name__, self.tolist())

    __hash__ = object.__hash__
    %}
}

%extend clockwerk::Euler321 {
    %pythoncode %{
    def __repr__(self):
        return "%s(%r)" % (type(self).__name__, self.tolist())

    __hash__ = object.__hash__
    %}
}

%extend clockwerk::MRP {
    %pythoncode %{
    def __repr__(self):
        return "%s(%r)" % (type(self).__name__, self.tolist())

    __hash__ = object.__hash__
    %}
}
