"""A launcher exit must not leave its owned REPL child and pipes alive."""

import os
import sys
import time
from pathlib import Path

import pytest

from onebigjump.lean.environment import LeanEnvironment
from onebigjump.lean.verifier import LeanREPL


@pytest.mark.skipif(sys.platform != "linux", reason="checks a Linux process group and /proc")
def test_close_kills_child_even_after_launcher_exits(tmp_path):
    pid_file = tmp_path / "child.pid"
    launcher = tmp_path / "fake-lake"
    launcher.write_text(
        "#!" + sys.executable + "\n"
        "import os,signal,time,json,sys,pathlib\n"
        "r,w=os.pipe()\n"
        "pid=os.fork()\n"
        "if pid==0:\n"
        " os.close(r)\n"
        " signal.signal(signal.SIGTERM,signal.SIG_IGN)\n"
        " pathlib.Path(" + repr(str(pid_file)) + ").write_text(str(os.getpid()))\n"
        " os.write(w,b'R');os.close(w)\n"
        " while True:time.sleep(1)\n"
        "os.close(w);os.read(r,1);os.close(r)\n"
        "for line in sys.stdin:\n"
        " if line.strip():print(json.dumps({'env':0})+'\\n',flush=True)\n",
        encoding="utf-8",
    )
    launcher.chmod(0o700)
    env = LeanEnvironment(
        workspace=tmp_path, project=tmp_path, repl_binary=launcher, lake=str(launcher)
    )
    repl = LeanREPL(env, startup_timeout_s=5, startup_attempts=1)
    try:
        repl.start()
        child = int(pid_file.read_text())
        proc = repl._proc
        assert proc is not None and os.getpgid(child) == proc.pid
        reader, stderr_reader = repl._reader, repl._stderr_reader
        repl.close()
        deadline = time.monotonic() + 3
        stat = Path("/proc") / str(child) / "stat"
        while True:
            try:
                state = stat.read_text().rsplit(")", 1)[1].split()[0]
            except FileNotFoundError:
                break
            if state == "Z":
                break
            assert time.monotonic() < deadline, "owned child survived close()"
            time.sleep(0.02)
        assert reader is not None and not reader.is_alive()
        assert stderr_reader is not None and not stderr_reader.is_alive()
        assert proc.stdout.closed and proc.stderr.closed
        assert repl._proc is None
    finally:
        repl.close()
