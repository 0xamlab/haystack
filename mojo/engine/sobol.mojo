"""
Sobol quasi-random sequence generator (Joe-Kuo tables, up to 8 dimensions).
Falls back to random_float64() for dimensions > 8.
"""
from std.random import random_float64


struct SobolGen:
    var dim:   Int
    var count: Int
    var v:     List[List[Int]]
    var state: List[Int]          # XOR accumulator per dimension

    fn __init__(out self, dim: Int):
        self.dim   = dim
        self.count = 0
        self.v     = List[List[Int]](capacity=dim)
        self.state = List[Int](capacity=dim)
        for _ in range(dim):
            self.state.append(0)

        # Dimension 1: powers of 2
        var d1 = List[Int](capacity=32)
        for i in range(32): d1.append(1 << (31-i))
        self.v.append(d1.copy())

        # Dimensions 2-8: Joe-Kuo direction numbers
        var tbl = List[List[Int]]()
        var t2 = List[Int](); t2.append(1); t2.append(0); t2.append(1); tbl.append(t2.copy())
        var t3 = List[Int](); t3.append(2); t3.append(1); t3.append(1); t3.append(1); tbl.append(t3.copy())
        var t4 = List[Int](); t4.append(3); t4.append(1); t4.append(1); t4.append(1); t4.append(1); tbl.append(t4.copy())
        var t5 = List[Int](); t5.append(3); t5.append(2); t5.append(1); t5.append(1); t5.append(3); tbl.append(t5.copy())
        var t6 = List[Int](); t6.append(4); t6.append(1); t6.append(1); t6.append(1); t6.append(3); t6.append(3); tbl.append(t6.copy())
        var t7 = List[Int](); t7.append(4); t7.append(4); t7.append(1); t7.append(1); t7.append(5); t7.append(5); tbl.append(t7.copy())
        var t8 = List[Int](); t8.append(5); t8.append(2); t8.append(1); t8.append(1); t8.append(5); t8.append(5); t8.append(17); tbl.append(t8.copy())

        for d in range(1, min(dim, 8)):
            var row = tbl[d-1].copy()
            var s   = row[0]; var a = row[1]
            var vd  = List[Int](capacity=32)
            for i in range(s):
                vd.append(row[2+i] << (31-i))
            for i in range(s, 32):
                var vi = vd[i-s] ^ (vd[i-s] >> s)
                for k in range(1, s):
                    if (a >> (s-1-k)) & 1: vi ^= vd[i-k]
                vd.append(vi)
            self.v.append(vd.copy())

        # Pad remaining dimensions by repeating dim-1
        while len(self.v) < dim:
            self.v.append(self.v[0].copy())

    fn next_point(mut self) -> List[Float64]:
        var n = self.count; self.count += 1
        # Gray-code: find position of rightmost zero bit of n
        var c = 0; var tmp = n
        while (tmp & 1) == 1:
            tmp >>= 1
            c += 1
        var pt = List[Float64](capacity=self.dim)
        var norm = Float64(1 << 32)      # direction numbers span bits 0-31 → divide by 2^32
        for d in range(self.dim):
            if c < len(self.v[d]):
                self.state[d] ^= self.v[d][c]
            pt.append(
                Float64(self.state[d]) / norm
                if c < len(self.v[d]) else random_float64()
            )
        return pt^
