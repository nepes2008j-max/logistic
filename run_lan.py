"""Serve HandShake on the local network so it can be opened from a phone.

app.py is left untouched — this just imports the configured Flask app and binds
it to every interface instead of localhost.

    python run_lan.py [port]

Then open http://<this-machine's-LAN-ip>:<port>/ on any device on the same
Wi-Fi. The address is printed on startup.

Debug mode is deliberately OFF here. The Werkzeug debugger allows arbitrary code
execution through the browser, which must never be reachable from other machines
on a network.
"""

import socket
import sys

from app import app


def lan_ip():
    """Best-effort local network address of this machine."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # No packets are actually sent; this just picks the outbound interface.
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    ip = lan_ip()

    print()
    print("  HandShake is live on your network")
    print("  ---------------------------------")
    print("  This computer :  http://127.0.0.1:%d/" % port)
    print("  Your phone    :  http://%s:%d/" % (ip, port))
    print("  Device preview:  http://%s:%d/static/device_preview.html" % (ip, port))
    print()
    print("  Phone and computer must be on the same Wi-Fi.")
    print("  Stop with Ctrl-C.")
    print()

    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
