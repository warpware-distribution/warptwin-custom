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
Python operator support for the clockwerk matrix and vector types.

The intent is that a Matrix or CartesianVector behaves in Python the way it does in C++:
indexing with m[i][j] or v[i], the same arithmetic operators resolving through the same free
functions, and construction and comparison by value. All of it lives here rather than in the
C++ headers -- the headers stay free of anything that exists only for the bindings.

The types are templates, so the operator set is written once per kind as a SWIG macro and
invoked for each instantiation. C++ carries the arithmetic, which is where it matters; the
ergonomics on top -- index normalisation, bounds checks, slices, repr -- sit in the %pythoncode
blocks, where raising a proper IndexError or ValueError costs nothing and needs no exception
plumbing through the wrapper layer.

Attitude types are handled in attitudeoperators.i, which has to come after the dynamics headers.
*/

/* ================================================================================================
 * Shared Python helpers
 * ============================================================================================= */
%pythoncode %{
def _wt_index(i, n, what):
    """Normalise a Python index against a length, honouring negative indices."""
    i = int(i)
    if i < 0:
        i += n
    if i < 0 or i >= n:
        raise IndexError("%s index out of range for length %d" % (what, n))
    return i


class _MatrixRow(object):
    """A view of one row of a Matrix.

    Returned by Matrix.__getitem__ for an integer key so that m[i][j] both reads and writes the
    underlying element, which is what m[i][j] does in C++. Holding a reference to the matrix
    rather than a copy of the row is what makes the write land.
    """
    __slots__ = ("_m", "_r")

    def __init__(self, matrix, row):
        self._m = matrix
        self._r = row

    def __len__(self):
        return self._m.nCols()

    def __getitem__(self, col):
        if isinstance(col, slice):
            return [self._m.getAt(self._r, k) for k in range(*col.indices(len(self)))]
        return self._m.getAt(self._r, _wt_index(col, len(self), "column"))

    def __setitem__(self, col, value):
        if isinstance(col, slice):
            targets = list(range(*col.indices(len(self))))
            values = [float(v) for v in value]
            if len(values) != len(targets):
                raise ValueError("cannot assign %d values to %d columns"
                                 % (len(values), len(targets)))
            for k, v in zip(targets, values):
                self._m.setAt(self._r, k, v)
            return
        self._m.setAt(self._r, _wt_index(col, len(self), "column"), float(value))

    def __iter__(self):
        for c in range(len(self)):
            yield self._m.getAt(self._r, c)

    def __eq__(self, other):
        try:
            return list(self) == [float(v) for v in other]
        except TypeError:
            return NotImplemented

    def __ne__(self, other):
        result = self.__eq__(other)
        return result if result is NotImplemented else not result

    def __repr__(self):
        return repr(list(self))

    __hash__ = None


def _wt_mat_getitem(m, key):
    if isinstance(key, tuple):
        if len(key) != 2:
            raise IndexError("a matrix is indexed by a row and a column")
        return m.getAt(_wt_index(key[0], m.nRows(), "row"),
                       _wt_index(key[1], m.nCols(), "column"))
    if isinstance(key, slice):
        return [_MatrixRow(m, i) for i in range(*key.indices(m.nRows()))]
    return _MatrixRow(m, _wt_index(key, m.nRows(), "row"))


def _wt_mat_setitem(m, key, value):
    if isinstance(key, tuple):
        if len(key) != 2:
            raise IndexError("a matrix is indexed by a row and a column")
        m.setAt(_wt_index(key[0], m.nRows(), "row"),
                _wt_index(key[1], m.nCols(), "column"), float(value))
        return
    row = _wt_index(key, m.nRows(), "row")
    values = [float(v) for v in value]
    if len(values) != m.nCols():
        raise ValueError("cannot assign %d values to a row of %d" % (len(values), m.nCols()))
    for j, v in enumerate(values):
        m.setAt(row, j, v)


def _wt_mat_tolist(m):
    return [[m.getAt(i, j) for j in range(m.nCols())] for i in range(m.nRows())]


def _wt_mat_fromlist(m, rows):
    rows = [list(r) for r in rows]
    if len(rows) != m.nRows():
        raise ValueError("expected %d rows, got %d" % (m.nRows(), len(rows)))
    for i, row in enumerate(rows):
        if len(row) != m.nCols():
            raise ValueError("row %d has %d columns, expected %d" % (i, len(row), m.nCols()))
        for j, v in enumerate(row):
            m.setAt(i, j, float(v))


def _wt_vec_getitem(v, key):
    if isinstance(key, slice):
        return [v.getAt(k) for k in range(*key.indices(v.nElements()))]
    return v.getAt(_wt_index(key, v.nElements(), "element"))


def _wt_vec_setitem(v, key, value):
    if isinstance(key, slice):
        targets = list(range(*key.indices(v.nElements())))
        values = [float(x) for x in value]
        if len(values) != len(targets):
            raise ValueError("cannot assign %d values to %d elements"
                             % (len(values), len(targets)))
        for k, x in zip(targets, values):
            v.setAt(k, x)
        return
    v.setAt(_wt_index(key, v.nElements(), "element"), float(value))


def _wt_vec_tolist(v):
    return [v.getAt(i) for i in range(v.nElements())]


def _wt_vec_fromlist(v, values):
    values = [float(x) for x in values]
    if len(values) != v.nElements():
        raise ValueError("expected %d elements, got %d" % (v.nElements(), len(values)))
    for i, x in enumerate(values):
        v.setAt(i, x)
%}

