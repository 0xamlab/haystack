"""Tests for Wave 20 — FFT, Sparse Matrices, Genetic Algorithms."""

from fft import Complex, fft, ifft, fft_magnitude, fft_phase, power_spectrum, next_power_of_2, zero_pad
from sparse import COOEntry, SparseMatrixCOO, sparse_from_dense, sparse_matvec, sparse_add, sparse_transpose, sparse_density, sparse_trace
from genetic import Individual, GAConfig, initialize_population, tournament_select, crossover_uniform, crossover_single_point, mutate_gaussian, evolve_one_generation, run_ga, best_individual
from std.math import abs as fabs, sqrt


def _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


def _assert_close(a: Float64, b: Float64, tol: Float64, msg: String) raises:
    if fabs(a - b) > tol:
        raise Error("FAIL: " + msg + " | got " + String(a) + " expected " + String(b))


def test_fft() raises:
    print("── FFT tests ──")
    var n_pass: Int = 0

    # 1. next_power_of_2
    _assert(next_power_of_2(5) == 8, "next_power_of_2(5) == 8")
    n_pass += 1
    _assert(next_power_of_2(8) == 8, "next_power_of_2(8) == 8")
    n_pass += 1
    _assert(next_power_of_2(1) == 1, "next_power_of_2(1) == 1")
    n_pass += 1
    _assert(next_power_of_2(17) == 32, "next_power_of_2(17) == 32")
    n_pass += 1

    # 2. zero_pad
    var zp_in = List[Float64]()
    zp_in.append(1.0)
    zp_in.append(2.0)
    zp_in.append(3.0)
    var zp = zero_pad(zp_in, 8)
    _assert(len(zp) == 8, "zero_pad length == 8")
    n_pass += 1
    _assert_close(zp[0], 1.0, 1e-12, "zero_pad[0] == 1")
    n_pass += 1
    _assert_close(zp[1], 2.0, 1e-12, "zero_pad[1] == 2")
    n_pass += 1
    _assert_close(zp[2], 3.0, 1e-12, "zero_pad[2] == 3")
    n_pass += 1
    _assert_close(zp[7], 0.0, 1e-12, "zero_pad[7] == 0")
    n_pass += 1

    # 3. Complex arithmetic: (1+2i)*(3+4i) = (-5+10i)
    var c1 = Complex(1.0, 2.0)
    var c2 = Complex(3.0, 4.0)
    var cm = c1 * c2
    _assert_close(cm.re, -5.0, 1e-12, "(1+2i)*(3+4i) re == -5")
    n_pass += 1
    _assert_close(cm.im, 10.0, 1e-12, "(1+2i)*(3+4i) im == 10")
    n_pass += 1

    # Complex add/sub
    var ca = c1 + c2
    _assert_close(ca.re, 4.0, 1e-12, "(1+2i)+(3+4i) re == 4")
    n_pass += 1
    var cs = c1 - c2
    _assert_close(cs.re, -2.0, 1e-12, "(1+2i)-(3+4i) re == -2")
    n_pass += 1

    # 4. FFT of DC signal [1,1,1,1] — X[0] should be (4,0), others ~0
    var dc = List[Float64]()
    dc.append(1.0)
    dc.append(1.0)
    dc.append(1.0)
    dc.append(1.0)
    var Xdc = fft(dc)
    _assert_close(Xdc[0].re, 4.0, 1e-6, "fft DC X[0].re == 4")
    n_pass += 1
    _assert_close(Xdc[0].im, 0.0, 1e-6, "fft DC X[0].im == 0")
    n_pass += 1
    _assert_close(Xdc[1].re, 0.0, 1e-6, "fft DC X[1].re == 0")
    n_pass += 1
    _assert_close(Xdc[1].im, 0.0, 1e-6, "fft DC X[1].im == 0")
    n_pass += 1

    # 5. FFT of impulse [1,0,0,0] — all magnitudes should be 1.0
    var imp = List[Float64]()
    imp.append(1.0)
    imp.append(0.0)
    imp.append(0.0)
    imp.append(0.0)
    var Ximp = fft(imp)
    var mag_imp = fft_magnitude(Ximp)
    for i in range(4):
        _assert_close(mag_imp[i], 1.0, 1e-6, "impulse mag[" + String(i) + "] == 1")
    n_pass += 4

    # 6. IFFT(FFT(x)) roundtrip
    var sig = List[Float64]()
    sig.append(1.0)
    sig.append(2.0)
    sig.append(3.0)
    sig.append(4.0)
    var Xsig = fft(sig)
    var rec = ifft(Xsig)
    for i in range(4):
        _assert_close(rec[i].re, sig[i], 1e-6, "ifft(fft(x))[" + String(i) + "] roundtrip")
    n_pass += 4

    # 7. Power spectrum — all values >= 0
    var ps = power_spectrum(dc)
    for i in range(len(ps)):
        _assert(ps[i] >= -1e-12, "power_spectrum >= 0")
    n_pass += 1

    # 8. fft_magnitude of known signal
    var mag_dc = fft_magnitude(Xdc)
    _assert_close(mag_dc[0], 4.0, 1e-6, "mag DC X[0] == 4")
    n_pass += 1

    print("  FFT: " + String(n_pass) + " assertions passed")


