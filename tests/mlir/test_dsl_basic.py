import heterocl as hcl
import numpy as np
import pytest
from hcl_mlir.exceptions import MLIRLimitationError


def _test_logic_op(op):
    def kernel(A, B):
        return hcl.compute(A.shape, lambda x: hcl.select(op(A[x] > 5, B[x] > 5), 0, 1))

    A = hcl.placeholder((10,))
    B = hcl.placeholder((10,))
    s = hcl.create_schedule([A, B], kernel)
    f = hcl.build(s)

    return f


def test_and():

    f = _test_logic_op(hcl.and_)

    np_A = np.random.randint(10, size=(10,))
    np_B = np.random.randint(10, size=(10,))
    np_C = np.zeros(10)

    golden_C = [0 if np_A[i] > 5 and np_B[i] > 5 else 1 for i in range(0, 10)]

    hcl_A = hcl.asarray(np_A)
    hcl_B = hcl.asarray(np_B)
    hcl_C = hcl.asarray(np_C)

    f(hcl_A, hcl_B, hcl_C)

    ret_C = hcl_C.asnumpy()
    assert np.array_equal(ret_C, golden_C)

def test_or():

    with pytest.raises(MLIRLimitationError):
        f = _test_logic_op(hcl.or_)

        np_A = np.random.randint(10, size=(10,))
        np_B = np.random.randint(10, size=(10,))
        np_C = np.zeros(10)

        golden_C = [0 if np_A[i] > 5 or np_B[i] > 5 else 1 for i in range(0, 10)]

        hcl_A = hcl.asarray(np_A)
        hcl_B = hcl.asarray(np_B)
        hcl_C = hcl.asarray(np_C)

        f(hcl_A, hcl_B, hcl_C)

        ret_C = hcl_C.asnumpy()
        assert np.array_equal(ret_C, golden_C)

def test_if():
    def kernel(A):
        with hcl.if_(A[0] > 5):
            A[0] = 5

    A = hcl.placeholder((1,))
    s = hcl.create_schedule(A, kernel)
    f = hcl.build(s)

    np_A = np.random.randint(10, size=(1,))
    golden_A = [5 if np_A[0] > 5 else np_A[0]]

    hcl_A = hcl.asarray(np_A)

    f(hcl_A)

    ret_A = hcl_A.asnumpy()
    assert np.array_equal(golden_A, ret_A)

def test_else():
    hcl.init(hcl.Int(32))
    def kernel(A):
        with hcl.if_(A[0] > 5):
            A[0] = 5
        with hcl.else_():
            A[0] = -1

    A = hcl.placeholder((1,))
    s = hcl.create_schedule(A, kernel)
    f = hcl.build(s)
    np_A = np.random.randint(10, size=(1,))
    golden_A = [5 if np_A[0] > 5 else -1]
    hcl_A = hcl.asarray(np_A)
    f(hcl_A)
    ret_A = hcl_A.asnumpy()
    assert np.array_equal(golden_A, ret_A)

def test_if_scope():
    hcl.init()
    rshape = (1,)
    def kernel():
        false = hcl.scalar(0, "false", dtype='uint32')
        true = hcl.scalar(1, "true", dtype='uint32')
        res = hcl.compute(rshape, lambda x: 0, "res")
        with hcl.if_(true.v == 1): # op a
            with hcl.if_(false.v == 1): # op b
                res[0] = -1
        # op b should be popped from Schedule._IfElseStack here
        # in op a's __exit__ method
        # because it is not closed by elif or else
        with hcl.else_(): # op c
            res[0] = 3
        return res
    s = hcl.create_schedule([], kernel)
    # if hcl.else has the right scope 
    # res should not be updated
    # otherwise, res should be updated to 3
    golden = np.array([0])
    f = hcl.build(s)
    ret = hcl.asarray(np.zeros(rshape))
    f(ret)
    np.allclose(ret.asnumpy(), golden)


