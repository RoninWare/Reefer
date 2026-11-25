"""Sideload a channel ZIP onto every Roku on the local network.

    python tools/deploy_roku.py build/reef-loader.zip
    python tools/deploy_roku.py --list
    python tools/deploy_roku.py build/reef-loader.zip --only 192.168.1.20 192.168.1.21

Finds the Rokus by asking the network for them (SSDP, the way Roku's own apps do), then
uploads the ZIP to each one that has developer mode on, through the developer installer at
http://<roku>/plugin_install. A Roku has one sideload slot, so this replaces whatever was
sideloaded before.

The developer password is asked for once, without showing it, and used for every device. It
is never written anywhere and never taken from the command line. Uses only Python's standard
library.
"""
import argparse
import getpass
import html
import re
import socket
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

SEARCH = ("M-SEARCH * HTTP/1.1\r\nHost: 239.255.255.250:1900\r\nMan: \"ssdp:discover\"\r\nST: roku:ecp\r\nMX: 2\r\n\r\n").encode()


def local_addresses():
    """This computer's IPv4 addresses, one per network it is on."""
    found = {info[4][0] for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)}
    try:        # the address used to reach the wider network, in case the host name lists none
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("192.0.2.1", 9))
            found.add(probe.getsockname()[0])
    except OSError:
        pass
    return sorted(address for address in found if not address.startswith("127."))


def discover(wait=3.0):
    """The addresses of the Rokus that answer on any of this computer's networks."""
    rokus = set()
    for address in local_addresses():
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            try:
                sock.bind((address, 0))
            except OSError:
                continue
            sock.settimeout(wait)
            for _ in range(2):
                sock.sendto(SEARCH, ("239.255.255.250", 1900))
            try:
                while True:
                    reply, sender = sock.recvfrom(2048)
                    if b"roku:ecp" in reply.lower():
                        rokus.add(sender[0])
            except socket.timeout:
                pass
    return sorted(rokus, key=lambda ip: tuple(int(part) for part in ip.split(".")))


def describe(ip):
    """What a Roku says about itself: its name, model, software and whether developer mode is on."""
    try:
        with urllib.request.urlopen(f"http://{ip}:8060/query/device-info", timeout=5) as reply:
            page = reply.read(200_000).decode("utf-8", "replace")
    except OSError as error:
        return {"name": "(no answer)", "model": "", "version": "", "developer": None, "error": str(error)}

    def field(name):
        # The reply is a flat list of <name>text</name>. It comes from whatever answered on the
        # network, so it is read as text and never handed to an XML parser.
        found = re.search(rf"<{name}>([^<]*)</{name}>", page)
        return html.unescape(found.group(1)).strip() if found else ""

    return {"name": field("user-device-name") or field("friendly-device-name"), "model": field("model-name"),
            "version": field("software-version"), "developer": field("developer-enabled") == "true"}


def install(ip, password, package):
    """Uploads the package to one Roku. Returns (ok, what the Roku said)."""
    boundary = uuid.uuid4().hex
    body = b"".join([
        f'--{boundary}\r\nContent-Disposition: form-data; name="mysubmit"\r\n\r\nInstall\r\n'.encode(),
        f'--{boundary}\r\nContent-Disposition: form-data; name="archive"; filename="{package.name}"\r\n'
        f'Content-Type: application/zip\r\n\r\n'.encode(),
        package.read_bytes(),
        f"\r\n--{boundary}--\r\n".encode(),
    ])
    keys = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    keys.add_password(None, f"http://{ip}/", "rokudev", password)
    opener = urllib.request.build_opener(urllib.request.HTTPDigestAuthHandler(keys))
    request = urllib.request.Request(f"http://{ip}/plugin_install", data=body,
                                     headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with opener.open(request, timeout=180) as reply:
            page = reply.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        if error.code == 401:
            return False, "the Roku refused the password (HTTP 401)"
        return False, f"HTTP {error.code} {error.reason}"
    except OSError as error:
        return False, f"could not reach its installer: {error}"
    said = re.findall(r"'Set message content',\s*'([^']*)'", page) or re.findall(r'<font color="red">([^<]*)</font>', page)
    message = "; ".join(text.strip() for text in said if text.strip()) or "no message in the reply"
    lowered = message.lower()
    ok = ("success" in lowered or "identical to previous version" in lowered) and "fail" not in lowered
    return ok, message


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("zip", type=Path, nargs="?", help="the channel ZIP to sideload")
    parser.add_argument("--list", action="store_true", help="only list the Rokus found")
    parser.add_argument("--only", nargs="+", metavar="IP", help="deploy to these addresses instead of every Roku found")
    args = parser.parse_args()
    if not args.list and (args.zip is None or not args.zip.is_file()):
        parser.error("give the channel ZIP to sideload, or --list")

    rokus = args.only or discover()
    if not rokus:
        print("No Roku answered on this network.")
        return 1
    devices = {ip: describe(ip) for ip in rokus}
    for ip, device in devices.items():
        mode = {True: "developer mode on", False: "developer mode OFF", None: "did not answer"}[device["developer"]]
        print(f"  {ip:<15}  {device['name']:<28}  {device['model']:<22}  {device['version']:<10}  {mode}")
    if args.list:
        return 0

    ready = [ip for ip, device in devices.items() if device["developer"] is not False]
    if not ready:
        print("None of them has developer mode on.")
        return 1
    print(f"\nSideloading {args.zip.name} ({args.zip.stat().st_size / 1e6:.2f} MB) onto {len(ready)} Roku(s).")
    password = getpass.getpass("Roku developer password (not shown): ")
    if not password:
        print("No password given; nothing was deployed.")
        return 1
    failed = 0
    for ip in ready:
        ok, message = install(ip, password, args.zip)
        print(f"  {'OK    ' if ok else 'FAILED'}  {ip:<15}  {devices[ip]['name']}: {message}")
        failed += not ok
        if "refused the password" in message:
            print("Stopping: the same password would be refused by the others too.")
            break
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
