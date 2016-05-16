import codecs
import json
import os
from datetime import datetime, timedelta

import flask
application = flask.Flask(__name__)
application.config.from_object('default_settings')
application.config.from_envvar('MOCO_SETTINGS', silent=True)
config = application.config

import httplib2

from apiclient import discovery

from oauth2client import client
from oauth2client.file import Storage


# TODO: use os.path.join everywhere

@application.route('/oauth2callback/')
def oauth2callback():
    flow = client.flow_from_clientsecrets(
        config['CLIENT_SECRETS_FILE'],
        scope=" ".join(config['YOUTUBE_SCOPES']),
        redirect_uri=flask.url_for(
            'oauth2callback',
            _external=True))

    if 'code' not in flask.request.args:
        bytes_args = bytes(json.dumps(flask.request.args), encoding='utf-8')
        args = codecs.encode(bytes_args, 'base64')
        auth_uri = flow.step1_get_authorize_url(state=args)
        return flask.redirect(auth_uri)

    # Get credentials from auth code
    auth_code = flask.request.args.get('code')
    credentials = flow.step2_exchange(auth_code)

    # Rebuild state
    state = flask.request.args.get('state')
    bytes_state = bytes(state, encoding='utf-8')
    args = json.loads(codecs.decode(bytes_state, 'base64').decode('utf-8'))

    # Persist credentials for later use
    storage = Storage('%s%s.json' % (config['DATA_DIR'], args['email']))
    storage.put(credentials)
    return flask.redirect(args['r'])


@application.route('/_admin/list')
def admin_list():
    entries = [os.path.splitext(path)[0] for path in os.listdir(
        config['DATA_DIR'])]
    return flask.render_template('admin_list.html', entries=entries)


@application.route('/_admin/detail/<entry_id>')
def admin_detail(entry_id):
    storage = Storage("%s%s.json" % (config['DATA_DIR'], entry_id))
    credentials = storage.get()
    if not credentials or credentials.invalid:
        return 'Not Found', 404

    http_auth = credentials.authorize(httplib2.Http())
    youtube_service = discovery.build(config['YOUTUBE_API_SERVICE_NAME'],
                                      config['YOUTUBE_API_VERSION'],
                                      http=http_auth)

    youtube_analytics = discovery.build(
        config['YOUTUBE_ANALYTICS_API_SERVICE_NAME'],
        config['YOUTUBE_ANALYTICS_API_VERSION'],
        http=http_auth)

    channels_response = youtube_service.channels().list(
        mine=True,
        part="id,statistics,snippet,contentDetails,topicDetails"
    ).execute()

    print(channels_response)
    channel = channels_response["items"][0]

    now = datetime.now()
    one_week_ago = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    one_month_ago = (now - timedelta(days=30)).strftime("%Y-%m-%d")

    analytics_query_response = youtube_analytics.reports().query(
        ids="channel==%s" % channel['id'],
        metrics="viewerPercentage",
        dimensions="gender",
        start_date=one_month_ago,
        end_date=one_week_ago,
        max_results=10,
        sort='gender').execute()

    print(analytics_query_response)
    for row in analytics_query_response.get("rows", []):
        pass

    # TODO only get first channel. Need to a add a nother page
    # where user can choose a channel
    return flask.render_template('admin_detail.html', entry=channel)


if __name__ == "__main__":
    application.run(host='0.0.0.0', port=80, debug=True)
