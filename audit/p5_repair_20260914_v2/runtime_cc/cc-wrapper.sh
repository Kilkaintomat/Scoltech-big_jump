#!/usr/bin/env bash
export LD_LIBRARY_PATH="/beegfs/shared/opt/rh/gcc-12.2.0/lib64:/beegfs/shared/opt/rh/devtoolset-11/root/usr/lib64:${LD_LIBRARY_PATH:-}"
exec /beegfs/shared/opt/rh/gcc-12.2.0/bin/gcc -fuse-ld=bfd -B/beegfs/shared/opt/rh/gcc-12.2.0/bin/ -B/beegfs/shared/opt/rh/devtoolset-11/root/usr/bin/ -isystem /usr/include/x86_64-linux-gnu -B/usr/lib/x86_64-linux-gnu/ -L/usr/lib/x86_64-linux-gnu "$@"
