import os
from datetime import datetime, timedelta

import flask
application = flask.Flask(__name__)

import httplib2

from apiclient import discovery

from oauth2client import client
from oauth2client.file import Storage


CLIENT_SECRETS_FILE = "client_secrets.json"

YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.readonly",
                  "https://www.googleapis.com/auth/yt-analytics.readonly"]
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"
YOUTUBE_ANALYTICS_API_SERVICE_NAME = "youtubeAnalytics"
YOUTUBE_ANALYTICS_API_VERSION = "v1"


@app.route('/oauth2callback/')
def oauth2callback():
    flow = client.flow_from_clientsecrets(
        CLIENT_SECRETS_FILE,
        scope=" ".join(YOUTUBE_SCOPES),
        redirect_uri=flask.url_for(
            'oauth2callback', r=flask.request.args.get('r'),
            _external=True))

    if 'code' not in flask.request.args:
        auth_uri = flow.step1_get_authorize_url()
        return flask.redirect(auth_uri)

    auth_code = flask.request.args.get('code')
    credentials = flow.step2_exchange(auth_code)

    storage = Storage('data/%s.json' % (credentials.client_id))
    storage.put(credentials)
    return flask.redirect(flask.request.args.get('r'))


@app.route('/_admin/list')
def admin_list():
    entries = [os.path.splitext(path)[0] for path in os.listdir('data/')]
    return flask.render_template('admin_list.html', entries=entries)


@app.route('/_admin/detail/<entry_id>')
def admin_detail(entry_id):
    storage = Storage("data/%s.json" % (entry_id))
    credentials = storage.get()
    if not credentials or credentials.invalid:
        return 'Not Found', 404

    http_auth = credentials.authorize(httplib2.Http())
    youtube_service = discovery.build(YOUTUBE_API_SERVICE_NAME,
                                      YOUTUBE_API_VERSION, http=http_auth)

    youtube_analytics = discovery.build(YOUTUBE_ANALYTICS_API_SERVICE_NAME,
                                        YOUTUBE_ANALYTICS_API_VERSION,
                                        http=http_auth)

    channels_response = youtube_service.channels().list(
        mine=True,
        part="statistics"
    ).execute()

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
    app.run(debug=True)
