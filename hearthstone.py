#!/usr/bin/python3

from flask import Flask, current_app, render_template
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


def do_request(session, url, params=None):
    if not params:
        params = {}
    params['locale'] = current_app.config['locale']
    response = session.get(API_BASE_URL + url, params=params)
    if response.status_code != 200:
        raise RuntimeError('GET failed ({}): {}'.format(response.url, response.status_code))
    return response.json()


def request_metadata(session, name):
    entries = do_request(session, '/hearthstone/metadata/' + name)
    return {entry['id']: entry['name'] for entry in entries}


def request_cards(session, class_slug):
    params = {
        'rarity': 'legendary',
        'class': class_slug,
        'manaCost': '7,8,9,10',
    }
    return do_request(session, '/hearthstone/cards', params)


def make_card(card):
    locale = current_app.config['locale']
    return {
        'id': card['id'],
        'image': card['image'],
        'name': card['name'],
        'url': HEARTHSTONE_CARDS_URL.format(locale=locale, slug=card['slug']),
        'type': current_app.config['hearthstone_card_types'][card['cardTypeId']],
        'rarity': current_app.config['hearthstone_card_rarities'][card['rarityId']],
        'set': current_app.config['hearthstone_card_sets'][card['cardSetId']],
        'class': current_app.config['hearthstone_card_classes'][card['classId']],
    }


app = Flask(__name__)


@app.route('/')
def index():
    session = current_app.config['blizzard_api_session']
    cards = [make_card(c) for c in request_cards(session, 'warlock')['cards']]
    cards += [make_card(c) for c in request_cards(session, 'druid')['cards']]

    context = {
        'cards': sorted(random.sample(cards, 10), key=lambda card: card['id'])
    }
    return render_template('hearthstone.html', **context)


def main():
    if len(sys.argv) < 2:
        print('Usage: {} <client id> <client secret> [<locale>]'.format(sys.argv[0]))
        return 2
    
    client_id, client_secret = sys.argv[1:3]
    session = oauth_login(client_id, client_secret)

    with app.app_context():
        current_app.config['locale'] = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_LOCALE
        current_app.config['blizzard_api_session'] = session
        current_app.config['hearthstone_card_types'] = request_metadata(session, 'types')
        current_app.config['hearthstone_card_rarities'] = request_metadata(session, 'rarities')
        current_app.config['hearthstone_card_sets'] = request_metadata(session, 'sets')
        current_app.config['hearthstone_card_classes'] = request_metadata(session, 'classes')

        # HACK: Some cards have cardSetId=3, which isn't returned from the metadata endpoint.
        # Looking at the Hearthstone card browser, set 3 seems to be 'Legacy'.
        current_app.config['hearthstone_card_sets'][3] = 'Legacy'

    app.run()


if __name__ == '__main__':
    main()
