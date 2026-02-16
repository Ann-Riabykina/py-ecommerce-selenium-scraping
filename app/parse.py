from dataclasses import dataclass, asdict
from urllib.parse import urljoin
import csv
import re
from typing import Iterable

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://webscraper.io/"
HOME_URL = urljoin(BASE_URL, "test-sites/e-commerce/more/")


@dataclass
class Product:
    title: str
    description: str
    price: float
    rating: int
    num_of_reviews: int


_PRICE_RE = re.compile(r"[-+]?\d*\.?\d+")
_REVIEWS_RE = re.compile(r"(\d+)")


def _to_float_price(text: str) -> float:
    text = text.replace(",", "")
    match_obj = _PRICE_RE.search(text)
    return float(match_obj.group(0)) if match_obj else 0.0


def _to_int_reviews(text: str) -> int:
    match_obj = _REVIEWS_RE.search(text)
    return int(match_obj.group(1)) if match_obj else 0


def _extract_rating(block: BeautifulSoup) -> int:
    rated = block.select_one("[data-rating]")
    if rated and rated.has_attr("data-rating"):
        try:
            return int(str(rated["data-rating"]).strip())
        except Exception:
            pass

    stars = block.select(".glyphicon-star, .ws-icon-star, .fa-star")
    if stars:
        return len(stars)

    return 0


def _parse_products_from_html(html: str) -> list[Product]:
    soup = BeautifulSoup(html, "html.parser")

    blocks = soup.select("div.thumbnail")
    if not blocks:
        blocks = soup.select("div.product-wrapper")
    if not blocks:
        blocks = soup.select("div.col-sm-4.col-lg-4.col-md-4")

    products: list[Product] = []
    for block in blocks:
        title_el = (block.select_one("a.title")
                    or block.select_one("h4 a")
                    or block.select_one("a"))
        desc_el = (block.select_one("p.description")
                   or block.select_one("p.caption")
                   or block.select_one("p"))
        price_el = (block.select_one("h4.price")
                    or block.select_one("h4.pull-right")
                    or block.select_one("h4"))

        reviews_el = (block.select_one("p.review-count")
                      or block.select_one(".ratings p.pull-right")
                      or block.select_one("p.pull-right"))

        title = title_el.get_text(strip=True) if title_el else ""
        description = desc_el.get_text(" ", strip=True) if desc_el else ""
        price = _to_float_price(price_el.get_text(strip=True))\
            if price_el else 0.0
        num_reviews = _to_int_reviews(reviews_el.get_text(strip=True))\
            if reviews_el else 0
        rating = _extract_rating(block)

        if title and description and price_el:
            products.append(
                Product(
                    title=title,
                    description=description,
                    price=price,
                    rating=rating,
                    num_of_reviews=num_reviews,
                )
            )
    return products


def _find_more_url(html: str, current_url: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    more = soup.select_one("a.ecomerce-items-scroll-more")
    if not more or not more.get("href"):
        return None
    return urljoin(current_url, more["href"])


def _scrape_page(url: str, follow_more: bool, session: requests.Session) \
        -> list[Product]:
    products: list[Product] = []
    seen_urls: set[str] = set()

    next_url: str | None = url
    while next_url and next_url not in seen_urls:
        seen_urls.add(next_url)

        resp = session.get(next_url, timeout=30)
        resp.raise_for_status()
        html = resp.text

        products.extend(_parse_products_from_html(html))

        if follow_more:
            next_url = _find_more_url(html, next_url)
        else:
            next_url = None

    return products


def _write_csv(products: Iterable[Product], filename: str) -> None:
    products = list(products)
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["title", "description", "price",
                                               "rating", "num_of_reviews"])
        writer.writeheader()
        for product in products:
            writer.writerow(asdict(product))


def get_all_products() -> None:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome Safari",
            "Accept-Language": "en-US,en;q=0.9",
        }
    )

    pages = [
        ("home.csv", HOME_URL, False),
        ("computers.csv", urljoin(HOME_URL, "computers"), False),
        ("laptops.csv", urljoin(HOME_URL, "computers/laptops"), True),
        ("tablets.csv", urljoin(HOME_URL, "computers/tablets"), True),
        ("phones.csv", urljoin(HOME_URL, "phones"), False),
        ("touch.csv", urljoin(HOME_URL, "phones/touch"), True),
    ]

    for filename, url, follow_more in pages:
        products = _scrape_page(url, follow_more=follow_more, session=session)
        _write_csv(products, filename)


if __name__ == "__main__":
    get_all_products()
