import xmltodict
import base64
import json

from urllib.parse import urlparse

from utils.models import *

from .applemusic_api import AppleMusicApi


module_information = ModuleInformation(
    service_name = 'Apple Music (Basic Support)',
    module_supported_modes = ModuleModes.covers | ModuleModes.lyrics | ModuleModes.credits | ModuleModes.playlist,
    session_settings = {'user_token': ''},
    session_storage_variables=[
        'storefront', 'language', 'lyrics_language', 'lyrics_storefront',
        'verified_storefront', 'verified_language', 'verified_lyrics_language', 'verified_user_token',
        'access_token'
    ],
    global_settings = {
        'force_region': '',
        'selected_language': 'en',
        'get_original_cover': True,
        'print_original_cover_url': False,
        'lyrics_type': 'standard', # 'custom' or 'standard'
        'lyrics_custom_ms_sync': False,
        'lyrics_language_override': ''
    },
    netlocation_constant = 'apple',
    test_url = 'https://music.apple.com/us/playlist/beat-saber-x-monstercat/pl.0ccb67a275dc416c9dadd6fe1f80d518',
    url_decoding = ManualEnum.manual,
    login_behaviour = ManualEnum.manual
)


class ModuleInterface:
    def __init__(self, module_controller: ModuleController):
        self.tsc = module_controller.temporary_settings_controller
        self.module_controller = module_controller
        self.msettings = module_controller.module_settings

        self.session = AppleMusicApi(module_controller.module_error, self.msettings['user_token'])

        access_token = self.tsc.read('access_token')
        if access_token and json.loads(base64.b64decode(access_token.split('.')[1] + '==').decode('utf-8'))['exp'] > module_controller.get_current_timestamp():
            self.session.access_token = access_token
        else:
            self.tsc.set('access_token', self.session.get_access_token())

        if self.tsc.read('storefront') and self.tsc.read('language') and self.tsc.read('lyrics_language') and self.tsc.read('verified_storefront') == self.msettings['force_region'] and self.tsc.read('verified_language') == self.msettings['selected_language'] and self.tsc.read('verified_lyrics_language') == self.msettings['lyrics_language_override'] and self.tsc.read('verified_user_token') == self.msettings['user_token']:
            self.session.storefront = self.tsc.read('storefront')
            self.session.language = self.tsc.read('language')
            self.session.lyrics_storefront = self.tsc.read('lyrics_storefront')
            self.session.lyrics_language = self.tsc.read('lyrics_language')
        else:
            self.set_regions()
    
    def set_regions(self):
        account_storefront, language_tag, lyrics_language_tag, lyrics_storefront = self.session.get_languages(self.msettings['force_region'], self.msettings['selected_language'], self.msettings['lyrics_language_override'])
        
        self.tsc.set('storefront', account_storefront)
        self.tsc.set('language', language_tag)
        self.tsc.set('lyrics_language', lyrics_language_tag)
        self.tsc.set('lyrics_storefront', lyrics_storefront)
        
        self.tsc.set('verified_storefront', self.msettings['force_region'])
        self.tsc.set('verified_language', self.msettings['selected_language'])
        self.tsc.set('verified_lyrics_language', self.msettings['lyrics_language_override'])
        self.tsc.set('verified_user_token', self.msettings['user_token'])

    @staticmethod
    def custom_url_parse(link):
        url = urlparse(link)
        components = url.path.split('/')
        if not components or len(components) < 4:
            print('Invalid URL: ' + link)
            exit()

        if components[2] == 'playlist':
            return MediaIdentification(
                media_type = DownloadTypeEnum.playlist,
                media_id = components[-1].split('?')[0].split('.')[-1]
            )
        else:
            print('Unsupported URL: ' + link)
            exit()

    def parse_cover_url(self, unparsed_url, resolution, compression_level: CoverCompressionEnum, file_format=ImageFileTypeEnum.jpg):
        if file_format is ImageFileTypeEnum.png and (self.msettings['get_original_cover'] or self.msettings['print_original_cover_url']):
            result = 'https://a1.mzstatic.com/r40/' + '/'.join(unparsed_url.split('/')[5:-1])
            if self.msettings['print_original_cover_url']: 
                self.module_controller.printer_controller.oprint('Original cover URL: ' + result)

            if self.msettings['get_original_cover']:
                cover_extension = unparsed_url.split('.')[-1]
                if cover_extension not in [i.name for i in ImageFileTypeEnum]:
                    raise self.module_controller.module_error('Invalid cover extension: ' + cover_extension)
                
                return result, ImageFileTypeEnum[cover_extension]
        
        if compression_level is CoverCompressionEnum.low:
            compression = '-100'
        elif compression_level is CoverCompressionEnum.high:
            compression = '-0'
        crop_code = ''
        
        # while Apple Music doesn't use the compression modifier, we use the crop code position in the format string for convenience
        final_crop_code = crop_code + compression

        url = unparsed_url.format(w=resolution, h=resolution, c=final_crop_code, f=file_format.name).replace('bb.', compression+'.')
        url = f'{url.rsplit(".", 1)[0]}.{file_format.name}'
        return url, file_format

    def get_track_cover(self, track_id, cover_options: CoverOptions, data = {}):
        track_data = data[track_id] if track_id in data else self.session.get_track(track_id)
        
        cover_url, cover_type = self.parse_cover_url(
            unparsed_url = track_data['attributes']['artwork']['url'],
            resolution = cover_options.resolution,
            compression_level = cover_options.compression,
            file_format = cover_options.file_type
        )
        
        return CoverInfo(
            url = cover_url,
            file_type = cover_type
        )

    def get_playlist_info(self, playlist_id, data={}):
        cover_options = self.module_controller.orpheus_options.default_cover_options
        playlist_data = data[playlist_id] if playlist_id in data else self.session.get_playlist_base_data(playlist_id)
        if 'tracks' not in playlist_data.get('relationships', {}):
            if 'relationships' not in playlist_data: playlist_data['relationships'] = {}
            playlist_data['relationships']['tracks'] = {}
            playlist_data['relationships']['tracks']['data'] = {}
        tracks_list, track_data = self.session.get_playlist_tracks(playlist_data)
        playlist_info = playlist_data['attributes']

        cover_url, cover_type = self.parse_cover_url(
            unparsed_url = playlist_data['attributes']['artwork']['url'],
            resolution = cover_options.resolution,
            compression_level = cover_options.compression,
            file_format = cover_options.file_type
        )

        return PlaylistInfo(
            name = playlist_info['name'],
            creator = playlist_info['curatorName'],
            tracks = tracks_list,
            release_year = playlist_info['lastModifiedDate'].split('-')[0] if playlist_info.get('lastModifiedDate') else None,
            cover_url = cover_url,
            cover_type = cover_type,
            track_extra_kwargs = {'data': track_data}
        )
    
    def get_track_info(self, track_id, quality_tier: QualityEnum, codec_options: CodecOptions, data={}, total_discs=None):
        cover_options = self.module_controller.orpheus_options.default_cover_options
        track_data = data[track_id] if track_id in data else self.session.get_track(track_id)
        track_relations = track_data['relationships']
        track_info = track_data['attributes']
        if not 'lyrics' in track_relations: track_relations['lyrics'] = self.session.get_lyrics(track_id)

        return TrackInfo(
            name = track_info['name'],
            release_year = track_info.get('releaseDate', '').split('-')[0],
            album_id = track_relations['albums']['data'][0]['id'],
            album = track_info['albumName'],
            artists = [i['attributes']['name'] for i in track_relations['artists']['data']],
            artist_id = track_relations['artists']['data'][0]['id'],
            duration = track_info['durationInMillis'] // 1000,
            explicit = track_info.get('contentRating') == 'explicit',
            codec = CodecEnum.FLAC,
            cover_url = self.parse_cover_url(
                unparsed_url = track_info['artwork']['url'],
                resolution = cover_options.resolution,
                compression_level = cover_options.compression,
                file_format = ImageFileTypeEnum.jpg
            )[0],
            tags = Tags(
                album_artist = track_relations['albums']['data'][0]['attributes']['artistName'],
                track_number = track_info.get('trackNumber'),
                total_tracks = track_relations['albums']['data'][0]['attributes'].get('trackCount'),
                disc_number = track_info.get('discNumber'),
                total_discs = total_discs,
                genres = track_info.get('genreNames'),
                isrc = track_info.get('isrc'),
                upc = track_relations['albums']['data'][0]['attributes'].get('upc'),
                copyright = track_relations['albums']['data'][0]['attributes'].get('copyright'),
                composer = track_info.get('composerName'),
                release_date = track_info.get('releaseDate')
            ),
            description = track_info.get('editorialNotes', {}).get('standard'),
            cover_extra_kwargs = {'data': {track_id: track_data}},
            lyrics_extra_kwargs = {'data': {track_id: track_data}},
            credits_extra_kwargs = {'data': {track_id: track_data}}
        )
    
    def ts_format(self, input_ts):
        mins = int(input_ts.split(':')[-2]) if ':' in input_ts else 0
        # strip the "s" from the float value
        secs = float(input_ts.split(':')[-1]) if ':' in input_ts else float(input_ts.replace('s', ''))
        # yeah really hacky, don't do that, needs a proper timestamp parser
        if mins == 0:
            mins = int(secs // 60)
            secs = secs % 60
        return f'{mins:0>2}:{secs:06.3f}' if self.msettings['lyrics_custom_ms_sync'] else f'{mins:0>2}:{secs:05.2f}'
    
    def get_track_lyrics(self, track_id, data = {}):
        if track_id in data:
            if 'lyrics' in data[track_id]['relationships'] and data[track_id]['relationships']['lyrics'] and data[track_id]['relationships']['lyrics']['data']:
                lyrics_xml = data[track_id]['relationships']['lyrics']['data'][0]['attributes']['ttml']
            elif data[track_id]['attributes']['hasLyrics']:
                lyrics_data = self.session.get_lyrics(track_id)
                lyrics_xml = lyrics_data['data'][0]['attributes']['ttml'] if lyrics_data else None
            else:
                lyrics_xml = None
        else:
            lyrics_xml = self.session.get_lyrics(track_id)['data'][0]['attributes']['ttml']
        
        if not lyrics_xml: return LyricsInfo(embedded=None, synced=None)

        lyrics_dict = xmltodict.parse(lyrics_xml)
        # print(json.dumps(lyrics_dict, indent=4, sort_keys=True))
        if lyrics_dict['tt']['@itunes:timing'] != 'Line' and lyrics_dict['tt']['@itunes:timing'] != 'None': raise Exception(f"Unknown lyrics format {lyrics_dict['tt']['@itunes:timing']}")
        
        synced_lyrics_list = []
        unsynced_lyrics_list = []
        
        verses = lyrics_dict['tt']['body']['div']
        if not isinstance(verses, list): verses = [verses]
        
        for verse in verses:
            # using:
            # [start new line timestamp]lyrics<end new line timestamp>
            # also, there's the enhanced format that we don't use which is:
            # [last line end timestamp] <start new line timestamp> lyrics 
            
            lines = verse['p']
            if not isinstance(lines, list): lines = [lines]
            
            if '#text' in lines[0]:
                for line in lines:
                    if lyrics_dict['tt']['@itunes:timing'] == 'Line':
                        new_line = f"[{self.ts_format(line['@begin'])}]{line['#text']}"
                        if self.msettings['lyrics_type'] == 'custom': new_line += f"<{self.ts_format(line['@end'])}>"
                        synced_lyrics_list.append(new_line)
                    unsynced_lyrics_list.append(line['#text'])
            else:
                unsynced_lyrics_list += lines
            
            if lyrics_dict['tt']['@itunes:timing'] == 'Line': synced_lyrics_list.append(f"[{self.ts_format(verse['@end'])}]")
            unsynced_lyrics_list.append('')

        return LyricsInfo(
            embedded = '\n'.join(unsynced_lyrics_list[:-1]),
            synced = '\n'.join(synced_lyrics_list[:-1])
        )

    def get_track_credits(self, track_id, data = {}):
        if track_id in data:
            if 'lyrics' in data[track_id]['relationships'] and data[track_id]['relationships']['lyrics'] and data[track_id]['relationships']['lyrics']['data']:
                lyrics_xml = data[track_id]['relationships']['lyrics']['data'][0]['attributes']['ttml']
            elif data[track_id]['attributes']['hasLyrics']:
                lyrics_data = self.session.get_lyrics(track_id)
                lyrics_xml = lyrics_data['data'][0]['attributes']['ttml'] if lyrics_data else None
            else:
                lyrics_xml = None
        else:
            lyrics_xml = self.session.get_lyrics(track_id)['data'][0]['attributes']['ttml']

        if not lyrics_xml: return []
        
        lyrics_dict = xmltodict.parse(lyrics_xml)
        return [CreditsInfo('Lyricist', lyrics_dict['tt']['head']['metadata']['iTunesMetadata']['songwriters']['songwriter'])]
        

    def search(self, query_type: DownloadTypeEnum, query, track_info: TrackInfo = None, limit = 10):
        if track_info and track_info.tags.isrc:
            results = [self.session.get_track(isrc=track_info.tags.isrc)]
        if not (track_info and track_info.tags.isrc) or not results:
            results = self.session.search(query_type.name + 's' if query_type is not DownloadTypeEnum.track else 'songs', query, limit)

        return [SearchResult(
                name = i['attributes']['name'],
                artists = [j['attributes']['name'] for j in i['relationships']['artists']['data']] if query_type in [DownloadTypeEnum.album, DownloadTypeEnum.track] else [i['attributes']['curatorName']] if query_type is DownloadTypeEnum.playlist else [],
                result_id = str(i['id']),
                explicit = i['attributes'].get('contentRating') == 'explicit',
                additional = [format_ for format_ in i['attributes']['audioTraits']] if 'audioTraits' in i['attributes'] else None,
                extra_kwargs = {'data': {i['id']: i}}
            ) for i in results]
