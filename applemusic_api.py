import re
import base64
import pbkdf2
import hashlib

from Cryptodome.Hash import SHA256

from uuid import uuid4
from utils.utils import create_requests_session

from .fingerprint import Fingerprint


import srp._pysrp as srp
srp.rfc5054_enable()
srp.no_username_in_x()

def b64enc(data):
    return base64.b64encode(data).decode()

def b64dec(data):
    return base64.b64decode(data)


class AppleMusicApi(object):
    def __init__(self, exception, storefront='US', language='en-US', lyrics_resource='lyrics'):
        self.s = create_requests_session()
        self.api_base = 'https://amp-api.music.apple.com/v1/'

        self.storefront = storefront
        self.language = language
        self.lyrics_storefront = storefront
        self.lyrics_language = language
        self.lyrics_resource = lyrics_resource

        self.access_token = ''
        self.user_token = ''

        self.exception = exception
        
        self.user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.5060.66 Safari/537.36'

    def headers(self):
        return {
            'authorization': 'Bearer ' + self.access_token,
            'Connection': 'Keep-Alive',
            'Content-Type': 'application/json',
            'Origin': 'https://music.apple.com',
            'Referer': 'https://music.apple.com/',
            'Accept-Encoding': 'gzip, deflate',
            'Accept-Language': f'{self.language},en;q=0.9',
            'User-Agent': self.user_agent,
            'Media-User-Token': self.user_token,
            'x-apple-renewal': 'true'
        }
    
    def get_access_token(self):
        s = create_requests_session()
        r = s.get('https://music.apple.com/us/search', headers=self.headers())
        if r.status_code != 200: raise self.exception(r.text)

        index_js = re.search('(?<=index\-)(.*?)(?=\.js")', r.text).group(1)
        r = s.get(f'https://music.apple.com/assets/index-{index_js}.js', headers=self.headers())
        if r.status_code != 200: raise self.exception(r.text)

        self.access_token = re.search('(?=eyJh)(.*?)(?=")', r.text).group(1)
        return self.access_token
    
    def auth(self, email: str, password: str):
        auth_url = 'https://idmsa.apple.com/appleauth/'
        client_id = '06f8d74b71c73757a2f82158d5e948ae7bae11ec45fda9a58690f55e35945c51'
        frame_id = 'auth-' + str(uuid4()).lower()
        
        # get "dslang", "site" and "aasp" cookies
        r = self.s.get(auth_url + 'auth/authorize/signin', headers=self.headers(), params={
            'frame_id': frame_id,
            'language': 'en_us',
            'skVersion': '7',
            'iframeId': frame_id,
            'client_id': client_id,
            'redirect_uri': 'https://music.apple.com',
            'response_type': 'code',
            'response_mode': 'web_message',
            'account_ind': '1',
            'state': frame_id,
            'authVersion': 'latest'
        })
        if r.status_code != 200:  raise self.exception(r.text)
        auth_attributes = r.headers['X-Apple-Auth-Attributes']

        # get "aa" cookie
        r = self.s.post(auth_url + 'jslog', headers=self.headers(), json={
            'type': 'INFO',
            'title': 'AppleAuthPerf-s-y',
            'message': '''APPLE ID : TTI {"data":{"initApp":{"startTime":1154.2000000001863},"loadAuthComponent":{"startTime":1500.7000000001863},"startAppToTTI":{"duration":346.70000000018626}},"order":["initApp","loadAuthComponent","startAppToTTI"]}''',
            'iframeId': frame_id,
            'details': '''{"pageVisibilityState":"visible"}'''
        })
        assert (r.status_code == 200)

        # actual login
        headers = {
            'Accept': 'application/json',
            'Referer': 'https://idmsa.apple.com/',
            'Content-Type': 'application/json',
            'X-Apple-Widget-Key': client_id,
            'X-Apple-Frame-Id': frame_id,
            'X-Apple-Domain-Id': '3',
            'X-Apple-Locale': 'en_us',
            'X-Requested-With': 'XMLHttpRequest',
            'Origin': 'https://idmsa.apple.com',
            'X-Apple-I-Require-UE': 'true',
            'X-Apple-I-FD-Client-Info': '{' + f'"U":"{self.user_agent}","L":"{self.language}","Z":"GMT-8:00","V":"1.1","F":"{Fingerprint().create_fingerprint()}"' + '}',
            'X-Apple-Auth-Attributes': auth_attributes,
            'User-Agent': self.user_agent,
            'X-Apple-Mandate-Security-Upgrade': '0'
        }
        
        json_ = {'accountName': email, 'rememberMe': 'false'}
        params_ = {'isRememberMeEnabled': 'false'}
        
        r = self.s.post(auth_url + 'auth/federate', headers=headers, params=params_, json=json_)
        if 'federated' not in r.json(): raise self.exception(r.text)
        
        # finally begin login
        user = srp.User(email, bytes(), hash_alg=srp.SHA256, ng_type=srp.NG_2048)
        _, A = user.start_authentication()
        
        json_ = {'a': b64enc(A), 'accountName': email, 'protocols': ['s2k', 's2k_fo']}

        r = self.s.post(auth_url + 'auth/signin/init', headers=headers, json=json_)
        out_json = r.json()
        if r.status_code != 200: raise self.exception(out_json['serviceErrors'][0]['message'])
        if 'b' not in out_json: raise self.exception(r.text)
        if out_json.get('protocol') != 's2k': raise self.exception('Protocol not supported')
        
        salt = b64dec(out_json['salt'])
        iterations = out_json['iteration']
        B = b64dec(out_json['b'])
        c = out_json['c']
        
        pass_hash = hashlib.sha256(password.encode("utf-8")).digest()
        enc_pass = pbkdf2.PBKDF2(pass_hash, salt, iterations, SHA256).read(32)
        
        user.p = enc_pass
        M1 = user.process_challenge(salt, B)
        if M1 is None: raise self.exception("Failed to process challenge")
        
        M2 = user.K
        
        # real version uses m2 as well... hmmm
        json_ = {'accountName': email, 'c': c, 'm1': b64enc(M1), 'm2': b64enc(M2), 'rememberMe': 'false'}
        
        r = self.s.post(auth_url + 'auth/signin/complete', headers=headers, params=params_, json=json_)
        if r.status_code != 200: raise self.exception(r.json()['serviceErrors'][0]['message'])

        # exchange the "myacinfo" cookie with the "media-user-token"
        r = self.s.post('https://buy.music.apple.com/account/web/auth', headers=self.headers(), json={'webAuthorizationFlowContext': 'music'})
        if r.status_code != 200: raise self.exception(r.text)

        self.user_token = self.s.cookies['media-user-token']
        return self.user_token

    def get_account_details(self, force_region, selected_language, lyrics_language):
        r = self.s.get(self.api_base + 'me/account', headers=self.headers(), params={'meta': 'subscription'})
        if r.status_code != 200: raise self.exception(r.text)

        self.lyrics_storefront = r.json()['meta']['subscription']['storefront']
        if force_region.lower() == self.lyrics_storefront: force_region = None
        if force_region: print(f"Apple Music: WARNING: Selected region {force_region} is not the same as your Apple Music region {self.lyrics_storefront}, lyrics will use the region {self.lyrics_storefront}. Only lyrics available in both regions will be used, maybe use a copy of the module with the folder name (which determines the name of the module) and the netlocation_constant changed for lyrics only if you want credits or playlists from other regions.")

        self.storefront = force_region.lower() if force_region else self.lyrics_storefront
        account_active = r.json()['meta']['subscription']['active']
        
        storefront_endpoint = f'storefronts/{force_region.lower()}' if force_region else 'me/storefront'
        endpoint_data = self.s.get(self.api_base + storefront_endpoint, headers=self.headers())
        if endpoint_data.status_code != 200: raise self.exception(f'Region {force_region} is not supported')

        supported_languages = endpoint_data.json()['data'][0]['attributes']['supportedLanguageTags']
        if selected_language:
            for i in supported_languages:
                if selected_language in i:
                    self.language = i
                    break
            else:
                print(f"Apple Music: WARNING: Selected language {selected_language} in region {force_region if force_region else self.lyrics_storefront} is unsupported, force a different region or use one of these: {', '.join(supported_languages)}")
                self.language = supported_languages[0]
        else:
            self.language = supported_languages[0]

        if not lyrics_language: lyrics_language = selected_language

        if force_region:
            supported_languages = self.s.get(f'{self.api_base}me/storefront', headers=self.headers()).json()['data'][0]['attributes']['supportedLanguageTags']
            if lyrics_language:
                for i in supported_languages:
                    if selected_language in i:
                        self.lyrics_language = i
                        break
                else:
                    print(f"Apple Music: WARNING: Selected language {selected_language} in lyrics region {self.lyrics_storefront} is unsupported, force a different region or use one of these: {', '.join(supported_languages)}")
                    self.lyrics_language = supported_languages[0]
            else:
                self.lyrics_language = supported_languages[0]

        return self.storefront, account_active, self.language, self.lyrics_language, self.lyrics_storefront

    def check_active_subscription(self):
        url = f'{self.api_base}me/account'
        params = {'meta': 'subscription', 'challenge[subscriptionCapabilities]': 'voice,premium'}

        response = self.s.get(url, headers=self.headers(), params=params)
        if response.status_code != 200: raise self.exception(response.text)
        response_data = response.json()

        if 'meta' in response_data and 'subscription' in response_data['meta']:
            return response_data['meta']['subscription'].get('active', False)

        return False

    def _get(self, url: str, params=None, storefront=None, language=None):
        if not params: params = {}
        if not storefront: storefront = self.storefront
        params['l'] = language if language else self.language

        r = self.s.get(f'{self.api_base}catalog/{storefront}/{url}', params=params, headers=self.headers())
        if r.status_code not in [200, 201, 202]: raise self.exception(r.text)

        return r.json()

    def search(self, query_type: str, query: str, limit: int = 10):
        if limit > 25: limit = 25

        params = {
            'term': query,
            'types': query_type,
            'limit': limit
        }

        if query_type == 'songs':
            params['extend[songs]'] = 'attribution,composerName,contentRating,discNumber,durationInMillis,isrc,movementCount,movementName,movementNumber,releaseDate,trackNumber,workNamedata'
            params['include[songs]'] = 'artists,albums' + (f',{self.lyrics_resource}' if self.storefront == self.lyrics_storefront else '') # doesn't give lyrics?
            params['extend[albums]'] = 'copyright,upc'
        elif query_type == 'playlists':
            params['include[playlists]'] = 'curator'
            params['extend[playlists]'] = 'artwork,description,trackTypes,trackCount'
        
        results = self._get('search', params)['results']
        if query_type in results:
            results = results[query_type]['data']
        else:
            results = []
        
        return results
    
    def get_playlist_base_data(self, playlist_id):
        return self._get(f'playlists/{playlist_id}', params={
            'include': 'curator,tracks',
            'extend': 'artwork,description,trackTypes,trackCount',
            'include[songs]': 'artists,albums' + (f',{self.lyrics_resource}' if self.storefront == self.lyrics_storefront else ''),
            'extend[songs]': 'extendedAssetUrls,attribution,composerName,contentRating,discNumber,durationInMillis,isrc,movementCount,movementName,movementNumber,releaseDate,trackNumber,workNamedata',
            'extend[albums]': 'copyright,upc'
        })['data'][0]

    def get_playlist_tracks(self, playlist_data):
        tracks_list, track_data = [], {}
        tracks = list(playlist_data['relationships']['tracks']['data'])
        offset = len(tracks)

        while len(tracks) + offset <= playlist_data['attributes']['trackCount']:
            tracks += self._get(f'playlists/{playlist_data["id"]}/tracks', params={
                'offset': offset,
                'include[songs]': 'artists,albums' + (f',{self.lyrics_resource}' if self.storefront == self.lyrics_storefront else ''),
                'extend[songs]': 'extendedAssetUrls,attribution,composerName,contentRating,discNumber,durationInMillis,isrc,movementCount,movementName,movementNumber,releaseDate,trackNumber,workNamedata',
                'extend[albums]': 'copyright,upc',
                'limit': 100
            })['data']
            offset += 100

        for track in tracks:
            tracks_list.append(track['id'])
            track_data[track['id']] = track

        return tracks_list, track_data

    def get_tracks_by_ids(self, track_ids: list = None, isrc: str = None):
        if not track_ids: track_ids = []

        params = {'filter[isrc]': isrc} if isrc else {'ids': ','.join(track_ids)}
        params['include'] = 'artists,albums' + (f',{self.lyrics_resource}' if self.storefront == self.lyrics_storefront else '')
        params['extend'] = 'attribution,composerName,contentRating,discNumber,durationInMillis,isrc,movementCount,movementName,movementNumber,releaseDate,trackNumber,workNamedata'
        params['extend[albums]'] = 'copyright,upc'

        return self._get('songs', params)['data']

    def get_track(self, track_id: str = None):
        return self.get_tracks_by_ids([track_id])[0]
    
    @staticmethod
    def get_lyrics_support(track_attributes):
        # could technically be a single line in the lambda
        if track_attributes.get('hasTimeSyncedLyrics'):
            return 1 if track_attributes.get('isVocalAttenuationAllowed') else 2
        else:
            return 3 if track_attributes.get('hasLyrics') else 4
    
    def get_track_by_isrc(self, isrc: str, album_name: str):
        results = self.get_tracks_by_ids(isrc=isrc)

        correct_region_results = [i for i in results if i['attributes']['url'].split('i=')[-1].split('&')[0] == i['id']]
        incorrect_region_results = [i for i in results if i['attributes']['url'].split('i=')[-1].split('&')[0] != i['id']]

        correct_region_results_sorted_by_track_number = sorted(correct_region_results, key=lambda x: x['attributes'].get('trackNumber', 1))
        
        fix_results_by_album = lambda list_to_sort: sorted(list_to_sort, key=lambda x: (x['attributes']['albumName'] != album_name))
        correct_album_correct_region_results = fix_results_by_album(correct_region_results_sorted_by_track_number)
        correct_album_incorrect_region_results = fix_results_by_album(incorrect_region_results)

        correct_album_prioritised_lyrics_results = sorted(correct_album_correct_region_results, key=lambda x: self.get_lyrics_support(x['attributes']))
        return correct_album_prioritised_lyrics_results + correct_album_incorrect_region_results

    def get_lyrics(self, track_id, lyrics_resource=None):
        if not lyrics_resource: lyrics_resource = self.lyrics_resource

        try:
            data = self._get(f'songs/{track_id}/{lyrics_resource}', storefront=self.lyrics_storefront, language=self.language)
        except self.exception:
            return None

        return data#['data'][0]['attributes']['ttml']