/* ================================================================================================
 * Matrix<R, C>
 *
 * The arithmetic calls the same free operators in matrixmath.hpp that C++ callers use, so Python
 * and C++ cannot drift apart on what an operation means.
 * ============================================================================================= */
%define WT_MATRIX_METHODS(R, C)
%extend clockwerk::Matrix<R, C> {
    /* ---- shape and raw element access; bounds are checked in the Python layer ---- */
    int nRows() const {return R;}
    int nCols() const {return C;}
    double getAt(int r, int c) const {return $self->values[r][c];}
    void setAt(int r, int c, double value) {$self->values[r][c] = value;}

    /* ---- arithmetic ---- */
    clockwerk::Matrix<R, C> __add__(const clockwerk::Matrix<R, C> &b) const {return *$self + b;}
    clockwerk::Matrix<R, C> __add__(double b) const {return *$self + b;}
    clockwerk::Matrix<R, C> __radd__(double b) const {return b + *$self;}
    clockwerk::Matrix<R, C> __sub__(const clockwerk::Matrix<R, C> &b) const {return *$self - b;}
    clockwerk::Matrix<R, C> __sub__(double b) const {return *$self + (-b);}
    clockwerk::Matrix<R, C> __rsub__(double b) const {return (-1.0)*(*$self) + b;}
    clockwerk::Matrix<R, C> __neg__() const {return (-1.0)*(*$self);}
    clockwerk::Matrix<R, C> __mul__(double b) const {return (*$self)*b;}
    clockwerk::Matrix<R, C> __rmul__(double b) const {return b*(*$self);}

    /* ---- comparison by value. The operator itself is written in Python so that comparing
       against something that is not a matrix answers False rather than raising ---- */
    bool equals(const clockwerk::Matrix<R, C> &b, double tolerance) const {
        for(int i = 0; i < R; i++) {
            for(int j = 0; j < C; j++) {
                double diff = $self->values[i][j] - b.values[i][j];
                if(diff < 0.0) {diff = -diff;}
                if(diff > tolerance) {return false;}
            }
        }
        return true;
    }

    %pythoncode %{
    def __len__(self):
        return self.nRows()

    def __iter__(self):
        for i in range(self.nRows()):
            yield _MatrixRow(self, i)

    def __getitem__(self, key):
        return _wt_mat_getitem(self, key)

    def __setitem__(self, key, value):
        _wt_mat_setitem(self, key, value)

    def tolist(self):
        """The matrix as a list of row lists."""
        return _wt_mat_tolist(self)

    def fromlist(self, rows):
        """Set every element from a list of row lists of the matching shape."""
        _wt_mat_fromlist(self, rows)

    def __truediv__(self, b):
        b = float(b)
        if b == 0.0:
            raise ZeroDivisionError("division of a matrix by zero")
        return self*(1.0/b)

    def __eq__(self, other, tolerance=0.0):
        # Guarded on the interface rather than on the class. More than one SWIG module publishes
        # a proxy class for the same C++ type -- VisualsModel.i deliberately re-wraps the vector
        # types so its own signatures are exposed -- and which class an object comes back as
        # depends on import order. Comparing by class would make two matrices holding the same
        # value unequal for a reason the caller cannot see. The C++ comparison resolves through
        # the shared SWIG type table and works across modules.
        if not hasattr(other, "nRows") or not hasattr(other, "nCols"):
            return NotImplemented
        if other.nRows() != self.nRows() or other.nCols() != self.nCols():
            return False
        try:
            return self.equals(other, tolerance)
        except TypeError:
            return NotImplemented

    def __ne__(self, other):
        result = self.__eq__(other)
        return result if result is NotImplemented else not result

    def isclose(self, other, tolerance=1e-9):
        """Element-wise comparison to a tolerance, for comparing floating point results."""
        return self.__eq__(other, tolerance)

    def __repr__(self):
        return "%s(%r)" % (type(self).__name__, self.tolist())

    def __str__(self):
        return self.dump()

    # Defining __eq__ would otherwise make these unhashable, and they were hashable before
    __hash__ = object.__hash__
    %}
}
%enddef

