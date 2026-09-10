import json
import os
import sys
import urllib.request

SERVER_URL = os.environ.get(
    "LICENSE_SERVER_URL",
    "https://YOUR-SERVICE-NAME.onrender.com"
).rstrip("/")

ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "").strip()


def request(path, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        SERVER_URL + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def main():
    if not ADMIN_SECRET:
        print("ERROR: Set ADMIN_SECRET before using this tool.")
        print("Windows CMD:    set ADMIN_SECRET=your-secret")
        print("PowerShell:     $env:ADMIN_SECRET='your-secret'")
        return

    if len(sys.argv) < 2:
        print("python license_admin_online.py create [count]")
        print("python license_admin_online.py revoke CODE")
        return

    action = sys.argv[1].lower()

    if action == "create":
        try:
            count = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        except ValueError:
            print("Count must be a number.")
            return

        result = request(
            "/api/admin/create",
            {
                "admin_secret": ADMIN_SECRET,
                "count": count
            }
        )

        for code in result.get("codes", []):
            print(code)

        if not result.get("codes"):
            print(result.get("message", result))

    elif action == "revoke":
        if len(sys.argv) < 3:
            print("Missing code.")
            return

        result = request(
            "/api/admin/revoke",
            {
                "admin_secret": ADMIN_SECRET,
                "code": sys.argv[2]
            }
        )

        print(result.get("message", result))

    else:
        print("Unknown action.")


if __name__ == "__main__":
    main()
