import heterocl as hcl
import numpy as np
import hcl_mlir

def test_if():

    hcl.init()
    def absolute(A, B):
        with hcl.for_(0, A.shape[0], tag="C") as x:
            with hcl.for_(0, A.shape[1]) as y:
                with hcl.if_(A[x, y] >= 0):
                    B[x, y] = A[x, y]
                with hcl.else_():
                    B[x, y] = -A[x, y]

    A = hcl.placeholder((10, 20), name="A", dtype="float32")
    B = hcl.placeholder(A.shape, name="B", dtype="float32")
    s = hcl.create_schedule([A, B], absolute)
    C = absolute.C
    o, i = s[C].split(C.axis[0], factor=3)
    s[C].reorder(i, o)
    # test lower
    ir = hcl.lower(s)
    loops = hcl_mlir.get_affine_loop_nests(s.device_top)[0]
    assert "0 to 4" in str(loops[0]["body"])
    # test build
    f = hcl.build(s)
    a_np = np.random.random((A.shape))
    a_hcl = hcl.asarray(a_np, dtype="float32")
    b_hcl = hcl.asarray(np.zeros(B.shape), dtype="float32")
    f(a_hcl, b_hcl)
    b_np = np.abs(a_np)
    np.testing.assert_allclose(b_np, b_hcl.asnumpy())


def test_schedule_intra_stage():

    hcl.init()
    def popcount(A, B): # each element in A is a 32-bit integer
        with hcl.for_(0, A.shape[0], tag="C") as x:
            with hcl.for_(0, A.shape[1]) as y:
                B[x, y] = 0
                with hcl.for_(0, 32) as i:
                    B[x, y] += A[x, y][i]

    A = hcl.placeholder((10, 20))
    B = hcl.placeholder(A.shape)

    def test_unroll():
        s = hcl.create_schedule([A, B], popcount)
        C = popcount.C
        s[C].unroll(C.axis[0], factor=3)
        ir = hcl.lower(s)
        assert "unroll = 3" in str(ir)

    def test_reorder():
        s = hcl.create_schedule([A, B], popcount)
        C = popcount.C
        s[C].reorder(C.axis[1], C.axis[0])
        ir = hcl.lower(s)
        loops = hcl_mlir.get_affine_loop_nests(s.device_top)[0]
        assert "0 to 20" in str(loops[0]["body"])
        assert "0 to 10" in str(loops[1]["body"])

    def test_fuse():
        s = hcl.create_schedule([A, B], popcount)
        C = popcount.C
        s[C].fuse(C.axis[0], C.axis[1])
        ir = hcl.lower(s)
        loops = hcl_mlir.get_affine_loop_nests(s.device_top)[0]
        assert "0 to 200" in str(loops[0]["body"])

    def test_split():
        s = hcl.create_schedule([A, B], popcount)
        C = popcount.C
        s[C].split(C.axis[0], factor=3)
        ir = hcl.lower(s)
        loops = hcl_mlir.get_affine_loop_nests(s.device_top)[0]
        assert "0 to 4" in str(loops[0]["body"])
        assert "0 to min affine_map<(d0, d1) -> (3, -d0 + 10)>" in str(loops[1]["body"])
        assert "0 to 20" in str(loops[2]["body"])

    test_unroll()
    test_reorder()
    test_fuse()
    test_split()


def test_schedule_inter_stage():

    hcl.init()
    def popcount(A, B): # each element in A is a 32-bit integer
        C = hcl.compute(A.shape, lambda xx, yy: A[xx, yy] + 1, name="C")
        with hcl.for_(0, A.shape[0], tag="Out") as x:
            with hcl.for_(0, A.shape[1]) as y:
                B[x, y] = 0
                with hcl.for_(0, 32) as i:
                    B[x, y] += A[x, y][i]

    A = hcl.placeholder((10, 20))
    B = hcl.placeholder(A.shape)

    def test_compute_at():
        s = hcl.create_schedule([A, B], popcount)
        print(s.device_module)
        Out = popcount.Out
        s[popcount.C].compute_at(s[Out], Out.axis[1])
        ir = hcl.lower(s)
        loops = hcl_mlir.get_affine_loop_nests(s.device_top)[0]
        assert 'affine.store %2, %0[%arg2, %arg3] {to = "C"} : memref<10x20xi32>' in str(loops[1]["body"])
        assert "0 to 32" in str(loops[2]["body"])

    test_compute_at()


if __name__ == '__main__':
    test_if()
    test_schedule_intra_stage()
    test_schedule_inter_stage()