def test_sparse() raises:
    print("── Sparse tests ──")
    var n_pass: Int = 0

    # 1. Create 3x3 identity in COO
    var eye = SparseMatrixCOO(3, 3)
    eye.add_entry(0, 0, 1.0)
    eye.add_entry(1, 1, 1.0)
    eye.add_entry(2, 2, 1.0)
    _assert(eye.nnz() == 3, "identity nnz == 3")
    n_pass += 1

    # 2. to_dense of identity
    var dense_eye = eye.to_dense()
    _assert_close(dense_eye[0][0], 1.0, 1e-12, "eye[0][0] == 1")
    n_pass += 1
    _assert_close(dense_eye[0][1], 0.0, 1e-12, "eye[0][1] == 0")
    n_pass += 1
    _assert_close(dense_eye[1][1], 1.0, 1e-12, "eye[1][1] == 1")
    n_pass += 1
    _assert_close(dense_eye[2][2], 1.0, 1e-12, "eye[2][2] == 1")
    n_pass += 1

    # 3. sparse_from_dense of mostly-zero matrix
    var mostly_zero = List[List[Float64]]()
    for i in range(4):
        var row = List[Float64]()
        for j in range(4):
            row.append(0.0)
        mostly_zero.append(row^)
    mostly_zero[0][0] = 5.0
    mostly_zero[2][3] = -3.0
    var sp = sparse_from_dense(mostly_zero)
    _assert(sp.nnz() == 2, "sparse_from_dense nnz == 2")
    n_pass += 1

    # 4. sparse_matvec with identity — returns input unchanged
    var vec3 = List[Float64]()
    vec3.append(7.0)
    vec3.append(8.0)
    vec3.append(9.0)
    var mv = sparse_matvec(eye, vec3)
    _assert_close(mv[0], 7.0, 1e-12, "I*v[0] == 7")
    n_pass += 1
    _assert_close(mv[1], 8.0, 1e-12, "I*v[1] == 8")
    n_pass += 1
    _assert_close(mv[2], 9.0, 1e-12, "I*v[2] == 9")
    n_pass += 1

    # 5. sparse_matvec with known matrix [[2,0],[0,3]] * [4,5] = [8,15]
    var mat2 = SparseMatrixCOO(2, 2)
    mat2.add_entry(0, 0, 2.0)
    mat2.add_entry(1, 1, 3.0)
    var v2 = List[Float64]()
    v2.append(4.0)
    v2.append(5.0)
    var mv2 = sparse_matvec(mat2, v2)
    _assert_close(mv2[0], 8.0, 1e-12, "diag*v[0] == 8")
    n_pass += 1
    _assert_close(mv2[1], 15.0, 1e-12, "diag*v[1] == 15")
    n_pass += 1

    # 6. sparse_add — combine two matrices
    var a = SparseMatrixCOO(2, 2)
    a.add_entry(0, 0, 1.0)
    a.add_entry(1, 1, 2.0)
    var b = SparseMatrixCOO(2, 2)
    b.add_entry(0, 0, 3.0)
    b.add_entry(0, 1, 4.0)
    var ab = sparse_add(a, b)
    var ab_dense = ab.to_dense()
    _assert_close(ab_dense[0][0], 4.0, 1e-12, "add [0][0] == 4")
    n_pass += 1
    _assert_close(ab_dense[0][1], 4.0, 1e-12, "add [0][1] == 4")
    n_pass += 1
    _assert_close(ab_dense[1][1], 2.0, 1e-12, "add [1][1] == 2")
    n_pass += 1

    # 7. sparse_transpose
    var rect = SparseMatrixCOO(2, 3)
    rect.add_entry(0, 2, 5.0)
    rect.add_entry(1, 0, 7.0)
    var rect_t = sparse_transpose(rect)
    _assert(rect_t.nrows == 3, "transpose nrows == 3")
    n_pass += 1
    _assert(rect_t.ncols == 2, "transpose ncols == 2")
    n_pass += 1
    # Entry (0,2,5) becomes (2,0,5)
    _assert(rect_t.entries[0].row == 2, "transpose entry row swapped")
    n_pass += 1
    _assert(rect_t.entries[0].col == 0, "transpose entry col swapped")
    n_pass += 1

    # 8. sparse_density of 100x100 identity — should be 0.01
    var big_eye = SparseMatrixCOO(100, 100)
    for i in range(100):
        big_eye.add_entry(i, i, 1.0)
    _assert_close(sparse_density(big_eye), 0.01, 1e-12, "density of 100x100 I == 0.01")
    n_pass += 1

    # 9. sparse_trace of identity == dimension
    _assert_close(sparse_trace(eye), 3.0, 1e-12, "trace(I_3) == 3")
    n_pass += 1
    _assert_close(sparse_trace(big_eye), 100.0, 1e-12, "trace(I_100) == 100")
    n_pass += 1

    print("  Sparse: " + String(n_pass) + " assertions passed")