def test_cond_all():
    def kernel(A):
        with hcl.if_(A[0] > 5):
            A[0] = 5
        with hcl.elif_(A[0] > 3):
            A[0] = 3
        with hcl.else_():
            A[0] = 0

    A = hcl.placeholder((1,))
    s = hcl.create_schedule(A, kernel)
    f = hcl.build(s)

    np_A = np.random.randint(10, size=(1,))
    golden_A = [5 if np_A[0] > 5 else (3 if np_A[0] > 3 else 0)]

    hcl_A = hcl.asarray(np_A)

    f(hcl_A)

    ret_A = hcl_A.asnumpy()

def test_elif():
    def kernel(A):
        with hcl.if_(A[0] > 5):
            A[0] = 5
        with hcl.elif_(A[0] > 3):
            A[0] = 3

    A = hcl.placeholder((1,))
    s = hcl.create_schedule(A, kernel)
    f = hcl.build(s)

    np_A = np.random.randint(10, size=(1,))
    golden_A = [5 if np_A[0] > 5 else (3 if np_A[0] > 3 else np_A[0])]

    hcl_A = hcl.asarray(np_A)

    f(hcl_A)

    ret_A = hcl_A.asnumpy()
    assert np.array_equal(golden_A, ret_A)


def test_for_basic():
    def kernel(A):
        with hcl.for_(0, 10) as i:
            A[i] = i

    A = hcl.placeholder((10,))
    s = hcl.create_schedule(A, kernel)
    f = hcl.build(s)

    np_A = np.random.randint(10, size=(10,))
    golden_A = [i for i in range(0, 10)]

    hcl_A = hcl.asarray(np_A)

    f(hcl_A)

    ret_A = hcl_A.asnumpy()
    assert np.array_equal(golden_A, ret_A)


def test_for_irregular_bound():
    def kernel(A):
        with hcl.for_(4, 8) as i:
            A[i] = i

    A = hcl.placeholder((10,))
    s = hcl.create_schedule(A, kernel)
    f = hcl.build(s)

    np_A = np.random.randint(10, size=(10,))
    golden_A = np.copy(np_A)
    for i in range(4, 8):
        golden_A[i] = i

    hcl_A = hcl.asarray(np_A)

    f(hcl_A)

    ret_A = hcl_A.asnumpy()
    assert np.array_equal(golden_A, ret_A)


def test_for_step_non_one():
    def kernel(A):
        with hcl.for_(0, 10, 2) as i:
            A[i] = i

    A = hcl.placeholder((10,))
    s = hcl.create_schedule(A, kernel)
    f = hcl.build(s)

    np_A = np.random.randint(10, size=(10,))
    golden_A = np.copy(np_A)
    for i in range(0, 10, 2):
        golden_A[i] = i

    hcl_A = hcl.asarray(np_A)

    f(hcl_A)

    ret_A = hcl_A.asnumpy()
    assert np.array_equal(golden_A, ret_A)


def test_for_step_negative():
    def kernel(A):
        with hcl.for_(9, -1, -1) as i:
            A[i] = i

    A = hcl.placeholder((10,))
    s = hcl.create_schedule(A, kernel)
    f = hcl.build(s)

    np_A = np.random.randint(10, size=(10,))
    golden_A = [i for i in range(0, 10)]

    hcl_A = hcl.asarray(np_A)

    f(hcl_A)

    ret_A = hcl_A.asnumpy()
    assert np.array_equal(golden_A, ret_A)


def test_for_index_casting():
    def kernel(A):
        with hcl.for_(0, 10) as i:
            with hcl.for_(i, 10) as j:
                A[j] += i

    A = hcl.placeholder((10,))
    s = hcl.create_schedule(A, kernel)
    f = hcl.build(s)

    np_A = np.zeros(10)
    golden_A = np.zeros(10)

    for i in range(0, 10):
        for j in range(i, 10):
            golden_A[j] += i

    hcl_A = hcl.asarray(np_A)

    f(hcl_A)

    ret_A = hcl_A.asnumpy()
    assert np.array_equal(golden_A, ret_A)


