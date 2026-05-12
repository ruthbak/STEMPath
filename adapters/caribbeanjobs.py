import requests
from bs4 import BeautifulSoup
import urllib.parse
from urllib.parse import urljoin


BASE_URL = "https://www.caribbeanjobs.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/91.0.4472.124 Safari/537.36"
    )
}


def _text_or_default(parent, selector: str, default: str = "") -> str:
    element = parent.select_one(selector)
    if not element:
        return default
    return element.get_text(strip=True) or default


def _href_or_default(parent, selector: str = "a", default: str = "") -> str:
    element = parent.select_one(selector)
    if not element:
        return default
    href = element.get("href") or default
    return urljoin(BASE_URL, href) if href else default


def _first_text_or_default(parent, selectors: tuple[str, ...], default: str = "") -> str:
    for selector in selectors:
        text = _text_or_default(parent, selector)
        if text:
            return text
    return default


def _first_href_or_default(parent, selectors: tuple[str, ...], default: str = "") -> str:
    for selector in selectors:
        href = _href_or_default(parent, selector)
        if href:
            return href
    return default


def fetch_jobs(role_title: str, location: str = "Jamaica") -> list[dict]:
    """
    Returns a list of normalized job dicts:
    { title, company, location, url, link, source }
    """
    encoded_role = urllib.parse.quote(role_title)
    encoded_location = urllib.parse.quote(location)
    url = f"{BASE_URL}/ShowResults.aspx?Keywords={encoded_role}&Location={encoded_location}"

    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"CaribbeanJobs request error: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")

    jobs = []
    for card in soup.select(".job-result")[:5]:
        title = _first_text_or_default(card, (".job-result-title a", ".job-title a", ".job-title"))
        link = _first_href_or_default(card, (".job-result-title a", ".job-title a", "a"))

        if not title:
            continue

        jobs.append({
            "title": title,
            "company": _first_text_or_default(
                card,
                (".job-result-company a", ".company a", ".company"),
                "CaribbeanJobs",
            ),
            "location": _text_or_default(card, ".location", location),
            "url": link,
            "link": link,
            "source": "CaribbeanJobs",
        })
    return jobs