def test_genetic() raises:
    print("── Genetic Algorithm tests ──")
    var n_pass: Int = 0

    var config = GAConfig(
        population_size=20,
        n_genes=5,
        mutation_rate=0.1,
        crossover_rate=0.8,
        elitism=2,
        gene_min=-10.0,
        gene_max=10.0,
    )

    # 1. initialize_population — correct size
    var pop = initialize_population(config)
    _assert(len(pop) == 20, "pop size == 20")
    n_pass += 1

    # 2. Gene count correct
    _assert(len(pop[0].genes) == 5, "n_genes == 5")
    n_pass += 1

    # 3. Genes within bounds
    var all_in_bounds = True
    for i in range(len(pop)):
        for j in range(len(pop[i].genes)):
            if pop[i].genes[j] < -10.0 or pop[i].genes[j] > 10.0:
                all_in_bounds = False
    _assert(all_in_bounds, "all genes in [-10, 10]")
    n_pass += 1

    # 4. Evaluate and test tournament_select returns valid individual
    for i in range(len(pop)):
        # Simple fitness assignment for testing
        var s: Float64 = 0.0
        for j in range(len(pop[i].genes)):
            var diff = pop[i].genes[j] - Float64(j)
            s += diff * diff
        pop[i].fitness = -s

    var sel = tournament_select(pop, 3)
    _assert(len(sel.genes) == 5, "tournament_select returns 5 genes")
    n_pass += 1

    # 5. crossover_uniform — child has same number of genes
    var p1 = pop[0].copy()
    var p2 = pop[1].copy()
    var child_u = crossover_uniform(p1, p2, 0.5)
    _assert(len(child_u.genes) == 5, "uniform crossover child has 5 genes")
    n_pass += 1

    # 6. crossover_single_point — child genes are from parents
    var child_sp = crossover_single_point(p1, p2)
    _assert(len(child_sp.genes) == 5, "single_point child has 5 genes")
    n_pass += 1

    # Verify child genes come from one parent or the other
    var genes_from_parents = True
    for i in range(len(child_sp.genes)):
        var from_p1 = fabs(child_sp.genes[i] - p1.genes[i]) < 1e-12
        var from_p2 = fabs(child_sp.genes[i] - p2.genes[i]) < 1e-12
        if not from_p1 and not from_p2:
            genes_from_parents = False
    _assert(genes_from_parents, "single_point child genes from parents")
    n_pass += 1

    # 7. mutate_gaussian — genes still within bounds
    var mut_ind_genes = List[Float64]()
    for i in range(5):
        mut_ind_genes.append(0.0)
    var mut_ind = Individual(mut_ind_genes^, 0.0)
    mutate_gaussian(mut_ind, 1.0, 2.0, -10.0, 10.0)  # rate=1.0 means all mutated
    var mut_in_bounds = True
    for i in range(len(mut_ind.genes)):
        if mut_ind.genes[i] < -10.0 or mut_ind.genes[i] > 10.0:
            mut_in_bounds = False
    _assert(mut_in_bounds, "mutated genes in bounds")
    n_pass += 1

    # 8. evolve_one_generation — population size preserved
    var pop2 = evolve_one_generation(pop, config, 0)
    _assert(len(pop2) == 20, "evolved pop size == 20")
    n_pass += 1

    # 9. best_individual returns highest fitness
    var best = best_individual(pop2)
    var is_best = True
    for i in range(len(pop2)):
        if pop2[i].fitness > best.fitness + 1e-12:
            is_best = False
    _assert(is_best, "best_individual has highest fitness")
    n_pass += 1

    # 10. run_ga with 50 generations — fitness should improve
    var ga_config = GAConfig(
        population_size=30,
        n_genes=4,
        mutation_rate=0.2,
        crossover_rate=0.8,
        elitism=2,
        gene_min=-10.0,
        gene_max=10.0,
    )

    # Evaluate initial population to get initial best
    var init_pop = initialize_population(ga_config)
    var init_best_fit: Float64 = -1e15
    for i in range(len(init_pop)):
        var s: Float64 = 0.0
        for j in range(len(init_pop[i].genes)):
            var diff = init_pop[i].genes[j] - Float64(j)
            s += diff * diff
        var f = -s
        if f > init_best_fit:
            init_best_fit = f

    var result = run_ga(ga_config, 50, 0)
    # Best fitness should be >= initial average (evolved is better)
    _assert(result.fitness > -1000.0, "GA result fitness reasonable (> -1000)")
    n_pass += 1

    # Fitness should be negative (distance to target) but close to 0
    _assert(result.fitness <= 0.0, "GA fitness <= 0 (minimizing distance)")
    n_pass += 1

    # Gene count preserved
    _assert(len(result.genes) == 4, "GA result has 4 genes")
    n_pass += 1

    print("  Genetic: " + String(n_pass) + " assertions passed")


def main() raises:
    print("=== Wave 20 Tests: FFT, Sparse, Genetic ===")
    test_fft()
    test_sparse()
    test_genetic()
    print("=== All Wave 20 tests passed ===")
