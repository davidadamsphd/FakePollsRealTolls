import argparse
import csv
import logging
import requests
from bs4 import BeautifulSoup

MAX_RESULTS_FROM_QUERY = 700
RESULTS_PER_PAGE = 100

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'
}


def parseargs():
    parser = argparse.ArgumentParser(
        description='Runner for this script.'
    )
    parser.add_argument("-v", "--verbose", help="increase output verbosity",
                        action="store_true")
    parser.add_argument("--url", help="pollster ratings url",
                        required=True)
    parser.add_argument("--output-csv", help="file to put the rating results",
                        required=True)
    args = parser.parse_args()
    if args.verbose:
        logging.basicConfig(level=logging.INFO)
    return args


def main():
    args = parseargs()
    logging.info('starting...')
    r = requests.get(args.url, headers=HEADERS)
    bs = BeautifulSoup(r.content, 'html.parser')
    pollster_names = [p.get('data-mobile') for p in bs.find_all('td', class_=' pollster')]
    pollster_ratings = [p.text.strip() for p in bs.find_all('div', class_='gradeText')]
    logging.info('lengths of names and ratings: {}, {}'.format(
        len(pollster_names), len(pollster_ratings)))
    assert len(pollster_names) == len(pollster_ratings)
    to_write = zip(pollster_names, pollster_ratings)
    with open(args.output_csv, 'wb') as f:
        writer = csv.writer(f, delimiter=',')
        writer.writerows(to_write)

if __name__ == '__main__':
    main()