def test_while_basic():
    def kernel(A):
        a = hcl.scalar(0)
        with hcl.while_(a[0] < 10):
            A[a[0]] = a[0]
            a[0] += 1

    A = hcl.placeholder((10,))
    s = hcl.create_schedule(A, kernel)
    f = hcl.build(s)

    np_A = np.random.randint(10, size=(10,))
    golden_A = [i for i in range(0, 10)]

    hcl_A = hcl.asarray(np_A)

    f(hcl_A)

    ret_A = hcl_A.asnumpy()
    assert np.array_equal(golden_A, ret_A)

def test_invalidate():
    def kernel():
        i = hcl.scalar(0,"i",dtype=hcl.UInt(32))
        with hcl.while_(i.v < 10):
            i.v += 1
    s = hcl.create_schedule([], kernel)

def test_break_in_for():
    with pytest.raises(Exception):
        def kernel(A):
            with hcl.for_(0, 10) as i:
                with hcl.if_(i > 5):
                    hcl.break_()
                A[i] = i

        A = hcl.placeholder((10,))
        s = hcl.create_schedule(A, kernel)
        f = hcl.build(s)

        np_A = np.random.randint(10, size=(10,))
        golden_A = np.copy(np_A)
        for i in range(0, 6):
            golden_A[i] = i

        hcl_A = hcl.asarray(np_A)

        f(hcl_A)

        ret_A = hcl_A.asnumpy()
        assert np.array_equal(golden_A, ret_A)


def test_break_in_while():
    with pytest.raises(Exception):
        def kernel(A):
            i = hcl.scalar(0)
            with hcl.while_(True):
                with hcl.if_(i[0] > 5):
                    hcl.break_()
                A[i[0]] = i[0]
                i[0] += 1

        A = hcl.placeholder((10,))
        s = hcl.create_schedule(A, kernel)
        f = hcl.build(s)

        np_A = np.random.randint(10, size=(10,))
        golden_A = np.copy(np_A)
        for i in range(0, 6):
            golden_A[i] = i

        hcl_A = hcl.asarray(np_A)

        f(hcl_A)

        ret_A = hcl_A.asnumpy()
        assert np.array_equal(golden_A, ret_A)


def test_break_multi_level():
    with pytest.raises(Exception):
        def kernel(A):
            with hcl.for_(0, 10) as i:
                with hcl.for_(0, 10) as j:
                    with hcl.if_(j >= i):
                        hcl.break_()
                    A[i] += j

        A = hcl.placeholder((10,))
        s = hcl.create_schedule(A, kernel)
        f = hcl.build(s)

        np_A = np.random.randint(10, size=(10,))
        golden_A = np.copy(np_A)
        for i in range(0, 10):
            for j in range(0, i):
                golden_A[i] += j

        hcl_A = hcl.asarray(np_A)

        f(hcl_A)

        ret_A = hcl_A.asnumpy()
        assert np.array_equal(golden_A, ret_A)


def test_get_bit_expr():

    hcl.init()

    def kernel(A):
        return hcl.compute(A.shape, lambda x: (A[x] + 1)[0])

    A = hcl.placeholder((10,))
    s = hcl.create_schedule(A, kernel)
    f = hcl.build(s)

    np_A = np.random.randint(10, size=(10,))
    np_B = np.zeros(10)
    golden = (np_A + 1) & 1
    hcl_A = hcl.asarray(np_A)
    hcl_B = hcl.asarray(np_B)

    f(hcl_A, hcl_B)

    ret = hcl_B.asnumpy()
    assert np.array_equal(golden, ret)


def test_get_bit_tensor():

    hcl.init()

    def kernel(A):
        return hcl.compute(A.shape, lambda x: A[x][0])

    A = hcl.placeholder((10,))
    s = hcl.create_schedule(A, kernel)
    f = hcl.build(s)

    np_A = np.random.randint(10, size=(10,))
    np_B = np.zeros(10)
    golden = np_A & 1
    hcl_A = hcl.asarray(np_A)
    hcl_B = hcl.asarray(np_B)

    f(hcl_A, hcl_B)

    ret = hcl_B.asnumpy()
    assert np.array_equal(golden, ret)


