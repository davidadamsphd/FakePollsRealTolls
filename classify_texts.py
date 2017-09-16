import argparse
import csv
import logging
import re


def load_regex_list():
    regexes = [
        re.compile(r'.*?([Aa]|[Tt]he) (new)?(?P<poll>.{3,50}?) poll'),
        re.compile(r'Results for this (?P<poll>.{3,50}?) poll'),
        re.compile(r'(?P<poll>.{3,50}?) ran the survey'),
        re.compile(r'.*? a just-released (?P<poll>.{3,50}?) poll'),
        re.compile(r'.*? in (?P<poll>.{3,50}?) polling history'),
        re.compile(r'.*? a separate (?P<poll>.{3,50}?) survey'),
        re.compile(r'[Ii]n the (?P<poll>.{3,50}?) poll[,.]'),
        re.compile(r'The survey (?:.+) was conducted by (?P<poll>.{3,50}?) between'),
        re.compile(r'^(?P<poll>.{3,50}?) ran the survey.'),
        re.compile(r'.*?[Aa]ccording to a (new)?(national)?(?P<poll>.{3,50}?) poll.'),
        re.compile(r'.*?[Rr]esults from a (new)?(?P<poll>.{3,50}?) poll'),
        re.compile(r'.*? a new (?P<poll>.{3,50}?) poll reports'),
        re.compile(r'.*?([Tt]he)? (?P<poll>.{3,50}?) also released a (similar)? survey'),
        re.compile(r'.*?(a)? (new)? poll from (?P<poll>.{3,50}?).')
    ]
    return regexes


def parseargs():
    parser = argparse.ArgumentParser(
        description='Runner for this script.'
    )
    parser.add_argument("-v", "--verbose", help="increase output verbosity",
                        action="store_true")
    parser.add_argument("--positive-csv", help="csv file to write with positive cases",
                        required=True)
    parser.add_argument("--negative-csv", help="csv file to write with negative cases",
                        required=True)
    args = parser.parse_args()
    if args.verbose:
        logging.basicConfig(level=logging.INFO)
    return args


def load_positive_cases(filename):
    with open(filename, 'rb') as f:
        reader = csv.reader(f, delimiter=',')
        cases = []
        for row in reader:
            cases.append((row[0].decode('utf-8'), row[1].decode('utf-8')))
        return cases


def load_negative_cases(filename):
    with open(filename, 'rb') as f:
        reader = csv.reader(f, delimiter=',')
        cases = []
        for row in reader:
            cases.append((row[0].decode('utf-8')))
        return cases


def find_pollster_in_string(s, regex_list):
    pollsters = []
    for r in regex_list:
        m = r.match(s)
        if m:
            pollsters.append(m.group('poll'))
    return pollsters


def main():
    args = parseargs()
    pos_cases = load_positive_cases(args.positive_csv)
    regex_list = load_regex_list()

    for s in pos_cases:
        print(s[0], find_pollster_in_string(s[0], regex_list))
    # for s in pos_cases:
    #     print(s)


if __name__ == '__main__':
    main()
