#!/usr/bin/env python3
from __future__ import annotations

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import ssl
import sys
import threading
from urllib.parse import parse_qs, urlparse
import urllib.request


APP_DIR = Path(__file__).resolve().parent
PROJECT_DIR = APP_DIR.parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

DATA_FILE = PROJECT_DIR / "data" / "points_wallet.json"
PINGAN_RULES_FILE = PROJECT_DIR / "config" / "pingan_wanlitong_rules.json"
OFFICIAL_COSTS_FILE = PROJECT_DIR / "config" / "official_purchase_costs.json"
CERT_FILE = PROJECT_DIR / "certs" / "points-wallet.crt"
KEY_FILE = PROJECT_DIR / "certs" / "points-wallet.key"


class PointsWalletHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(APP_DIR), **kwargs)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/data":
            self.write_json(load_data())
            return
        if path == "/api/rates":
            self.write_json(load_rates())
            return
        if path == "/api/transfer-rules":
            self.write_json({"programs": transfer_rules()})
            return
        if path == "/api/pingan-rules":
            self.write_json(load_pingan_rules())
            return
        if path == "/api/official-costs":
            self.write_json(load_official_costs())
            return
        if path == "/api/tripplus-refresh":
            self.write_json(refresh_tripplus_costs())
            return
        if path == "/api/seataero-search":
            self.write_json(search_seataero(parse_qs(parsed.query)))
            return
        super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/data":
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            DATA_FILE.parent.mkdir(exist_ok=True)
            DATA_FILE.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self.write_json({"ok": True})
            return
        if path == "/api/pingan-rules":
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            if not isinstance(payload.get("programs"), list):
                self.write_json({"ok": False, "error": "programs must be a list"})
                return
            PINGAN_RULES_FILE.parent.mkdir(exist_ok=True)
            payload["updatedAt"] = "manual"
            PINGAN_RULES_FILE.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self.write_json({"ok": True})
            return
        if path == "/api/official-costs":
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            if not isinstance(payload.get("programs"), list):
                self.write_json({"ok": False, "error": "programs must be a list"})
                return
            payload["updatedAt"] = "manual"
            OFFICIAL_COSTS_FILE.parent.mkdir(exist_ok=True)
            OFFICIAL_COSTS_FILE.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self.write_json({"ok": True})
            return
        self.send_error(404)

    def write_json(self, payload: dict) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class RedirectHandler(SimpleHTTPRequestHandler):
    def do_GET(self) -> None:
        self.redirect_to_https()

    def do_HEAD(self) -> None:
        self.redirect_to_https()

    def do_POST(self) -> None:
        self.redirect_to_https()

    def redirect_to_https(self) -> None:
        host = self.headers.get("Host", "127.0.0.1").split(":")[0]
        location = f"https://{host}:8788{self.path}"
        self.send_response(308)
        self.send_header("Location", location)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()


def load_data() -> dict:
    if not DATA_FILE.exists():
        return {}
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def load_rates() -> dict:
    fallback = {"TWD": 1, "CNY": 4.35, "USD": 31.5, "JPY": 0.21, "EUR": 34, "GBP": 40, "HKD": 4.03, "CAD": 23, "AUD": 20.6}
    try:
        with urllib.request.urlopen("https://open.er-api.com/v6/latest/TWD", timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))
        rates = data.get("rates") or {}
        converted = {currency: 1 / value for currency, value in rates.items() if value}
        converted["TWD"] = 1
        return {"base": "TWD", "rates": converted, "source": "open.er-api.com"}
    except Exception:
        return {"base": "TWD", "rates": fallback, "source": "fallback"}


def load_pingan_rules() -> dict:
    if not PINGAN_RULES_FILE.exists():
        return {"programs": [], "assumptions": {}}
    try:
        return json.loads(PINGAN_RULES_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"programs": [], "assumptions": {}}


def load_official_costs() -> dict:
    if not OFFICIAL_COSTS_FILE.exists():
        return {"programs": [], "source": "manual", "sourceUrl": "https://www.tripplus.cc/storefront"}
    try:
        return json.loads(OFFICIAL_COSTS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"programs": [], "source": "manual", "sourceUrl": "https://www.tripplus.cc/storefront"}


