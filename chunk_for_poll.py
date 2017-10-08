import csv
import requests
import nltk
from unidecode import unidecode

import get_trainig_data


def contains_poll_survey(noun_phrase):
    # Notes: could disallow 'JJ' in the phrase...
    for word in noun_phrase:
        if word[0] in set(['poll', 'survey']) and word[1] == 'NN':
            return True
    return False


def search_for_pollster(sentence, poll_idx, search_backwards=True, extra_logging=False):
    if search_backwards:
        start_idx = poll_idx - 1
        delta = -1
        end_idx = -1
    else:
        start_idx = poll_idx + 1
        delta = 1
        end_idx = len(sentence)

    first_nnp_idx = None
    last_nnp_idx = None

    # Notes: possible breaks: WDT, VBD, VBZ, VBG, VB
    # Edges cases: forward NNP followed by VBD, VBZ, VBG, VB
    # Aggressive: cannot have VBD, VBZ, VBG, VB between poll and pollster

    for j in range(start_idx, end_idx, delta):
        if extra_logging:
            print(sentence[j])
        if isinstance(sentence[j], nltk.tree.Tree):
            if not first_nnp_idx:
                continue
            else:
                break
        if sentence[j][1] in set(['NNP', 'NNPS']):
            last_nnp_idx = j
            if not first_nnp_idx:
                first_nnp_idx = j
        else:
            if not first_nnp_idx:
                # Don't allow verbs in between poll and pollster (allow VBD)
                # Don't allow JJS (maybe not JJR, JJ)
                if sentence[j][1] in set(['VBZ', 'VBG', 'VB', 'JJS']):
                    break
                else:
                    continue
            if sentence[j][1] not in set(['CC']):
                break
    if not first_nnp_idx:
        if extra_logging:
            print('unable to find an NNP or NNPS')
        return None, None

    if not search_backwards:
        if (last_nnp_idx+1) < (len(sentence)-1):
            if not isinstance(sentence[j], nltk.tree.Tree) and (
                        sentence[last_nnp_idx+1][1] in set(['VBD', 'VBZ', 'VBG', 'VB'])):
                if extra_logging:
                    print('found verb directly after NNP phrase')
                return None, None

    if extra_logging:
        print('indicies: {} {}'.format(first_nnp_idx, last_nnp_idx+1))
    if search_backwards:
        first_nnp_idx, last_nnp_idx = last_nnp_idx, first_nnp_idx
    # Make sure that the phrase isn't too far from poll.
    min_dist = min(abs(poll_idx - first_nnp_idx), abs(poll_idx - last_nnp_idx))
    # Make sure there is at least one NNP in the phrase
    found_nnp = False
    for i in range(first_nnp_idx, last_nnp_idx+1):
        if sentence[i][1] == 'NNP':
            found_nnp = True
            break
    if not found_nnp:
        return None, None

    pollster = [w[0] for w in [sentence[i] for i in range(first_nnp_idx, last_nnp_idx+1)]]
    return ' '.join(pollster), min_dist


def find_pollster(p, extra_logging=False):
    grammar = "NP: {<DT>?<JJ>*<NN>}"
    cp = nltk.RegexpParser(grammar)
    parsed = cp.parse(nltk.pos_tag(p))
    if extra_logging:
        print('=============')
        print(parsed)
    pollster = None
    # The algorithm is:
    # 1) Try to find a noun phrase (NP) with poll or survey in it (as a common noun NN)
    # 2) Search forward and backward for a sequence of proper noun phrases (NNP)
    #   a) Limit how far forward (and backward) to search  (TODO)
    #   b) Find a good heuristic for other parts of speech that can be part of the NNP

    for i, word in enumerate(parsed):
        if isinstance(word, nltk.tree.Tree):
            # We're looking for Noun Phrases with the word poll or survey in it
            if contains_poll_survey(word):
                # Back track to find the polling firm
                if extra_logging:
                    print('searching for pollster')
                b_pollster, b_distance = search_for_pollster(
                    parsed, i, search_backwards=True, extra_logging=extra_logging)
                f_pollster, f_distance = search_for_pollster(
                    parsed, i, search_backwards=False, extra_logging=extra_logging)

                if not b_pollster and not f_pollster:
                    continue
                if not b_pollster and f_pollster:
                    pollster = f_pollster
                    break
                if b_pollster and not f_pollster:
                    pollster = b_pollster
                    break

                if b_distance <= f_distance:
                    pollster = b_pollster
                    break
                else:
                    pollster = f_pollster
                    break
    return pollster


def get_possible_sentences_from_url(url):
    content = requests.get(url).content
    texts = get_trainig_data.text_from_html(content)
    prob_texts = [t for t in texts if len(t) > 100]
    document = unidecode(''.join(prob_texts))
    sentences = nltk.sent_tokenize(document)

    sentences_pos = [nltk.word_tokenize(sent) for sent in sentences]
    return [s for s in sentences_pos if 'poll' in set(s)]


def main():
    poll_s = get_possible_sentences_from_url(
        'https://www.nbcnews.com/politics/first-read/trump-clinton-voters-divided-'
        'over-changing-america-n798926')
    # cases = 'data/positive_cases.csv'
    neg = False
    # cases = 'data/negative_cases.csv'
    # neg = True
    # with open(cases, 'rb') as f:
    #     reader = csv.reader(f)
    #     lines = [nltk.word_tokenize(unidecode(row[0].decode('utf-8'))) for row in reader]
    # poll_s = lines
    for p in poll_s:
        pollster = find_pollster(p)
        if pollster:
            print('---------- pollster: {}'.format(pollster))
            if neg:
                find_pollster(p, extra_logging=True)
        else:
            if neg:
                print('------good----')
            else:
                find_pollster(p, extra_logging=True)


if __name__ == '__main__':
    main()
