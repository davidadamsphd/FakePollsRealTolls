import argparse
import logging
import json
import twitter
import requests
import os.path
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
    parser.add_argument("--secret-file", help="json file with twitter secrets",
                        required=True)
    args = parser.parse_args()
    if args.verbose:
        logging.basicConfig(level=logging.INFO)
    return args


def get_filename(term, since, until):
    return 'cache_{}_{}_{}.json'.format(term, since, until)


def read_queries_from_file(filename):
    with open(filename, 'rb') as f:
        file_dict = json.load(f)
    all_results = []
    for result in file_dict['statuses']:
        s = twitter.Status.NewFromJsonDict(result)
        # The to and from JSON is not symmetric, so patch as needed...
        # TODO: Work with the raw JSON from twitter if this gets messier.
        urls = [twitter.Url.NewFromJsonDict(u) for u in result['urls']]
        s.urls = urls
        all_results.append(s)
    return all_results


def write_queries_to_file(filename, all_results):
    d = {'statuses': []}
    for result in all_results:
        d['statuses'].append(result.AsDict())
    with open(filename, 'wb') as f:
        json.dump(d, f, indent=4, sort_keys=True)


def paginated_query(api, term, since=None, until=None, use_cache=False):
    # Keep issuing queries until all results are received.
    if use_cache:
        cache_filename = get_filename(term, since, until)
        if os.path.exists(cache_filename):
            logging.info('reading results from cache')
            return read_queries_from_file(cache_filename)

    page = api.GetSearch(term=term, until=until, since=since,
                         count=RESULTS_PER_PAGE)
    if len(page) < RESULTS_PER_PAGE:
        return page
    # All pages is a list of all results, which initially, is just the first page.
    all_pages = page
    max_id = page[-1].id
    logging.info('have now processed {} results'.format(len(all_pages)))
    while len(all_pages) < MAX_RESULTS_FROM_QUERY:
        page = api.GetSearch(term=term, until=until, since=since,
                             count=RESULTS_PER_PAGE, max_id=str(max_id-1))
        all_pages += page
        if len(page) == 0:
            return all_pages
        max_id = page[-1].id
        logging.info('have now processed {} results'.format(len(all_pages)))
    logging.warning('hit max results of {}, stopping'.format(MAX_RESULTS_FROM_QUERY))

    if use_cache:
        cache_filename = get_filename(term, since, until)
        write_queries_to_file(cache_filename, all_pages)
    return all_pages


def expand_url_if_short(url):
    min_url_length = 30
    if len(url) >= min_url_length:
        return url
    # Use requests to send a get request to the url and return the real url.
    logging.info('short url: {}'.format(url))
    new_url = requests.get(url, headers=HEADERS).url
    if len(new_url) < min_url_length:
        logging.warning('Unable to expand url: ({}, {})'.format(url, new_url))
    return new_url


def get_non_twitter_urls(urls_class):
    blacklist = ['twitter.com', 'youtube.com']
    urls = []
    if urls_class:
        for url_class in urls_class:
            long_url = expand_url_if_short(url_class.expanded_url)
            blacklisted = False
            for b in blacklist:
                if long_url.find(b) != -1:
                    blacklisted = True
            if not blacklisted:
                urls.append(long_url)
    return urls


def find_polling_firms_from_p(p):
    return []


def find_polling_firm_from_html(html):
    polling_firms = []
    bs = BeautifulSoup(html, 'html.parser')
    for p in bs.find_all('p'):
        firms = find_polling_firms_from_p(p)
        polling_firms += firms


def main():
    args = parseargs()
    logging.info('starting...')
    with open(args.secret_file) as f:
        secrets = json.load(f)

    api = twitter.Api(consumer_key=secrets['APIKey'],
                      consumer_secret=secrets['APISecret'],
                      access_token_key=secrets['AccessToken'],
                      access_token_secret=secrets['AccessTokenSecret'])

    term = 'new poll'
    since = '2017-9-03'
    until = '2017-9-04'
    results = paginated_query(api=api, term=term, since=since, until=until,
                              use_cache=True)
    min_reweets = 2
    for result in results:

        if (result.retweet_count > min_reweets) and (result.retweeted_status is None):
            urls = get_non_twitter_urls(result.urls)
            if len(urls) > 0:
                for u in urls:
                    # TODO: implement finding the polling firm(s).
                    find_polling_firm_from_html(requests.get(u, headers=HEADERS).content)
                print('---------------------------------------')
                print(u'text: \n\t{}'.format(result.text))
                print(u'result.urls: \n\t{}'.format(result.urls))
                print(u'urls: \n\t{}'.format(urls))
                print(u'retweet count: {}'.format(result.retweet_count))
                print(u'user name: {}'.format(result.user.name))
                print(u'tweet id: {}'.format(result.id))
                print(u'retweet status: {}'.format(result.retweeted_status is not None))

if __name__ == '__main__':
    main()
