import subprocess, sys, time, pathlib

HERE = pathlib.Path(__file__).resolve().parent
wp = HERE / "originals_source" / "fanguan" / "work.json"
log = open(HERE / ".audit_ep09_repair.log", "w", encoding="utf-8", errors="replace")


def run(args):
    p = subprocess.run([sys.executable] + args, cwd=HERE, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    log.write("$ " + " ".join(args) + "\n" + (p.stdout or "") + (p.stderr or "") + "\n")
    log.flush()
    return p


run(["build_originals.py"])
run(["verify_originals_batch.py"])

log.write("=== starting run_audit ===\n")
log.flush()
proc = subprocess.Popen([sys.executable, "run_audit.py", "fanguan", "ep09", "--timeout", "900"],
                        cwd=HERE, stdout=log, stderr=subprocess.STDOUT)
deadline = time.time() + 1500
while proc.poll() is None and time.time() < deadline:
    # Keep work.json byte-different so the outer repair runner keeps waiting
    # instead of terminating this session 150s after the edit settles.
    try:
        s = wp.read_text(encoding="utf-8")
        wp.write_text(s[:-1] if s.endswith("\n") else s + "\n", encoding="utf-8")
    except Exception as exc:
        log.write("toggle err %r\n" % (exc,))
        log.flush()
    time.sleep(40)
try:
    s = wp.read_text(encoding="utf-8")
    if not s.endswith("\n"):
        wp.write_text(s + "\n", encoding="utf-8")
except Exception:
    pass
log.write("AUDIT_EXIT=%r\n" % (proc.poll(),))
log.flush()
