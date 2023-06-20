import json
import logging
import pathlib
import re
from dataclasses import dataclass
from datetime import datetime

from bs4 import BeautifulSoup

import requests as requests

from enhased_json_decoder import EnhancedJSONEncoder

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

goodreads_base_url = "https://www.goodreads.com"
goodreads_first_page_url = f"{goodreads_base_url}/review/list/18740796-vadym-klymenko?shelf=read"

read_books_output_json_file = pathlib.Path(__file__).parent.resolve() / "data" / "read.json"
top_rated_output_json_file = pathlib.Path(__file__).parent.resolve() / "data" / "top_rated.json"


@dataclass
class BookReview:
    title: str
    author: str
    cover_url: str
    rating: int
    date_started: str = None
    date_read: str = None


def process_bookshelf_page(page_content: BeautifulSoup) -> list[BookReview]:
    books_table = page_content.find('table', id='books')
    books = []

    for row in books_table.find_all('tr')[1:]: # skip header
        title = row.find('td', class_='field title').find('a').text.strip()
        author = row.find('td', class_='field author').find('a').text
        cover_url = row.find('img')["src"]
        if cover_url:
            # Replace small cover with big one
            # https://i.gr-assets.com/images/S/compressed.photo.goodreads.com/books/1675866212l/106136930._SY75_.jpg
            pattern = r"\._S[YX]\d+_\."
            cover_url = re.sub(pattern, ".", cover_url)
        rating = len(row.find('td', class_='field rating').find_all('span', class_='p10'))  # 5 stars = 5 spans

        date_started = row.find('td', class_='field date_started').find('span', class_='date_started_value')
        if date_started:
            date_started = date_str_to_iso(date_started.text)

        date_read = row.find('td', class_='field date_read').find('span', class_='date_read_value')
        if date_read:
            date_read = date_str_to_iso(date_read.text)

        if not date_started and not date_read:
            # Треба прибрати книжки з Шакалячого експреса :)
            continue

        book = BookReview(
            title=title,
            author=author,
            cover_url=cover_url,
            rating=rating,
            date_started=date_started,
            date_read=date_read
        )

        books.append(book)

    return books


def get_next_page(bs_content: BeautifulSoup) -> str | None:
    has_next_page = bs_content.find('a', class_='next_page')
    if not has_next_page:
        return None
    next_page_url = has_next_page["href"]
    return f"{goodreads_base_url}{next_page_url}"


def date_str_to_iso(date: str) -> str:
    """
    Convert date string to isoformat

    :param date: Date in string format like Feb 08, 2023 or Feb 2023
    :return: Date in isoformat (YYYY-MM-DD)
    """
    if ", " not in date:
        date_obj = datetime.strptime(date, "%b %Y").replace(day=1)
    else:
        date_obj = datetime.strptime(date, "%b %d, %Y")

    return date_obj.date().isoformat()


def parse_books(url: str) -> list[BookReview]:
    """
    Parse books from goodreads

    :param url: Url to parse
    :return: List of books
    """
    logger.info("Processing url %s...", url)
    request = requests.get(url)

    books = []

    books_page_content = BeautifulSoup(request.content, 'html.parser')
    books.extend(process_bookshelf_page(books_page_content))

    next_page_url = get_next_page(books_page_content)
    if next_page_url:
        books.extend(parse_books(next_page_url))

    return books


def process():
    """
    Process books from goodreads and write them to file
    """
    books = parse_books(goodreads_first_page_url)

    logger.info("Books on goodreads: %s", len(books))
    logger.info("Writing books to file...")

    with open(read_books_output_json_file, 'w', encoding='utf-8') as f:
        books_dict = {"books": books}
        json_str = json.dumps(books_dict, cls=EnhancedJSONEncoder, ensure_ascii=False, indent=2)
        f.write(json_str)

    with open(top_rated_output_json_file, 'w', encoding='utf-8') as f:
        top_rated_books = list(filter(lambda book: book.rating in [4, 5], books))
        books_dict = {"books": top_rated_books}
        json_str = json.dumps(books_dict, cls=EnhancedJSONEncoder, ensure_ascii=False, indent=2)
        f.write(json_str)

    logger.info("Done!")


if __name__ == '__main__':
    process()