def test_set_bit_expr():

    hcl.init()

    def kernel(A, B):
        with hcl.for_(0, 10) as i:
            # B[i] is never written to
            (B[i] + 1)[0] = A[i]

    A = hcl.placeholder((10,), dtype=hcl.Int(1))
    B = hcl.placeholder((10,))
    s = hcl.create_schedule([A, B], kernel)
    f = hcl.build(s)
    np_A = np.random.randint(2, size=(10,))
    np_B = np.random.randint(5, size=(10,))
    golden = np_B
    hcl_A = hcl.asarray(np_A, dtype=hcl.Int(1))
    hcl_B = hcl.asarray(np_B)

    f(hcl_A, hcl_B)

    ret = hcl_B.asnumpy()
    assert np.array_equal(golden, ret)


def test_set_bit_tensor():

    hcl.init()

    def kernel(A, B):
        with hcl.for_(0, 10) as i:
            B[i][0] = A[i]

    A = hcl.placeholder((10,), dtype=hcl.Int(1))
    B = hcl.placeholder((10,))
    s = hcl.create_schedule([A, B], kernel)
    f = hcl.build(s)

    np_A = np.random.randint(1, size=(10,))
    np_B = np.random.randint(10, size=(10,))
    golden = (np_B & 0b1110) | np_A
    hcl_A = hcl.asarray(np_A, dtype=hcl.Int(1))
    hcl_B = hcl.asarray(np_B)

    f(hcl_A, hcl_B)

    ret = hcl_B.asnumpy()
    assert np.array_equal(golden, ret)


def test_get_slice_expr():

    hcl.init()

    def kernel(A):
        return hcl.compute(A.shape, lambda x: (A[x] + 1)[0:2])

    A = hcl.placeholder((10,))
    s = hcl.create_schedule(A, kernel)
    f = hcl.build(s)

    np_A = np.random.randint(10, size=(10,))
    np_B = np.zeros(10)
    golden = (np_A + 1) & 0b11
    hcl_A = hcl.asarray(np_A)
    hcl_B = hcl.asarray(np_B)

    f(hcl_A, hcl_B)

    ret = hcl_B.asnumpy()
    assert np.array_equal(golden, ret)


def test_get_slice_tensor():

    hcl.init()

    def kernel(A):
        return hcl.compute(A.shape, lambda x: A[x][0:2])

    A = hcl.placeholder((10,))
    s = hcl.create_schedule(A, kernel)
    f = hcl.build(s)

    np_A = np.random.randint(10, size=(10,))
    np_B = np.zeros(10)
    golden = np_A & 0b11
    hcl_A = hcl.asarray(np_A)
    hcl_B = hcl.asarray(np_B)

    f(hcl_A, hcl_B)

    ret = hcl_B.asnumpy()
    assert np.array_equal(golden, ret)


def test_get_slice_tensor_reverse():

    hcl.init(hcl.UInt(8))

    def kernel(A):
        return hcl.compute(A.shape, lambda x: (A[x][0:8]).reverse())

    A = hcl.placeholder((10,))
    s = hcl.create_schedule(A, kernel)
    f = hcl.build(s)

    np_A = np.random.randint(10, size=(10,))
    np_B = np.zeros(10)
    golden = np_A & 0xFF
    golden = golden.astype("uint8")
    hcl_A = hcl.asarray(np_A)
    hcl_B = hcl.asarray(np_B)

    f(hcl_A, hcl_B)

    ret = hcl_B.asnumpy()
    ret = ret.astype("uint8")

    for i in range(0, 10):
        x = np.unpackbits(golden[i])
        x = np.flip(x)
        y = np.unpackbits(ret[i])
        assert np.array_equal(x, y)


