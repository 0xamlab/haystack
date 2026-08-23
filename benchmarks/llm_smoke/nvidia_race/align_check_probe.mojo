# align_check_probe.mojo — verify the DEVICE-side base alignment of DeviceBuffer allocations
# and the offset arithmetic the hot kernels rely on, so the `load[width=4, alignment=16]`
# annotation is provably safe. Runs on-GPU.
from std.sys import has_accelerator, is_defined
from max.gpu.host import DeviceBuffer, DeviceContext

def main() raises:
    @parameter
    if not (is_defined["ALGENTA_GPU"]() and is_defined["ALGENTA_CUDA"]()):
        print("needs -D ALGENTA_GPU -D ALGENTA_CUDA")
        return
    else:
        if not has_accelerator():
            print("align_check_probe: no accelerator")
            return
        var ctx = DeviceContext()
        # Several allocations of the sizes/dtypes the hot kernels use.
        var a = ctx.enqueue_create_buffer[DType.float32](1024)
        var b = ctx.enqueue_create_buffer[DType.float32](3072)
        var c = ctx.enqueue_create_buffer[DType.float32](1)   # tiny
        var d = ctx.enqueue_create_buffer[DType.float32](4096 * 1024)
        var ai = Int(a.unsafe_ptr())
        var bi = Int(b.unsafe_ptr())
        var ci = Int(c.unsafe_ptr())
        var di = Int(d.unsafe_ptr())
        print("base alignment (bytes) of fresh DeviceBuffer allocations:")
        print("  a(1024 f32):   addr%", 16, "=", ai % 16, " | %256 =", ai % 256)
        print("  b(3072 f32):   addr%", 16, "=", bi % 16, " | %256 =", bi % 256)
        print("  c(1 f32):      addr%", 16, "=", ci % 16, " | %256 =", ci % 256)
        print("  d(4M f32):     addr%", 16, "=", di % 16, " | %256 =", di % 256)
        # The packed3 GEMV offset arithmetic: base + row*words_per_row + t/3, words_per_row
        # a multiple of 4 words and t a multiple of 12 elements. Confirm the element->word
        # offsets the kernel computes stay 4-word (16B) aligned.
        var k = 1024
        var k_pack = ((k + 11) // 12) * 12
        var words_per_row = k_pack // 3
        print("packed3 k=1024: k_pack", k_pack, "words_per_row", words_per_row,
              "words%4", words_per_row % 4, "(0 => row bases 16B aligned)")
        var k2 = 3072
        var kp2 = ((k2 + 11) // 12) * 12
        print("packed3 k=3072: k_pack", kp2, "words_per_row", kp2 // 3,
              "words%4", (kp2 // 3) % 4)
        print("align_check_probe: done")
