from std.python import Python

def main() raises:
    var sys_m = Python.import_module("sys")
    var io_m = Python.import_module("io")
    var buf = io_m.StringIO()
    sys_m.stdout = buf
    print("hello-from-mojo")
    sys_m.__stdout__.write("CAPTURED=" + String(buf.getvalue()) + "\n")