def test_set_slice_expr():

    hcl.init()

    def kernel(A, B):
        with hcl.for_(0, 10) as i:
            (B[i] + 1)[0:2] = A[i]

    A = hcl.placeholder((10,), dtype=hcl.Int(1))
    B = hcl.placeholder((10,))
    s = hcl.create_schedule([A, B], kernel)
    f = hcl.build(s)
    np_A = np.random.randint(2, size=(10,))
    np_B = np.random.randint(5, size=(10,))
    golden = np_B
    hcl_A = hcl.asarray(np_A, dtype=hcl.Int(1))
    hcl_B = hcl.asarray(np_B)

    f(hcl_A, hcl_B)

    ret = hcl_B.asnumpy()
    assert np.array_equal(golden, ret)

def test_set_slice_tensor():

    hcl.init()

    def kernel(A, B):
        with hcl.for_(0, 10) as i:
            B[i][0:2] = A[i]

    A = hcl.placeholder((10,))
    B = hcl.placeholder((10,))
    s = hcl.create_schedule([A, B], kernel)
    f = hcl.build(s)

    np_A = np.random.randint(1, size=(10,))
    np_B = np.random.randint(10, size=(10,))
    golden = (np_B & 0b1100) | np_A
    hcl_A = hcl.asarray(np_A)
    hcl_B = hcl.asarray(np_B)

    f(hcl_A, hcl_B)

    ret = hcl_B.asnumpy()
    assert np.array_equal(golden, ret)


def test_set_slice_tensor_reverse():

    hcl.init(hcl.UInt(8))

    def kernel(A, B):
        with hcl.for_(0, 10) as i:
            B[i][0:8] = A[i].reverse()

    A = hcl.placeholder((10,))
    B = hcl.placeholder((10,))
    s = hcl.create_schedule([A, B], kernel)
    f = hcl.build(s)

    np_A = np.random.randint(1, size=(10,))
    np_B = np.random.randint(10, size=(10,))
    np_A = np_A.astype("uint8")
    np_B = np_B.astype("uint8")
    hcl_A = hcl.asarray(np_A)
    hcl_B = hcl.asarray(np_B)

    f(hcl_A, hcl_B)

    ret = hcl_B.asnumpy()
    ret = ret.astype("uint8")

    for i in range(0, 10):
        a = np.flip(np.unpackbits(np_A[i]))
        b = np.unpackbits(ret[i])
        assert np.array_equal(a, b)


def test_slice_op():

    hcl.init()

    def kernel(A):
        return hcl.compute(A.shape, lambda x: A[x][0:8] + A[x][8:16])

    A = hcl.placeholder((10,))
    s = hcl.create_schedule(A, kernel)
    f = hcl.build(s)

    np_A = np.random.randint(10, size=(10,))
    np_B = np.zeros(10)
    golden = (np_A & 0xFF) + ((np_A >> 8) & 0xFF)
    hcl_A = hcl.asarray(np_A)
    hcl_B = hcl.asarray(np_B)

    f(hcl_A, hcl_B)

    ret = hcl_B.asnumpy()
    assert np.array_equal(golden, ret)


def test_tensor_slice_mutate():
    hcl.init()
    def kernel():
        z1 = hcl.compute((2,3,4), lambda x,y,z: 0, dtype=hcl.Int(32))
        def do(i,j,k):
            z1[i][j][k] = i + j + k
        hcl.mutate(z1.shape, do)
        return z1
    
    s = hcl.create_schedule([], kernel)
    hcl_res = hcl.asarray(np.zeros((2,3,4), dtype=np.int32))
    f = hcl.build(s)
    f(hcl_res)
    np_res = hcl_res.asnumpy()
    golden = np.zeros((2,3,4), dtype=np.int32)
    for i in range(2):
        for j in range(3):
            for k in range(4):
                golden[i][j][k] = i + j + k
    assert np.array_equal(golden, np_res)