def refresh_tripplus_costs() -> dict:
    url = "https://www.tripplus.cc/storefront"
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            html = response.read(300000).decode("utf-8", errors="replace")
    except Exception as exc:
        return {
            "ok": False,
            "message": f"TripPlus 目前拒絕後端自動讀取（{exc}）。官網成本表仍可手動維護，填入每哩成本後會立即進入查票比較。",
            "programs": load_official_costs().get("programs", []),
        }

    if "challenge-platform" in html or "Just a moment" in html or "Cloudflare" in html:
        return {
            "ok": False,
            "message": "TripPlus 目前有 Cloudflare 驗證，後端無法自動抓商品；請先用官網成本表手動維護。",
            "programs": load_official_costs().get("programs", []),
        }

    return {
        "ok": False,
        "message": "TripPlus 頁面可讀，但沒有找到穩定商品 API；保留手動維護資料。",
        "programs": load_official_costs().get("programs", []),
    }


def first_query(query: dict, key: str, default: str = "") -> str:
    value = query.get(key, [default])
    return value[0] if value else default


def search_seataero(query: dict) -> dict:
    try:
        from seat_aero import SeatAeroClient, SeatAeroError, get_api_key, load_dotenv

        load_dotenv(PROJECT_DIR / ".env")
        client = SeatAeroClient(get_api_key(PROJECT_DIR), timeout_seconds=35)
        result = client.search(
            origin_airport=first_query(query, "origin").upper(),
            destination_airport=first_query(query, "destination").upper(),
            sources=first_query(query, "source", "aeroplan"),
            take=int(first_query(query, "take", "20") or "20"),
            start_date=first_query(query, "startDate"),
            end_date=first_query(query, "endDate"),
            cabins=first_query(query, "cabins"),
            include_trips=False,
            only_direct_flights=first_query(query, "direct", "false") == "true",
        )
        return {"ok": True, "result": result}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def transfer_rules() -> list[dict]:
    airline = [
        "ANA",
        "EVA Air",
        "China Airlines",
        "Qatar Avios",
        "Finnair Avios",
        "British Airways Avios",
        "Asia Miles",
        "JAL",
        "Alaska",
        "Air Canada Aeroplan",
        "United",
        "Flying Blue",
    ]
    rules = [
        {
            "program": program,
            "category": "airline",
            "ratio": 3,
            "bonusThreshold": 60000,
            "bonusMiles": 5000,
            "note": "Marriott 多數航空夥伴 3:1，滿 60k Bonvoy 通常 +5k miles。",
        }
        for program in airline
    ]
    rules.append(
        {
            "program": "LifeMiles",
            "category": "airline",
            "ratio": 3,
            "bonusThreshold": 0,
            "bonusMiles": 0,
            "note": "LifeMiles 目前不適用 Marriott 每 60k +5k bonus。",
        }
    )
    for program in ["Marriott", "Choice", "Hilton", "IHG", "Accor"]:
        rules.append(
            {
                "program": program,
                "category": "hotel",
                "ratio": None,
                "bonusThreshold": 0,
                "bonusMiles": 0,
                "note": "飯店計畫不是 Marriott 官方可直接轉點對象；此處做等值成本比較。",
            }
        )
    return rules


def main() -> None:
    if not CERT_FILE.exists() or not KEY_FILE.exists():
        raise SystemExit(f"Missing HTTPS certificate: {CERT_FILE} / {KEY_FILE}")

    redirect_server = ThreadingHTTPServer(("0.0.0.0", 8787), RedirectHandler)
    redirect_thread = threading.Thread(target=redirect_server.serve_forever, daemon=True)
    redirect_thread.start()

    server = ThreadingHTTPServer(("0.0.0.0", 8788), PointsWalletHandler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=str(CERT_FILE), keyfile=str(KEY_FILE))
    server.socket = context.wrap_socket(server.socket, server_side=True)
    print("Points Wallet redirecting http://0.0.0.0:8787 to https://0.0.0.0:8788", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
