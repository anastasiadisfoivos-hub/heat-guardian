#!/usr/bin/env python3
"""Talk to the 08_logger band over USB serial from the Mac and save what it sends.

Needs pyserial (once):  python3 -m pip install --user pyserial

  python3 capture.py dump                 # pull every file -> dump_<date>.txt (stops at "# DUMP DONE")
  python3 capture.py dumpnew              # only files not dumped before (+ events, min.bin)
  python3 capture.py dumpmin              # only the 1-minute file
  python3 capture.py time                 # set the band's clock to the Mac's clock, print stat
  python3 capture.py live --minutes 10    # record the live 1 Hz stream for 10 minutes
  python3 capture.py cmd "mark 4"         # send one command, show the reply for 3 s

The port is found automatically (/dev/cu.usbmodem*); use --port to choose. Close the Arduino Serial
Monitor first: only one program can hold the port. Then parse with parse_log.py.
"""
import argparse
import glob
import sys
import time

try:
    import serial
except ImportError:
    sys.exit("pyserial missing. In Terminal run:  python3 -m pip install --user pyserial")


def find_port():
    ports = sorted(glob.glob("/dev/cu.usbmodem*")) + sorted(glob.glob("/dev/ttyACM*"))
    if not ports:
        sys.exit("No band found. Plug the USB-C cable in (data cable), close the Serial Monitor, try again.")
    return ports[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["dump", "dumpnew", "dumpmin", "time", "live", "cmd"])
    ap.add_argument("text", nargs="?", default="")
    ap.add_argument("--port")
    ap.add_argument("--minutes", type=float, default=10)
    ap.add_argument("-o", "--out")
    a = ap.parse_args()
    port = a.port or find_port()
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = a.out or f"{a.what}_{stamp}.txt"
    s = serial.Serial(port, 115200, timeout=0.5)
    s.dtr = True
    time.sleep(1.0)
    s.reset_input_buffer()

    def send(cmd):
        s.write((cmd + "\n").encode())

    if a.what == "time":
        send(f"time {int(time.time())}")
        time.sleep(0.5)
        send("stat")
        t_end, done_markers = time.time() + 4, ()
    elif a.what in ("dump", "dumpnew", "dumpmin"):
        send("hex off")             # keep the dump clean; turned back on at the end (09 >= 0.9.17-demo-b7u: `hex`; `live` = LIVE demo)
        time.sleep(0.3)
        send("dump new" if a.what == "dumpnew" else a.what)
        t_end, done_markers = time.time() + 3600, ("# DUMP DONE", "# DUMP ABORTED", "# DUMP: storage")
    elif a.what == "live":
        send("hex on")              # 09 >= 0.9.17-demo-b7u (08_logger: use  cmd "live on")
        t_end, done_markers = time.time() + 60 * a.minutes, ()
    else:
        send(a.text)
        t_end, done_markers = time.time() + 3, ()
    n = 0
    last_print = time.time()
    with open(out, "w") as fh:
        while time.time() < t_end:
            line = s.readline().decode(errors="replace")
            if not line:
                continue
            fh.write(line if line.endswith("\n") else line + "\n")
            n += 1
            if a.what in ("time", "cmd") or line.startswith("# DUMP") or line.startswith("# END"):
                print(line.rstrip())
            if time.time() - last_print > 5 and a.what in ("dump", "dumpnew", "dumpmin", "live"):
                print(f"... {n} lines so far")
                last_print = time.time()
            if any(line.startswith(m) for m in done_markers):
                break
    if a.what in ("dump", "dumpnew", "dumpmin"):
        send("hex on")
    s.close()
    print(f"saved {n} lines to {out}")


if __name__ == "__main__":
    main()
