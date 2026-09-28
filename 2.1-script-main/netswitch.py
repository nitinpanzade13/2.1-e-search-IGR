"""
On-demand Wi-Fi rotation.

The portal's search quota is tied to the public IP. Reconnecting the
phone hotspot makes the carrier hand out a new one; the parking profile
exists only to force a real disassociation in between.

This replaces switch-hotspot.bat, which looped on a fixed 60s timer and
would happily cut the connection in the middle of a request.
"""
import subprocess
import time

import requests

from config import (
    WIFI_INTERFACE,
    HOTSPOT_PROFILE,
    PARKING_PROFILE,
    SWITCH_SETTLE_SECONDS,
    CONNECTIVITY_TIMEOUT,
    MAX_ROTATION_ATTEMPTS,
)

IP_ECHO_SERVICES = [
    "https://api.ipify.org",
    "https://ifconfig.me/ip",
    "https://icanhazip.com",
]


def _run(args):
    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=60,
    )

    return result.returncode, (result.stdout or "").strip()


def connected_profile():
    """Name of the currently associated network, or '' if offline."""

    try:
        code, out = _run(["netsh", "wlan", "show", "interfaces"])
    except Exception:
        return ""

    if code != 0:
        return ""

    for line in out.splitlines():
        stripped = line.strip()

        # Match "Profile : X" but not "Profile name"/"SSID".
        if stripped.startswith("Profile") and ":" in stripped:
            return stripped.split(":", 1)[1].strip()

    return ""


def connect(profile, interface=WIFI_INTERFACE):
    """Associate with a saved Wi-Fi profile."""

    print(f"  [net] connecting to {profile!r}...")

    code, out = _run([
        "netsh", "wlan", "connect",
        f"name={profile}",
        f"interface={interface}",
    ])

    if code != 0:
        print(f"  [net] netsh failed: {out}")
        return False

    return True


def public_ip(timeout=8):
    """Best-effort public IP lookup. Returns None if every service fails."""

    for url in IP_ECHO_SERVICES:
        try:
            response = requests.get(url, timeout=timeout)

            if response.ok:
                ip = response.text.strip()

                if ip and len(ip) <= 45:
                    return ip

        except Exception:
            continue

    return None


def wait_for_connectivity(timeout=CONNECTIVITY_TIMEOUT):
    """Block until we can actually reach the internet, or time out."""

    deadline = time.time() + timeout

    while time.time() < deadline:

        ip = public_ip(timeout=6)

        if ip:
            return ip

        time.sleep(3)

    return None


def rotate(previous_ip=None, max_attempts=MAX_ROTATION_ATTEMPTS):
    """
    Park on the secondary network, then reconnect the hotspot until the
    public IP differs from `previous_ip`.

    Returns the new IP, or None if it never changed.
    """

    print("\n" + "-" * 70)
    print(f"[net] rotating IP (was {previous_ip or 'unknown'})")
    print("-" * 70)

    for attempt in range(1, max_attempts + 1):

        print(f"\n  [net] attempt {attempt}/{max_attempts}")

        connect(PARKING_PROFILE)
        time.sleep(SWITCH_SETTLE_SECONDS)

        connect(HOTSPOT_PROFILE)
        time.sleep(SWITCH_SETTLE_SECONDS)

        ip = wait_for_connectivity()

        if not ip:
            print("  [net] no connectivity yet, retrying...")
            continue

        if previous_ip is None or ip != previous_ip:
            print(f"  [net] new IP: {ip}")
            return ip

        print(f"  [net] IP unchanged ({ip}), retrying...")

    print("  [net] could not obtain a new IP")

    return None


if __name__ == "__main__":

    print("Current profile:", connected_profile() or "(offline)")

    before = public_ip()
    print("Current public IP:", before or "(unreachable)")

    answer = input("\nRun a test rotation? [y/N]: ").strip().lower()

    if answer == "y":
        after = rotate(previous_ip=before)
        print("\nResult:", after or "rotation failed")
