import requests
from bs4 import BeautifulSoup

def fetch_jobs(role_title: str, location: str = "Jamaica") -> list[dict]:
    """
    Returns a list of normalized job dicts:
    { title, company, location, url, date_posted }
    """
    url = f"https://www.caribbeanjobs.com/jobs?q={role_title}&l={location}"
    response = requests.get(url, timeout=10)
    soup = BeautifulSoup(response.text, "html.parser")
    
    jobs = []
    for card in soup.select(".job-result"):  # inspect actual class names on the site
        jobs.append({
            "title": card.select_one(".job-title").text.strip(),
            "company": card.select_one(".company").text.strip(),
            "location": card.select_one(".location").text.strip(),
            "url": card.select_one("a")["href"],
        })
    return jobs