def test_get_bit_expr_mutate():

    hcl.init()

    def kernel(A):
        ret = hcl.compute(A.shape, lambda _ : 0)
        def do(i):
            ret[i] = (A[i] + 1)[0]
        hcl.mutate(A.shape, do)
        return ret

    A = hcl.placeholder((10,))
    s = hcl.create_schedule(A, kernel)
    f = hcl.build(s)

    np_A = np.random.randint(10, size=(10,))
    np_B = np.zeros(10)
    golden = (np_A + 1) & 1
    hcl_A = hcl.asarray(np_A)
    hcl_B = hcl.asarray(np_B)

    f(hcl_A, hcl_B)

    ret = hcl_B.asnumpy()
    assert np.array_equal(golden, ret)


def test_set_bit_expr_mutate():

    hcl.init()

    def kernel(A, B):
        def do(i):
            # B[i] is never written to
            (B[i] + 1)[0] = A[i]
        hcl.mutate(A.shape, do)

    A = hcl.placeholder((10,), dtype=hcl.Int(1))
    B = hcl.placeholder((10,))
    s = hcl.create_schedule([A, B], kernel)
    f = hcl.build(s)
    np_A = np.random.randint(2, size=(10,))
    np_B = np.random.randint(5, size=(10,))
    golden = np_B
    hcl_A = hcl.asarray(np_A, dtype=hcl.Int(1))
    hcl_B = hcl.asarray(np_B)

    f(hcl_A, hcl_B)

    ret = hcl_B.asnumpy()
    assert np.array_equal(golden, ret)


def test_set_bit_tensor_mutate():

    hcl.init()

    def kernel(A, B):
        def do(i):
            B[i][0] = A[i]
        hcl.mutate(A.shape, do)

    A = hcl.placeholder((10,), dtype=hcl.Int(1))
    B = hcl.placeholder((10,))
    s = hcl.create_schedule([A, B], kernel)
    f = hcl.build(s)

    np_A = np.random.randint(1, size=(10,))
    np_B = np.random.randint(10, size=(10,))
    golden = (np_B & 0b1110) | np_A
    hcl_A = hcl.asarray(np_A, dtype=hcl.Int(1))
    hcl_B = hcl.asarray(np_B)

    f(hcl_A, hcl_B)

    ret = hcl_B.asnumpy()
    assert np.array_equal(golden, ret)

def test_get_slice_expr_mutate():

    hcl.init()

    def kernel(A):
        ret = hcl.compute(A.shape, lambda _  : 0)
        def do(i):
            ret[i] = (A[i] + 1)[0:2]
        hcl.mutate(A.shape, do)
        return ret

    A = hcl.placeholder((10,))
    s = hcl.create_schedule(A, kernel)
    f = hcl.build(s)

    np_A = np.random.randint(10, size=(10,))
    np_B = np.zeros(10)
    golden = (np_A + 1) & 0b11
    hcl_A = hcl.asarray(np_A)
    hcl_B = hcl.asarray(np_B)

    f(hcl_A, hcl_B)

    ret = hcl_B.asnumpy()
    assert np.array_equal(golden, ret)

def test_get_slice_tensor_mutate():

    hcl.init()

    def kernel(A):
        ret = hcl.compute(A.shape, lambda _ : 0)
        def do(i):
            ret[i] = A[i][0:2]
        hcl.mutate(A.shape, do)
        return ret

    A = hcl.placeholder((10,))
    s = hcl.create_schedule(A, kernel)
    f = hcl.build(s)

    np_A = np.random.randint(10, size=(10,))
    np_B = np.zeros(10)
    golden = np_A & 0b11
    hcl_A = hcl.asarray(np_A)
    hcl_B = hcl.asarray(np_B)

    f(hcl_A, hcl_B)

    ret = hcl_B.asnumpy()
    assert np.array_equal(golden, ret)

