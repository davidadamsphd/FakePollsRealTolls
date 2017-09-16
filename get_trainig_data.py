import argparse
import csv
import logging
import json
import twitter
import requests
import os.path
import time

from bs4 import BeautifulSoup
from bs4.element import Comment

MAX_RESULTS_FROM_QUERY = 100000
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
    parser.add_argument("--pollster-csv", help="csv file with pollster ratings",
                        required=True)
    parser.add_argument("--positive-output", help="csv file to write with positive cases",
                        required=True)
    parser.add_argument("--negative-output", help="csv file to write with negative cases",
                        required=True)
    args = parser.parse_args()
    if args.verbose:
        logging.basicConfig(level=logging.INFO)
    return args


def get_filename(term, since, until):
    return 'cache_{}_{}_{}_{}.json'.format(term, since, until, MAX_RESULTS_FROM_QUERY)


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


def paginated_query(api, term, since=None, until=None, use_cache=False, be_nice=False):
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
        if be_nice:
            time.sleep(6)  # Sleep 6 seconds to avoid the Twitter API limit
        page = api.GetSearch(term=term, until=until, since=since,
                             count=RESULTS_PER_PAGE, max_id=str(max_id-1))
        all_pages += page
        if len(page) == 0:
            break
        max_id = page[-1].id
        logging.info('have now processed {} results'.format(len(all_pages)))
    if len(all_pages) >= MAX_RESULTS_FROM_QUERY:
        logging.warning('hit max results of {}, stopping'.format(MAX_RESULTS_FROM_QUERY))

    if use_cache:
        cache_filename = get_filename(term, since, until)
        write_queries_to_file(cache_filename, all_pages)
    return all_pages


def expand_url_if_short(url):
    new_url = None
    try:
        min_url_length = 30
        if len(url) >= min_url_length:
            return url
        # Use requests to send a get request to the url and return the real url.
        logging.info('short url: {}'.format(url))
        new_url = requests.get(url, headers=HEADERS).url
        if len(new_url) < min_url_length:
            logging.warning('Unable to expand url: ({}, {})'.format(url, new_url))
    except requests.exceptions.SSLError:
        logging.error('request failed')
    return new_url


def get_non_twitter_urls(urls_class):
    blacklist = ['twitter.com', 'youtube.com']
    urls = []
    if urls_class:
        for url_class in urls_class:
            long_url = expand_url_if_short(url_class.expanded_url)
            if not long_url:
                continue
            blacklisted = False
            for b in blacklist:
                if long_url.find(b) != -1:
                    blacklisted = True
            if not blacklisted:
                urls.append(long_url)
    return urls


def get_pollsters_from_file(filename):
    with open(filename, 'rb') as f:
        reader = csv.reader(f, delimiter=',')
        pollsters = [row[0] for row in reader]

    split_pollsters = []
    for p in pollsters:
        # Want to get NBC News/Wall Street Journal, but avoid 20/20 Insight
        if p.find('/') != -1 and p.find('20') == -1:
            split_pollsters += p.split('/')
    logging.info(split_pollsters)
    pollsters += split_pollsters

    pollsters_and = []
    for p in pollsters:
        if p.find('&') != -1:
            pollsters_and.append(p.replace('&', 'and'))
    logging.info(pollsters_and)
    pollsters += pollsters_and
    pollsters = list(set(pollsters))
    return pollsters


def get_postive_and_negative_cases(html, pollsters, heavy_logging=False):
    pos_cases = []
    neg_cases = []
    texts = text_from_html(html)
    if heavy_logging:
        logging.info('--------------------------\n--------------------------')
    for text in texts:
        if len(text) > 1000:
            continue
        if heavy_logging:
            logging.info(text)
        if text.find('poll') == -1 and text.find('survey') == -1:
            continue
        if heavy_logging:
            logging.info('found poll')
        found_poll = False
        for pollster in pollsters:
            if text.find(pollster) != -1:
                found_poll = True
                if heavy_logging:
                    logging.info('found poolster: {}'.format(pollster))
                pos_cases.append((text, pollster))
        if not found_poll:
            neg_cases.append(text)
    return [pos_cases, neg_cases]


def tag_visible(element):
    if element.parent.name in ['style', 'script', 'head', 'title', 'meta', '[document]']:
        return False
    if isinstance(element, Comment):
        return False
    return True


def text_from_html(body):
    soup = BeautifulSoup(body, 'html.parser')
    texts = soup.findAll(text=True)
    visible_texts = filter(tag_visible, texts)
    return visible_texts


def main():
    args = parseargs()
    logging.info('starting...')
    with open(args.secret_file) as f:
        secrets = json.load(f)

    pollsters = get_pollsters_from_file(args.pollster_csv)
    api = twitter.Api(consumer_key=secrets['APIKey'],
                      consumer_secret=secrets['APISecret'],
                      access_token_key=secrets['AccessToken'],
                      access_token_secret=secrets['AccessTokenSecret'])

    term = 'new poll'
    since = '2017-9-03'
    until = '2017-9-07'
    results = paginated_query(api=api, term=term, since=since, until=until,
                              use_cache=True, be_nice=True)
    min_reweets = 2
    all_positive_cases = []
    all_negative_cases = []
    for result in results:
        if (result.retweet_count > min_reweets) and (result.retweeted_status is None):
            urls = get_non_twitter_urls(result.urls)
            if len(urls) > 0:
                for u in urls:
                    try:
                        content = requests.get(u, headers=HEADERS).content
                        pos_cases, neg_cases = get_postive_and_negative_cases(content, pollsters)
                        all_positive_cases += pos_cases
                        all_negative_cases += neg_cases
                    except requests.exceptions.SSLError:
                        logging.error('request failed')
                logging.info('---------------------------------------')
                logging.info(u'text: \n\t{}'.format(result.text))
                logging.info(u'result.urls: \n\t{}'.format(result.urls))
                logging.info(u'urls: \n\t{}'.format(urls))
                logging.info(u'retweet count: {}'.format(result.retweet_count))
                logging.info(u'user name: {}'.format(result.user.name))
                logging.info(u'tweet id: {}'.format(result.id))
                logging.info(u'retweet status: {}'.format(result.retweeted_status is not None))

    logging.info(len(all_positive_cases), len(all_negative_cases))
    for p in all_positive_cases:
        logging.info(p)
    logging.info('--------------------------\n--------------------------')
    for p in all_negative_cases:
        logging.info(p)

    all_positive_cases = list(set(all_positive_cases))
    with open(args.positive_output, 'wb') as f:
        writer = csv.writer(f, delimiter=',')
        writer.writerows([(s[0].encode('utf-8'), s[1]) for s in all_positive_cases])

    all_negative_cases = list(set(all_negative_cases))
    with open(args.negative_output, 'wb') as f:
        writer = csv.writer(f, delimiter=',')
        rows = zip([s.encode('utf-8') for s in all_negative_cases])
        # I have to do it this way because I only have a single column.
        for row in rows:
            writer.writerow([row])


if __name__ == '__main__':
    main()
