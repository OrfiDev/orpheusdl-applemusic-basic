import re

from utils.utils import create_requests_session


class AppleMusicApi(object):
    def __init__(self, exception, user_token, storefront='US', language='en-US', lyrics_resource='lyrics'):
        self.s = create_requests_session()
        self.api_base = 'https://amp-api.music.apple.com/v1/'

        self.storefront = storefront
        self.language = language
        self.lyrics_storefront = storefront
        self.lyrics_language = language
        self.lyrics_resource = lyrics_resource

        self.user_token = user_token
        self.access_token = ''

        self.exception = exception

    def headers(self):
        return {
            'authorization': 'Bearer ' + self.access_token,
            'Connection': 'Keep-Alive',
            'Content-Type': 'application/json',
            'Origin': 'https://music.apple.com',
            'Referer': 'https://music.apple.com/',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': f'{self.language},en;q=0.9',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/86.0.4240.183 Safari/537.36',
            'Media-User-Token': self.user_token,
            'x-apple-renewal': 'true'
        }
    
    def get_languages(self, force_region, selected_language, lyrics_language):
        r = self.s.get(f'{self.api_base}me/storefront', headers=self.headers())
        if r.status_code != 200: raise self.exception(r.text)
        r = r.json()['data'][0]

        self.lyrics_storefront = r['id']
        if force_region.lower() == self.lyrics_storefront: force_region = None
        if force_region: print(f"Apple Music: WARNING: Selected region {force_region} is not the same as your Apple Music region {self.lyrics_storefront}, lyrics will use the region {self.lyrics_storefront}. Only lyrics available in both regions will be used, maybe use a copy of the module with the folder name (which determines the name of the module) and the netlocation_constant changed for lyrics only if you want credits or playlists from other regions.")

        self.storefront = force_region.lower() if force_region else self.lyrics_storefront
        endpoint_data = self.s.get(f'{self.api_base}storefronts/{self.storefront}', headers=self.headers())
        if endpoint_data.status_code != 200: raise self.exception(f'Region {force_region} is not supported')

        supported_languages = endpoint_data.json()['data'][0]['attributes']['supportedLanguageTags'] if force_region else r['attributes']['supportedLanguageTags']
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
            supported_languages = r['attributes']['supportedLanguageTags']
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

        return self.storefront, self.language, self.lyrics_language, self.lyrics_storefront
    
    def get_access_token(self):
        s = create_requests_session()
        r = s.get('https://music.apple.com/', headers=self.headers())
        if r.status_code != 200: raise self.exception(r.text)

        index_js = re.search('(?<=index\.)(.*?)(?=\.js")', r.text).group(1)
        r = s.get(f'https://music.apple.com/assets/index.{index_js}.js', headers=self.headers())
        if r.status_code != 200: raise self.exception(r.text)

        self.access_token = re.search('(?=eyJh)(.*?)(?=")', r.text).group(1)
        return self.access_token

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
