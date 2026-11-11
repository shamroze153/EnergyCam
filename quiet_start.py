"""Start a script again with the video decoder told to keep quiet. Windows only.

The decoder that reads the cameras is a separate library, and on Windows it
keeps its own copy of the environment and its own idea of where the console
is, both taken when the process starts. So the two ways of quietening it from
inside Python -- setting OPENCV_FFMPEG_LOGLEVEL before importing cv2, and
muffled() pointing the error stream at nothing -- work here on Linux and do
nothing at all on the laptop. Hundreds of "PPS id out of range" lines in a
scan, a verify and the loop itself, after both were in place, are how we know.

What the library does read is the environment the process was born with. So
the script starts itself once more with the setting already in place, waits
for that copy to finish, and leaves with its exit code. The copy is told it
is the copy, so it does not do the same again.

Call it at the very top of a script, before cv2 is imported, and only when
the file is being run rather than imported:

    if __name__ == "__main__":
        import quiet_start
        quiet_start.relaunch()
"""
import os
import subprocess
import sys

MARK = "ENERGYCAM_QUIET_CHILD"

# 0 is ffmpeg's "panic" level: everything quieter than a crash is dropped.
# The true silence value is -8, but one build here reads the setting as an
# unsigned number and refuses a negative, and 0 does the job anyway.
LEVEL = "0"


def relaunch():
    if os.name != "nt" or os.environ.get(MARK):
        return
    env = dict(os.environ)
    env[MARK] = "1"
    env.setdefault("OPENCV_FFMPEG_LOGLEVEL", LEVEL)
    try:
        child = subprocess.Popen([sys.executable] + sys.argv, env=env)
    except OSError:
        return          # run here instead: noisy, but running
    while True:
        try:
            code = child.wait()
            break
        except KeyboardInterrupt:
            # Ctrl+C reaches both copies. The copy stops itself the way it
            # always has; this one waits for it rather than leaving first and
            # handing the prompt back while the copy is still printing.
            continue
    sys.exit(code)
