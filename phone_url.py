"""Print the address to type into a phone to reach the dashboard.

Streamlit prints a "Network URL", but this laptop has two networks -- the
cable to the camera VLAN (192.168.67.x) and the office WiFi -- and Streamlit
picks one of them without knowing which. If it picks the camera VLAN, the
address it prints is one no phone can reach, and the obvious conclusion is
that the dashboard does not work on a phone. It does; the address was wrong.

So: every IPv4 address this machine answers on, with the camera VLAN marked
as the one that will not work from a phone.

    python phone_url.py [port]
"""
import socket
import subprocess
import sys

CAMERA_VLAN = "192.168.67."


def routed_address():
    """The address this machine would answer on for ordinary traffic.

    No packet is sent: connecting a UDP socket only picks a route, and the
    local end of that choice is the address. It is here because on a machine
    whose hostname resolves to 127.0.0.1 -- which is most of them -- the
    name-based lookup below finds nothing at all.
    """
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("198.51.100.1", 9))     # reserved, routed nowhere
        return probe.getsockname()[0]
    except OSError:
        return None
    finally:
        probe.close()


def addresses():
    """Every IPv4 this machine holds, without asking the network anything."""
    found = set()
    routed = routed_address()
    if routed:
        found.add(routed)
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None,
                                       socket.AF_INET):
            found.add(info[4][0])
    except socket.gaierror:
        pass
    # getaddrinfo on Windows often returns only one of several adapters, so
    # the real list comes from ipconfig when it is there.
    if sys.platform == "win32":
        try:
            out = subprocess.run(["ipconfig"], capture_output=True, text=True,
                                 timeout=10).stdout
            for line in out.splitlines():
                if "IPv4" in line and ":" in line:
                    found.add(line.split(":")[-1].strip())
        except (OSError, subprocess.SubprocessError):
            pass
    return sorted(a for a in found
                  if a and not a.startswith("127.") and a.count(".") == 3)


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else "8501"
    found = addresses()
    if not found:
        print(">> no network address found. The dashboard will still work on"
              " this machine at http://localhost:%s" % port)
        return 0

    usable = [a for a in found if not a.startswith(CAMERA_VLAN)]
    print()
    print("   On a phone, join the SAME WiFi as this laptop and open:")
    print()
    for address in usable:
        print("       http://%s:%s" % (address, port))
    if not usable:
        print("       (none -- this machine is only on the camera network)")
    for address in found:
        if address.startswith(CAMERA_VLAN):
            print()
            print("   Not http://%s:%s -- that is the camera cable, and no"
                  % (address, port))
            print("   phone is on it. Streamlit may print it anyway.")
    print()
    print("   If the page will not load, Windows Firewall is blocking the"
          " port.")
    print("   In an Administrator prompt, once:")
    print()
    print('       netsh advfirewall firewall add rule name="EnergyCam'
          ' dashboard" dir=in action=allow protocol=TCP localport=%s' % port)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