def test_get_slice_tensor_reverse_mutate():
    hcl.init(hcl.UInt(8))

    def kernel(A):
        ret = hcl.compute(A.shape, lambda _ : 0)
        def do(i):
            ret[i] = A[i][0:8].reverse()
        hcl.mutate(A.shape, do)
        return ret

    A = hcl.placeholder((10,))
    s = hcl.create_schedule(A, kernel)
    f = hcl.build(s)

    np_A = np.random.randint(10, size=(10,))
    np_B = np.zeros(10)
    golden = np_A & 0xFF
    golden = golden.astype("uint8")
    hcl_A = hcl.asarray(np_A)
    hcl_B = hcl.asarray(np_B)

    f(hcl_A, hcl_B)

    ret = hcl_B.asnumpy()
    ret = ret.astype("uint8")

    for i in range(0, 10):
        x = np.unpackbits(golden[i])
        x = np.flip(x)
        y = np.unpackbits(ret[i])
        assert np.array_equal(x, y)

def test_set_slice_expr_mutate():

    hcl.init()

    def kernel(A, B):
        def do(i):
            (B[i] + 1)[0:2] = A[i]
        hcl.mutate(A.shape, do)

    A = hcl.placeholder((10,), dtype=hcl.Int(1))
    B = hcl.placeholder((10,))
    s = hcl.create_schedule([A, B], kernel)
    f = hcl.build(s)
    np_A = np.random.randint(2, size=(10,))
    np_B = np.random.randint(5, size=(10,))
    golden = np_B
    hcl_A = hcl.asarray(np_A, dtype=hcl.Int(1))
    hcl_B = hcl.asarray(np_B)

    f(hcl_A, hcl_B)

    ret = hcl_B.asnumpy()
    assert np.array_equal(golden, ret)

def test_set_slice_tensor_mutate():

    hcl.init()

    def kernel(A, B):
        def do(i):
            B[i][0:2] = A[i]
        hcl.mutate(A.shape, do)

    A = hcl.placeholder((10,))
    B = hcl.placeholder((10,))
    s = hcl.create_schedule([A, B], kernel)
    f = hcl.build(s)

    np_A = np.random.randint(1, size=(10,))
    np_B = np.random.randint(10, size=(10,))
    golden = (np_B & 0b1100) | np_A
    hcl_A = hcl.asarray(np_A)
    hcl_B = hcl.asarray(np_B)

    f(hcl_A, hcl_B)

    ret = hcl_B.asnumpy()
    assert np.array_equal(golden, ret)

def test_set_slice_tensor_reverse_mutate():

    hcl.init(hcl.UInt(8))

    def kernel(A, B):
        def do(i):
            B[i][0:8] = A[i].reverse()
        hcl.mutate(A.shape, do)

    A = hcl.placeholder((10,))
    B = hcl.placeholder((10,))
    s = hcl.create_schedule([A, B], kernel)
    f = hcl.build(s)

    np_A = np.random.randint(1, size=(10,))
    np_B = np.random.randint(10, size=(10,))
    np_A = np_A.astype("uint8")
    np_B = np_B.astype("uint8")
    hcl_A = hcl.asarray(np_A)
    hcl_B = hcl.asarray(np_B)

    f(hcl_A, hcl_B)

    ret = hcl_B.asnumpy()
    ret = ret.astype("uint8")

    for i in range(0, 10):
        a = np.flip(np.unpackbits(np_A[i]))
        b = np.unpackbits(ret[i])
        assert np.array_equal(a, b)

def test_slice_op_mutate():

    hcl.init()

    def kernel(A):
        ret = hcl.compute(A.shape, lambda _ : 0)
        def do(i):
            ret[i] = A[i][0:8] + A[i][8:16]
        hcl.mutate(A.shape, do)
        return ret

    A = hcl.placeholder((10,))
    s = hcl.create_schedule(A, kernel)
    f = hcl.build(s)

    np_A = np.random.randint(10, size=(10,))
    np_B = np.zeros(10)
    golden = (np_A & 0xFF) + ((np_A >> 8) & 0xFF)
    hcl_A = hcl.asarray(np_A)
    hcl_B = hcl.asarray(np_B)

    f(hcl_A, hcl_B)

    ret = hcl_B.asnumpy()
    assert np.array_equal(golden, ret)

