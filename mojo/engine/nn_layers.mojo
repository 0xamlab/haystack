"""
nn_layers.mojo — Neural network layer primitives. Zero Python imports.

Replaces torch.nn basics with pure Mojo implementations of dense layers,
activations, loss functions, normalization, and weight initialization.

Public API:
  dense_forward        — Dense (fully connected) layer forward pass
  relu                 — ReLU activation
  sigmoid_activation   — Sigmoid activation
  tanh_activation      — Tanh activation
  softmax_layer        — Numerically stable softmax
  mse_loss             — Mean squared error loss
  cross_entropy_loss   — Binary cross entropy loss
  dropout              — Random dropout with scaling
  batch_norm           — Batch normalization
  leaky_relu           — Leaky ReLU activation
  init_weights_xavier  — Xavier/Glorot uniform initialization
"""
from std.math import exp, log, sqrt, tanh, abs as fabs
from std.random import random_float64


# Ceiling on wire-supplied layer dimensions: bounds the n_in*n_out allocation.
comptime MAX_NN_DIM: Int = 1024


# ── dense_forward ────────────────────────────────────────────────────────────


fn dense_forward(
    input: List[Float64],
    weights: List[List[Float64]],
    bias: List[Float64],
) -> List[Float64]:
    """Dense layer: output = W*input + bias.
    weights is [n_out × n_in]."""
    var n_out = len(weights)
    # A short bias or a weight row wider than input would be read past its
    # end below (uncatchable abort).
    if len(bias) < n_out:
        return List[Float64]()
    for i in range(n_out):
        if len(weights[i]) > len(input):
            return List[Float64]()
    var result = List[Float64]()
    for i in range(n_out):
        var s: Float64 = bias[i]
        for j in range(len(weights[i])):
            s += weights[i][j] * input[j]
        result.append(s)
    return result^


# ── relu ─────────────────────────────────────────────────────────────────────


fn relu(x: List[Float64]) -> List[Float64]:
    """ReLU activation: max(0, x)."""
    var result = List[Float64]()
    for i in range(len(x)):
        if x[i] > 0.0:
            result.append(x[i])
        else:
            result.append(0.0)
    return result^


# ── sigmoid_activation ───────────────────────────────────────────────────────


fn sigmoid_activation(x: List[Float64]) -> List[Float64]:
    """Sigmoid activation: 1 / (1 + exp(-x))."""
    var result = List[Float64]()
    for i in range(len(x)):
        result.append(1.0 / (1.0 + exp(-x[i])))
    return result^


# ── tanh_activation ──────────────────────────────────────────────────────────


fn tanh_activation(x: List[Float64]) -> List[Float64]:
    """Tanh activation."""
    var result = List[Float64]()
    for i in range(len(x)):
        result.append(tanh(x[i]))
    return result^


# ── softmax_layer ────────────────────────────────────────────────────────────


fn softmax_layer(x: List[Float64]) -> List[Float64]:
    """Numerically stable softmax: exp(x-max) / sum(exp(x-max))."""
    var n = len(x)
    # x[0] below would read past the end (uncatchable abort); the softmax
    # of nothing is nothing.
    if n == 0:
        return List[Float64]()
    var max_val = x[0]
    for i in range(1, n):
        if x[i] > max_val:
            max_val = x[i]
    var exps = List[Float64]()
    var total: Float64 = 0.0
    for i in range(n):
        var e = exp(x[i] - max_val)
        exps.append(e)
        total += e
    var result = List[Float64]()
    for i in range(n):
        result.append(exps[i] / total)
    return result^


# ── mse_loss ─────────────────────────────────────────────────────────────────


fn mse_loss(predicted: List[Float64], actual: List[Float64]) -> Float64:
    """Mean squared error loss: sum((p-a)^2) / n."""
    var n = len(predicted)
    # A short actual would be read past its end below, and n == 0 would zero
    # the mean's divisor (uncatchable abort / non-finite result).
    if n == 0 or len(actual) < n:
        return 0.0
    var total: Float64 = 0.0
    for i in range(n):
        var d = predicted[i] - actual[i]
        total += d * d
    return total / Float64(n)


# ── cross_entropy_loss ───────────────────────────────────────────────────────


fn cross_entropy_loss(predicted: List[Float64], actual: List[Float64]) -> Float64:
    """Binary cross entropy: -sum(y*log(p) + (1-y)*log(1-p)) / n."""
    var n = len(predicted)
    # A short actual would be read past its end below, and n == 0 would zero
    # the mean's divisor (uncatchable abort / non-finite result).
    if n == 0 or len(actual) < n:
        return 0.0
    var total: Float64 = 0.0
    var eps: Float64 = 1e-15
    for i in range(n):
        var p = predicted[i]
        if p < eps:
            p = eps
        if p > 1.0 - eps:
            p = 1.0 - eps
        total += actual[i] * log(p) + (1.0 - actual[i]) * log(1.0 - p)
    return -total / Float64(n)


# ── dropout ──────────────────────────────────────────────────────────────────


fn dropout(x: List[Float64], rate: Float64) -> List[Float64]:
    """Random dropout: zero out with probability `rate`, scale by 1/(1-rate)."""
    var result = List[Float64]()
    var scale = 1.0 / (1.0 - rate)
    for i in range(len(x)):
        if random_float64() < rate:
            result.append(0.0)
        else:
            result.append(x[i] * scale)
    return result^


# ── batch_norm ───────────────────────────────────────────────────────────────


fn batch_norm(
    x: List[Float64], gamma: Float64 = 1.0, beta: Float64 = 0.0
) -> List[Float64]:
    """Batch normalization: (x - mean)/std * gamma + beta."""
    var n = len(x)
    var mean: Float64 = 0.0
    for i in range(n):
        mean += x[i]
    mean /= Float64(n)
    var variance: Float64 = 0.0
    for i in range(n):
        var d = x[i] - mean
        variance += d * d
    variance /= Float64(n)
    var std = sqrt(variance + 1e-8)
    var result = List[Float64]()
    for i in range(n):
        result.append((x[i] - mean) / std * gamma + beta)
    return result^


# ── leaky_relu ───────────────────────────────────────────────────────────────


fn leaky_relu(x: List[Float64], alpha: Float64 = 0.01) -> List[Float64]:
    """Leaky ReLU: x if x > 0 else alpha*x."""
    var result = List[Float64]()
    for i in range(len(x)):
        if x[i] > 0.0:
            result.append(x[i])
        else:
            result.append(alpha * x[i])
    return result^


# ── init_weights_xavier ──────────────────────────────────────────────────────


fn init_weights_xavier(n_in: Int, n_out: Int) -> List[List[Float64]]:
    """Xavier/Glorot uniform init: U(-limit, limit) where limit=sqrt(6/(n_in+n_out))."""
    # Non-positive dims zero the limit's divisor; huge dims are an allocation
    # bomb, so clamp the wire-supplied counts.
    if n_in <= 0 or n_out <= 0:
        return List[List[Float64]]()
    var nin = n_in
    var nout = n_out
    if nin > MAX_NN_DIM:
        nin = MAX_NN_DIM
    if nout > MAX_NN_DIM:
        nout = MAX_NN_DIM
    var limit = sqrt(6.0 / Float64(nin + nout))
    var weights = List[List[Float64]]()
    for _ in range(nout):
        var row = List[Float64]()
        for _ in range(nin):
            var r = random_float64()  # [0, 1)
            row.append(r * 2.0 * limit - limit)
        weights.append(row^)
    return weights^
