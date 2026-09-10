import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

from flask import Flask, jsonify, request

app = Flask(__name__)

# Render supplies PORT automatically. Keep the fallback for local testing.
PORT = int(os.environ.get("PORT", "10000"))

# If a Render persistent disk is mounted at /var/data, the database will live there.
# Otherwise it stays beside this file for local/testing use.
DATA_DIR = "/var/data" if os.path.isdir("/var/data") else os.path.dirname(os.path.abspath(__file__))
os.makedirs(DATA_DIR, exist_ok=True)
DB_FILE = os.path.join(DATA_DIR, "licenses.db")

ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "").strip()
if not ADMIN_SECRET:
    raise RuntimeError("ADMIN_SECRET environment variable is required.")


def now_utc():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def db():
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS licenses (
            code TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            activated_at TEXT,
            expires_at TEXT,
            device_id TEXT,
            status TEXT NOT NULL DEFAULT 'UNUSED'
        )
    """)
    conn.commit()
    return conn


def create_code():
    return "KATH-" + "-".join(
        secrets.token_hex(2).upper() for _ in range(3)
    )


def admin_authorized(payload):
    supplied = str(payload.get("admin_secret", ""))
    return bool(supplied) and secrets.compare_digest(supplied, ADMIN_SECRET)


@app.get("/")
def home():
    return jsonify({
        "service": "Kathana License Server",
        "status": "online"
    })


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/api/activate")
def activate():
    payload = request.get_json(silent=True) or {}
    code = str(payload.get("code", "")).strip().upper()
    device_id = str(payload.get("device_id", "")).strip()

    if not code or not device_id:
        return jsonify({
            "valid": False,
            "message": "Code and device ID are required."
        }), 400

    conn = db()
    try:
        row = conn.execute(
            "SELECT * FROM licenses WHERE code=?",
            (code,)
        ).fetchone()

        if not row:
            return jsonify({
                "valid": False,
                "message": "Activation code does not exist."
            })

        if row["status"] == "REVOKED":
            return jsonify({
                "valid": False,
                "message": "This code has been revoked."
            })

        current = now_utc()

        if row["status"] == "ACTIVE":
            expires = datetime.fromisoformat(
                row["expires_at"].replace("Z", "+00:00")
            )

            if current >= expires:
                conn.execute(
                    "UPDATE licenses SET status='EXPIRED' WHERE code=?",
                    (code,)
                )
                conn.commit()
                return jsonify({
                    "valid": False,
                    "expired": True,
                    "message": "License expired."
                })

            if row["device_id"] != device_id:
                return jsonify({
                    "valid": False,
                    "message": "This code is already activated on another device."
                })

            return jsonify({
                "valid": True,
                "expires_at": row["expires_at"]
            })

        if row["status"] == "EXPIRED":
            return jsonify({
                "valid": False,
                "expired": True,
                "message": "License expired."
            })

        # UNUSED -> activate for exactly 30 days.
        expires = current + timedelta(days=30)

        conn.execute("""
            UPDATE licenses
            SET activated_at=?, expires_at=?, device_id=?, status='ACTIVE'
            WHERE code=?
        """, (
            iso(current),
            iso(expires),
            device_id,
            code
        ))
        conn.commit()

        return jsonify({
            "valid": True,
            "activated_at": iso(current),
            "expires_at": iso(expires)
        })
    finally:
        conn.close()


@app.post("/api/validate")
def validate():
    payload = request.get_json(silent=True) or {}
    code = str(payload.get("code", "")).strip().upper()
    device_id = str(payload.get("device_id", "")).strip()

    if not code or not device_id:
        return jsonify({
            "valid": False,
            "message": "Code and device ID are required."
        }), 400

    conn = db()
    try:
        row = conn.execute(
            "SELECT * FROM licenses WHERE code=?",
            (code,)
        ).fetchone()

        if not row:
            return jsonify({
                "valid": False,
                "message": "Activation code does not exist."
            })

        if row["status"] == "REVOKED":
            return jsonify({
                "valid": False,
                "message": "This code has been revoked."
            })

        if row["status"] != "ACTIVE":
            return jsonify({
                "valid": False,
                "message": "License is not active."
            })

        current = now_utc()
        expires = datetime.fromisoformat(
            row["expires_at"].replace("Z", "+00:00")
        )

        if current >= expires:
            conn.execute(
                "UPDATE licenses SET status='EXPIRED' WHERE code=?",
                (code,)
            )
            conn.commit()
            return jsonify({
                "valid": False,
                "expired": True,
                "message": "License expired."
            })

        if row["device_id"] != device_id:
            return jsonify({
                "valid": False,
                "message": "This code belongs to another device."
            })

        return jsonify({
            "valid": True,
            "expires_at": row["expires_at"]
        })
    finally:
        conn.close()


@app.post("/api/admin/create")
def admin_create():
    payload = request.get_json(silent=True) or {}

    if not admin_authorized(payload):
        return jsonify({
            "valid": False,
            "message": "Unauthorized."
        }), 403

    try:
        count = int(payload.get("count", 1))
    except Exception:
        count = 1

    count = max(1, min(count, 100))

    conn = db()
    try:
        codes = []

        for _ in range(count):
            code = create_code()

            while conn.execute(
                "SELECT 1 FROM licenses WHERE code=?",
                (code,)
            ).fetchone():
                code = create_code()

            conn.execute(
                "INSERT INTO licenses(code, created_at, status) VALUES (?, ?, 'UNUSED')",
                (code, iso(now_utc()))
            )
            codes.append(code)

        conn.commit()
        return jsonify({"codes": codes})
    finally:
        conn.close()


@app.post("/api/admin/revoke")
def admin_revoke():
    payload = request.get_json(silent=True) or {}

    if not admin_authorized(payload):
        return jsonify({
            "valid": False,
            "message": "Unauthorized."
        }), 403

    code = str(payload.get("code", "")).strip().upper()

    conn = db()
    try:
        cur = conn.execute(
            "UPDATE licenses SET status='REVOKED' WHERE code=?",
            (code,)
        )
        conn.commit()

        return jsonify({
            "success": cur.rowcount > 0,
            "message": "Revoked." if cur.rowcount else "Code not found."
        })
    finally:
        conn.close()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
