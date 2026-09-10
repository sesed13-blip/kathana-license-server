KATHANA LICENSE SERVER - RENDER

1. Upload these files to a GitHub repository:
   - app.py
   - requirements.txt
   - .python-version
   - render.yaml

2. In Render:
   New -> Web Service -> connect the GitHub repository.

3. Render should use:
   Build Command:
       pip install -r requirements.txt

   Start Command:
       gunicorn app:app

4. Add the secret environment variable:
   ADMIN_SECRET = a long random secret that only YOU know.

5. After deployment, test:
   /health

   It should return:
       {"status":"ok"}

6. Copy your public Render HTTPS address.
   Example:
       https://kathana-license-server.onrender.com

7. Put that address into:
   license_admin_online.py
   and later into the customer bot as LICENSE_SERVER_URL.

IMPORTANT:
- Never put ADMIN_SECRET inside the customer bot.
- The customer bot only needs the public HTTPS server address.
- The admin secret is only for creating/revoking codes.
- The database is SQLite.
- For a real production sales system, use persistent storage so licenses survive
  service replacement/deployment. Render supports persistent disks; the server
  automatically uses /var/data when that directory exists.

LOCAL TEST:
    py -m pip install -r requirements.txt
    set ADMIN_SECRET=change-this-to-a-real-secret
    py app.py

Then open:
    http://127.0.0.1:10000/health
