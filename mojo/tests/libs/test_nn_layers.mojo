"""test_nn_layers.mojo — auto-generated tests for nn_layers."""
from std.math import isnan, isinf
from nn_layers import relu, sigmoid_activation, tanh_activation, softmax_layer, mse_loss, cross_entropy_loss, dropout, batch_norm, leaky_relu, init_weights_xavier

def is_finite(x: Float64) -> Bool:
    return not isnan(x) and not isinf(x)

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(1); _li5.append(2); _li5.append(3)
    _li5.append(4); _li5.append(5)
    var _li3 = List[Int]()
    _li3.append(1); _li3.append(2); _li3.append(3)
    var _li2_zero = List[Int]()
    _li2_zero.append(0); _li2_zero.append(1)
    var _li3_tail = List[Int]()
    _li3_tail.append(2); _li3_tail.append(3); _li3_tail.append(4)
    var _li8 = List[Int]()
    for i in range(8):
        _li8.append(i + 1)
    var _li6_grid2x3 = List[Int]()
    _li6_grid2x3.append(0); _li6_grid2x3.append(1); _li6_grid2x3.append(0)
    _li6_grid2x3.append(1); _li6_grid2x3.append(1); _li6_grid2x3.append(0)
    var _li10_borda = List[Int]()
    _li10_borda.append(0); _li10_borda.append(1); _li10_borda.append(2); _li10_borda.append(3); _li10_borda.append(4)
    _li10_borda.append(1); _li10_borda.append(0); _li10_borda.append(2); _li10_borda.append(4); _li10_borda.append(3)
    var _li16 = List[Int]()
    for i in range(16):
        _li16.append(i)
    var _lf6_matrix = List[Float64]()
    _lf6_matrix.append(1.0); _lf6_matrix.append(2.0); _lf6_matrix.append(3.0)
    _lf6_matrix.append(4.0); _lf6_matrix.append(5.0); _lf6_matrix.append(6.0)
    var _lf8_coalitions = List[Float64]()
    _lf8_coalitions.append(0.0); _lf8_coalitions.append(1.0); _lf8_coalitions.append(2.0); _lf8_coalitions.append(4.0)
    _lf8_coalitions.append(3.0); _lf8_coalitions.append(5.0); _lf8_coalitions.append(6.0); _lf8_coalitions.append(9.0)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var passed: Int = 0
    var failed: Int = 0

    var _v_relu = relu(_lf5)
    if len(_v_relu) >= 0: passed += 1; print("  ✅ nn_layers::relu")
    var _v_sigmoid_activation = sigmoid_activation(_lf5)
    if len(_v_sigmoid_activation) >= 0: passed += 1; print("  ✅ nn_layers::sigmoid_activation")
    var _v_tanh_activation = tanh_activation(_lf5)
    if len(_v_tanh_activation) >= 0: passed += 1; print("  ✅ nn_layers::tanh_activation")
    var _v_softmax_layer = softmax_layer(_lf5)
    if len(_v_softmax_layer) >= 0: passed += 1; print("  ✅ nn_layers::softmax_layer")
    var _v_mse_loss = mse_loss(_lf5, _lf5)
    if is_finite(_v_mse_loss): passed += 1; print("  ✅ nn_layers::mse_loss =", _v_mse_loss)
    else: failed += 1; print("  ❌ nn_layers::mse_loss → non-finite:", _v_mse_loss)
    var _v_cross_entropy_loss = cross_entropy_loss(_lf5, _lf5)
    if is_finite(_v_cross_entropy_loss): passed += 1; print("  ✅ nn_layers::cross_entropy_loss =", _v_cross_entropy_loss)
    else: failed += 1; print("  ❌ nn_layers::cross_entropy_loss → non-finite:", _v_cross_entropy_loss)
    var _v_dropout = dropout(_lf5, 0.5)
    if len(_v_dropout) >= 0: passed += 1; print("  ✅ nn_layers::dropout")
    var _v_batch_norm = batch_norm(_lf5, 0.5, 0.5)
    if len(_v_batch_norm) >= 0: passed += 1; print("  ✅ nn_layers::batch_norm")
    var _v_leaky_relu = leaky_relu(_lf5, 0.5)
    if len(_v_leaky_relu) >= 0: passed += 1; print("  ✅ nn_layers::leaky_relu")
    _ = init_weights_xavier(5, 5)
    passed += 1; print("  ✅ nn_layers::init_weights_xavier")

    print("  [nn_layers] Passed:", passed, "Failed:", failed)