/* Multiplication is generated per compatible dimension pair -- Matrix<R,C> * Matrix<C,K> is the
 * only product that exists, and the result type differs for every K. The vector form is declared
 * first so that a CartesianVector argument resolves to it rather than to the Matrix<C,1> base it
 * derives from, giving back a vector the way C++ does. */
%define WT_MATRIX_MUL_VEC(R, C)
%extend clockwerk::Matrix<R, C> {
    clockwerk::CartesianVector<R> __mul__(const clockwerk::CartesianVector<C> &b) const {
        return *$self*b;
    }
}
%enddef

%define WT_MATRIX_MUL(R, C, K)
%extend clockwerk::Matrix<R, C> {
    clockwerk::Matrix<R, K> __mul__(const clockwerk::Matrix<C, K> &b) const {return *$self*b;}
}
%enddef

/* ================================================================================================
 * CartesianVector<L>
 *
 * A vector derives from Matrix<L,1>, so it inherits everything above. What is overridden here are
 * the places where a vector is indexed and multiplied as a vector rather than as a one-column
 * matrix.
 * ============================================================================================= */
%define WT_VECTOR_METHODS(L)
%extend clockwerk::CartesianVector<L> {
    int nElements() const {return L;}
    double getAt(int i) const {return $self->get(i);}
    void setAt(int i, double value) {$self->set(i, value);}

    clockwerk::CartesianVector<L> __add__(const clockwerk::CartesianVector<L> &b) const {
        return *$self + b;
    }
    clockwerk::CartesianVector<L> __add__(double b) const {return *$self + b;}
    clockwerk::CartesianVector<L> __radd__(double b) const {return b + *$self;}
    clockwerk::CartesianVector<L> __sub__(const clockwerk::CartesianVector<L> &b) const {
        return *$self - b;
    }
    clockwerk::CartesianVector<L> __sub__(double b) const {return *$self + (-b);}
    clockwerk::CartesianVector<L> __rsub__(double b) const {return (-1.0)*(*$self) + b;}
    clockwerk::CartesianVector<L> __neg__() const {return (-1.0)*(*$self);}
    clockwerk::CartesianVector<L> __mul__(double b) const {return (*$self)*b;}
    clockwerk::CartesianVector<L> __rmul__(double b) const {return b*(*$self);}

    double dot(const clockwerk::CartesianVector<L> &b) const {return clockwerk::dot(*$self, b);}

    bool equals(const clockwerk::CartesianVector<L> &b, double tolerance) const {
        for(int i = 0; i < L; i++) {
            double diff = $self->get(i) - b.get(i);
            if(diff < 0.0) {diff = -diff;}
            if(diff > tolerance) {return false;}
        }
        return true;
    }

    %pythoncode %{
    def __len__(self):
        return self.nElements()

    def __iter__(self):
        for i in range(self.nElements()):
            yield self.getAt(i)

    def __getitem__(self, key):
        return _wt_vec_getitem(self, key)

    def __setitem__(self, key, value):
        _wt_vec_setitem(self, key, value)

    def tolist(self):
        """The vector as a list of floats."""
        return _wt_vec_tolist(self)

    def fromlist(self, values):
        """Set every element from a sequence of the matching length."""
        _wt_vec_fromlist(self, values)

    def __truediv__(self, b):
        b = float(b)
        if b == 0.0:
            raise ZeroDivisionError("division of a vector by zero")
        return self*(1.0/b)

    def __eq__(self, other, tolerance=0.0):
        # See the note on Matrix.__eq__: guarded on the interface, not the class, because the
        # same C++ vector type has a proxy class in more than one module
        if not hasattr(other, "nElements"):
            return NotImplemented
        if other.nElements() != self.nElements():
            return False
        try:
            return self.equals(other, tolerance)
        except TypeError:
            return NotImplemented

    def __ne__(self, other):
        result = self.__eq__(other)
        return result if result is NotImplemented else not result

    def isclose(self, other, tolerance=1e-9):
        """Element-wise comparison to a tolerance, for comparing floating point results."""
        return self.__eq__(other, tolerance)

    def __repr__(self):
        return "%s(%r)" % (type(self).__name__, self.tolist())

    def __str__(self):
        return self.dump()

    __hash__ = object.__hash__
    %}
}
%enddef

/* The three-element case additionally carries the operations that only exist in three
 * dimensions, matching vectormath.hpp */
%define WT_VECTOR3_METHODS
%extend clockwerk::CartesianVector<3> {
    clockwerk::CartesianVector<3> cross(const clockwerk::CartesianVector<3> &b) const {
        return clockwerk::cross(*$self, b);
    }
    clockwerk::Matrix<3, 3> tilde() const {return clockwerk::tilde(*$self);}
}
%enddef

%include "mathinstantiations.swg"