def test_tensor_slice_struct():
    hcl.init()
    def kernel():
        stype = hcl.Struct({"x": hcl.UInt(8), "y": hcl.UInt(8)})
        xy = hcl.scalar(0x0102, "foo", dtype=stype).v
        z1 = hcl.compute((2,3), lambda x,y: x+y, dtype=hcl.UInt(32))
        r = hcl.compute((4,), lambda _: 0, dtype=hcl.UInt(32))
        t = z1[xy.y]
        assert t.shape == (3,)
        r[0] = t[xy.x]
        return r
    
    s = hcl.create_schedule([], kernel)
    hcl_res = hcl.asarray(np.zeros((4,), dtype=np.uint32), dtype=hcl.UInt(32))
    f = hcl.build(s)
    f(hcl_res)
    np_res = hcl_res.asnumpy()
    golden = np.zeros((4,), dtype=np.uint32)
    golden[0] = 3
    assert np.array_equal(golden, np_res)

def test_tensor_index_expr():
    hcl.init()
    def kernel(A, B, x):
        def do(i, j, k):
            B[i * 2 * 4 + j * 4 + k] = A[i][j][x.v]
        hcl.mutate(A.shape, do)
    A = hcl.placeholder((2, 2, 4), dtype=hcl.Float(32))
    B = hcl.placeholder((16,), dtype=hcl.Float(32))
    x = hcl.placeholder((1,), dtype=hcl.Int(32))
    s = hcl.create_schedule([A, B, x], kernel)
    f = hcl.build(s)
    np_A = np.random.randint(10, size=(2, 2, 4))
    np_B = np.zeros((16,))
    np_x = np.array([2])
    golden = np.zeros((16,))
    for i in range(0, 2):
        for j in range(0, 2):
            for k in range(0, 4):
                golden[i * 2 * 4 + j * 4 + k] = np_A[i][j][np_x[0]]
    hcl_A = hcl.asarray(np_A, dtype=hcl.Float(32))
    hcl_B = hcl.asarray(np_B, dtype=hcl.Float(32))
    hcl_x = hcl.asarray(np_x, dtype=hcl.Int(32))
    f(hcl_A, hcl_B, hcl_x)
    ret_B = hcl_B.asnumpy()
    assert np.array_equal(golden, ret_B)

def test_unused_struct_tensor():
    hcl.init()
    def kernel():
        stype = hcl.Struct({"x": hcl.UInt(8), "y": hcl.UInt(8)})
        xy = hcl.scalar(0x12, "foo", dtype=stype).v
        r = hcl.compute((2,), lambda i: 0, dtype=hcl.UInt(32))
        return r

    s = hcl.create_schedule([], kernel)
    hcl_res = hcl.asarray(np.zeros((2,), dtype=np.uint32), dtype=hcl.UInt(32))
    f = hcl.build(s)
    f(hcl_res)
    np_res = hcl_res.asnumpy()
    golden = np.zeros((2,), dtype=np.uint32)
    assert np.array_equal(golden, np_res)

def test_tensor_slice_dtype():
    hcl.init()
    def kernel():
        z1 = hcl.compute((2,3,4), lambda x,y,z: 0, dtype=hcl.Int(32))
        def do(i,j,k):
            z_slice = z1[0][0]
            z_slice[0] = hcl.get_bitwidth(z_slice.dtype)
        hcl.mutate(z1.shape, do)
        return z1
    
    s = hcl.create_schedule([], kernel)
    hcl_res = hcl.asarray(np.zeros((2,3,4), dtype=np.int32))
    f = hcl.build(s)
    f(hcl_res)
    np_res = hcl_res.asnumpy()
    golden = np.zeros((2,3,4), dtype=np.int32)
    golden[0][0][0] = 32
    assert np.array_equal(golden, np_res)