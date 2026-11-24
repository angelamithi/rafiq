"""Replace the rafiq.afrivance.ai block in the SHARED Caddyfile with deploy/shared-caddy-rafiq.caddy,
writing IN PLACE (same file, same inode) so the bind-mounted file inside shared_caddy updates.

    cp ~/proxy/Caddyfile ~/proxy/Caddyfile.backup-$(date +%F)
    python3 scripts/update_shared_caddy.py ~/proxy/Caddyfile
    docker exec shared_caddy caddy validate --config /etc/caddy/Caddyfile
    docker exec shared_caddy caddy reload --config /etc/caddy/Caddyfile

Only the rafiq block changes; every other site in the file is left exactly as it was.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    target = Path(sys.argv[1]).expanduser()
    block = (ROOT / "deploy" / "shared-caddy-rafiq.caddy").read_text()
    block = block[block.index("rafiq.afrivance.ai {"):].rstrip() + "\n"
    text = target.read_text()
    m = re.search(r"^rafiq\.afrivance\.ai \{\n.*?^\}\n?", text, re.S | re.M)
    new = text[:m.start()] + block + text[m.end():] if m else text.rstrip() + "\n\n" + block
    with open(target, "r+") as f:      # same inode: truncate and rewrite
        f.seek(0)
        f.write(new)
        f.truncate()
    print("Updated the rafiq block." if m else "Added the rafiq block.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
