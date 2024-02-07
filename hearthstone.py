#!/usr/bin/python3

from flask import Flask, current_app, render_template, request
from oauthlib.oauth2 import BackendApplicationClient
from requests_oauthlib import OAuth2Session
from requests.auth import HTTPBasicAuth

import random
import requests
import sys


DEFAULT_LOCALE = 'en_US'
TOKEN_URL = 'https://oauth.battle.net/token'
API_BASE_URL = 'https://us.api.blizzard.com'
HEARTHSTONE_CARDS_URL = 'https://hearthstone.blizzard.com/{locale}/cards/{slug}'


def oauth_login(client_id, client_secret):
    oauth = OAuth2Session(client=BackendApplicationClient(client_id=client_id))
    oauth.fetch_token(token_url=TOKEN_URL, auth=HTTPBasicAuth(client_id, client_secret))
    return oauth


def do_request(session, url, **params):
    response = session.get(API_BASE_URL + url, params=params)
    if response.status_code != 200:
        raise RuntimeError('GET failed ({}): {}'.format(response.url, response.status_code))
    return response.json()


def request_metadata(session, name, locale):
    entries = do_request(session, '/hearthstone/metadata/' + name, locale=locale)
    metadata = {entry['id']: entry['name'] for entry in entries}
    # HACK: Some cards have cardSetId=3, which isn't returned from the metadata endpoint.
    # Looking at the Hearthstone card browser, set 3 seems to be 'Legacy'.
    if name == 'sets':
        metadata[3] = 'Legacy'
    return metadata


def request_cards(session, class_slug, locale):
    params = {
        'rarity': 'legendary',
        'class': class_slug,
        'manaCost': '7,8,9,10',
        'locale': locale,
    }
    return do_request(session, '/hearthstone/cards', **params)


def make_card(session, card, metadata, locale):
    return {
        'id': card['id'],
        'image': card['image'],
        'name': card['name'],
        'url': HEARTHSTONE_CARDS_URL.format(locale=locale, slug=card['slug']),
        'type': metadata['types'][card['cardTypeId']],
        'rarity': metadata['rarities'][card['rarityId']],
        'set': metadata['sets'][card['cardSetId']],
        'class': metadata['classes'][card['classId']],
    }


app = Flask(__name__)


@app.route('/')
def index():
    session = current_app.config['blizzard_api_session']
    locale = request.args.get('locale', DEFAULT_LOCALE)
    metadata = {
        'types': request_metadata(session, 'types', locale),
        'rarities': request_metadata(session, 'rarities', locale),
        'sets': request_metadata(session, 'sets', locale),
        'classes': request_metadata(session, 'classes', locale),
    }

    cards = []
    for class_slug in ['warlock', 'druid']:
        for card in request_cards(session, class_slug, locale)['cards']:
            cards.append(make_card(session, card, metadata, locale))
    cards = random.sample(cards, 10)

    context = {'cards': sorted(cards, key=lambda card: card['id'])}
    return render_template('hearthstone.html', **context)


def main():
    if len(sys.argv) < 2:
        print('Usage: {} <client id> <client secret>'.format(sys.argv[0]))
        return 2
    
    client_id, client_secret = sys.argv[1:]
    session = oauth_login(client_id, client_secret)

    with app.app_context():
        current_app.config['blizzard_api_session'] = session

    app.run()


if __name__ == '__main__':
    main()
