"""Check which RSS catalog feeds are live and which are broken."""

from app.services.seed_data import RSS_CATALOG
from app.services.rss_fetcher import _parse_feed, USER_AGENT
from urllib.request import Request, urlopen
from urllib.error import URLError

def check():
    print(f"Checking {len(RSS_CATALOG)} catalog feeds...\n")
    ok = 0
    broken = 0
    for entry in RSS_CATALOG:
        name = entry["name"]
        url = entry["url"]
        try:
            req = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(req, timeout=15) as resp:
                code = resp.status
                xml = resp.read()
            entries = _parse_feed(xml)
            print(f"  OK  {name} — {code}, {len(entries)} entries")
            print(f"      {url}")
            ok += 1
        except (URLError, TimeoutError, OSError) as e:
            print(f"  FAIL  {name} — {e}")
            print(f"        {url}")
            broken += 1
        except Exception as e:
            print(f"  FAIL  {name} — {e}")
            print(f"        {url}")
            broken += 1

    print(f"\n{ok} OK, {broken} broken out of {len(RSS_CATALOG)} feeds")

if __name__ == "__main__":
    check()
