import re
from datetime import datetime

import pandas as pd
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm


def scrape_tenders(base_url: str, search_query: str, num_tenders: int):
    tenders = []
    page_num = 1
    pbar = tqdm(total=num_tenders, desc="Scraping data")
    prev_len = 0

    while len(tenders) < num_tenders:
        url = f"{base_url}/page/{page_num}/?s={search_query}"
        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")

        articles = soup.find_all("article")

        if not articles:
            raise ValueError("No articles found")

        for article in articles:
            project = article.find(
                "h2", class_="post-title entry-title"
            ).get_text(strip=True)

            company = (
                article.find("span", string=lambda x: x and "Company:" in x)
                .find_next_sibling(string=True)
                .strip()
            )

            sector = (
                article.find("span", string=lambda x: x and "Sector:" in x)
                .find_next_sibling(string=True)
                .strip()
            )

            date_pattern = r"Closing Date:\s+(\d{1,2}(?:st|nd|rd|th)\s+[A-Za-z,?]+\s+\d{4})"

            match = re.search(date_pattern, article.text)

            if match:
                extracted_date = match.group(1)
                closing_date = re.sub(
                    r"\s+", " ", extracted_date.replace("\xa0", " ")
                ).strip()

            tenders.append(
                {
                    "Date": closing_date,
                    "Company": company,
                    "URL": url,
                    "Sector": sector,
                    "Project": project,
                }
            )

        page_num += 1
        # print("tenders:", len(tenders))

        current_len = len(tenders)
        update_len = current_len - prev_len
        pbar.update(update_len)
        prev_len = current_len

    pbar.close()
    return tenders


def post_processing(data: pd.DataFrame):
    data = data.assign(
        Sector=lambda df: df.Sector.str.title().replace("Public", "Govt"),
        day=lambda df: df.Date.str.extract("(\d{1,2}).*"),
        month=lambda df: df.Date.str.extract("\w+\s+([A-Za-z]+),?\s+.*"),
        year=lambda df: df.Date.str.extract(".*(\d{4})$"),
        Date=lambda df: pd.to_datetime(
            df.day + df.month + df.year, format="mixed", dayfirst=True
        ),
    )

    return data.drop(columns=["day", "month", "year"])


if __name__ == "__main__":
    from argparse import ArgumentParser

    BASE_URL = "https://www.tenderyetu.com"
    ts = int(datetime.now().timestamp())

    parser = ArgumentParser()

    parser.add_argument(
        "-n",
        help="Number of tenders to fetch",
        default=100,
        type=int,
    )

    parser.add_argument(
        "-q",
        help="Search query",
        default="system",
        type=str,
    )

    args = parser.parse_args()

    print(args)

    validate = input("Do you want to continue?[y/n]")

    if validate.lower() != "y":
        print("Exiting...")
        exit(0)

    tenders_data = scrape_tenders(
        base_url=BASE_URL, search_query=args.q, num_tenders=args.n
    )

    csv_file_path = f"tenders_data_{ts}.csv"
    df = pd.DataFrame(tenders_data)
    df.to_csv(csv_file_path, index=False)
    print(f"Data saved to {csv_file_path}")

    # clean the dataset
    tenders = pd.read_csv(csv_file_path)
    cleaned = post_processing(tenders)
    cleaned_file_path = f"cleaned_data_{ts}.xlsx"
    cleaned.to_excel(cleaned_file_path, index=False)
    print("Done!!")
