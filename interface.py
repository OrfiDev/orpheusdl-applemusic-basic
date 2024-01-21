import xmltodict
import base64
import json

from urllib.parse import urlparse

from utils.models import *

from .applemusic_api import AppleMusicApi


module_information = ModuleInformation(
    service_name = 'Apple Music (Basic Support)',
    module_supported_modes = ModuleModes.covers | ModuleModes.lyrics | ModuleModes.credits | ModuleModes.playlist,
    session_settings = {
        'email': '',
        'password': '',
        'force_region': '',
        'selected_language': 'en'
    },
    session_storage_variables=[
        'storefront', 'language', 'lyrics_language', 'lyrics_storefront',
        'verified_storefront', 'verified_language', 'verified_lyrics_language', 'verified_user_token',
        'access_token'
    ],
    global_settings = {
        'get_original_cover': True,
        'print_original_cover_url': False,
        'lyrics_type': 'standard', # 'custom' or 'standard'
        'lyrics_custom_ms_sync': False,
        'lyrics_language_override': '',
        'lyrics_syllable_sync': False
    },
    netlocation_constant = 'apple',
    test_url = 'https://music.apple.com/us/playlist/beat-saber-x-monstercat/pl.0ccb67a275dc416c9dadd6fe1f80d518',
    url_decoding = ManualEnum.manual
)


class ModuleInterface:
    def __init__(self, module_controller: ModuleController):
        self.tsc = module_controller.temporary_settings_controller
        self.module_controller = module_controller
        self.msettings = module_controller.module_settings
        self.exception = module_controller.module_error
        self.oprint = module_controller.printer_controller.oprint

        self.lyrics_resource = 'syllable-lyrics' if self.msettings['lyrics_syllable_sync'] else 'lyrics'
        if self.msettings['lyrics_syllable_sync'] and self.msettings['lyrics_type'] == 'standard': raise self.exception("Syllable synced lyrics cannot be downloaded with the standard lyrics type.")

        self.session = AppleMusicApi(self.exception, lyrics_resource=self.lyrics_resource)

        access_token = self.tsc.read('access_token')
        if access_token and json.loads(base64.b64decode(access_token.split('.')[1] + '==').decode('utf-8'))['exp'] > module_controller.get_current_timestamp():
            self.session.access_token = access_token
        else:
            self.tsc.set('access_token', self.session.get_access_token())
        
        user_token = self.tsc.read('user_token')
        if user_token:
            self.session.user_token = user_token
            # print(self.session.check_active_subscription())

        if self.tsc.read('storefront') and self.tsc.read('language') and self.tsc.read('lyrics_language') and self.tsc.read('verified_storefront') == self.msettings['force_region'] and self.tsc.read('verified_language') == self.msettings['selected_language'] and self.tsc.read('verified_lyrics_language') == self.msettings['lyrics_language_override']:
            self.session.storefront = self.tsc.read('storefront')
            self.session.language = self.tsc.read('language')
            self.session.lyrics_storefront = self.tsc.read('lyrics_storefront')
            self.session.lyrics_language = self.tsc.read('lyrics_language')
        elif user_token:
            self.set_regions()
    
    def set_regions(self):
        account_storefront, account_active, language_tag, lyrics_language_tag, lyrics_storefront = self.session.get_account_details(self.msettings['force_region'], self.msettings['selected_language'], self.msettings['lyrics_language_override'])
        
        self.tsc.set('storefront', account_storefront)
        self.tsc.set('language', language_tag)
        self.tsc.set('lyrics_language', lyrics_language_tag)
        self.tsc.set('lyrics_storefront', lyrics_storefront)
        
        self.tsc.set('verified_storefront', self.msettings['force_region'])
        self.tsc.set('verified_language', self.msettings['selected_language'])
        self.tsc.set('verified_lyrics_language', self.msettings['lyrics_language_override'])
    
    def login(self, email, password):
        user_token = self.session.auth(email, password)
        self.tsc.set('user_token', user_token)

        self.set_regions()

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
                self.oprint('Original cover URL: ' + result)

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
    
    @staticmethod
    def get_timestamp(input_ts):
        mins = int(input_ts.split(':')[-2]) if ':' in input_ts else 0
        secs = float(input_ts.split(':')[-1]) if ':' in input_ts else float(input_ts.replace('s', ''))
        return mins * 60 + secs
    
    def ts_format(self, input_ts, already_secs=False):
        ts = input_ts if already_secs else self.get_timestamp(input_ts)
        mins = int(ts // 60)
        secs = ts % 60
        return f'{mins:0>2}:{secs:06.3f}' if self.msettings['lyrics_custom_ms_sync'] else f'{mins:0>2}:{secs:05.2f}'
    
    def parse_lyrics_verse(self, lines, multiple_agents, custom_lyrics, add_timestamps=True):
        # using:
        # [start new line timestamp]lyrics<end new line timestamp>
        # also, there's the enhanced format that we don't use which is:
        # [last line end timestamp] <start new line timestamp> lyrics 
        
        synced_lyrics_list = []
        unsynced_lyrics_list = []
        
        for line in lines:
            if isinstance(line, dict):
                if multiple_agents:
                    agent = line['@ttm:agent']
                    if agent[0] != 'v': raise self.exception(f'Weird agent: {agent}')
                    agent_num = int(agent[1:])

                if 'span' in line:
                    words = line['span']
                    if not isinstance(words, list): words = [words]
                    
                    unsynced_line = f'{agent_num}: ' if multiple_agents else ''
                    synced_line = f"[{self.ts_format(line['@begin'])}]" if add_timestamps else ''
                    synced_line += unsynced_line
                    if add_timestamps and custom_lyrics: synced_line += f"<{self.ts_format(line['@begin'])}>"

                    for word in words:
                        if '@ttm:role' in word:
                            if word['@ttm:role'] != 'x-bg': raise self.exception(f'Strange lyric role {word["@ttm:role"]}')
                            if word.get('@prespaced'): unsynced_line += ' '

                            _, bg_verse_synced_lyrics_list = self.parse_lyrics_verse(word['span'], False, False, False)
                            unsynced_line += ''.join([i[2] for i in bg_verse_synced_lyrics_list])

                            synced_bg_line = ''
                            first_ts = 0
                            for bg_word_begin, bg_word_end, bg_word_text in bg_verse_synced_lyrics_list:
                                if not synced_bg_line and add_timestamps:
                                    first_ts = bg_word_begin
                                    synced_bg_line = f"[{self.ts_format(first_ts, already_secs=True)}]"
                                    if multiple_agents: synced_bg_line += f'{agent_num}: '
                                    if add_timestamps and multiple_agents: synced_bg_line += f"<{self.ts_format(first_ts, already_secs=True)}>"
                                synced_bg_line += bg_word_text
                                if custom_lyrics and add_timestamps: synced_bg_line += f"<{self.ts_format(bg_word_end, already_secs=True)}>"

                            synced_lyrics_list.append((first_ts, first_ts, synced_bg_line))
                        else:
                            if word.get('@prespaced'):
                                synced_line += ' '
                                unsynced_line += ' '
                            
                            synced_line += word['#text']
                            unsynced_line += word['#text']

                            if custom_lyrics and add_timestamps: synced_line += f"<{self.ts_format(word['@end'])}>"

                    synced_lyrics_list.append((self.get_timestamp(line['@begin']), self.get_timestamp(line['@end']), synced_line))
                    unsynced_lyrics_list.append(unsynced_line)
                elif '#text' in line:
                    synced_line = f"[{self.ts_format(line['@begin'])}]" if add_timestamps else ''
                    if add_timestamps and custom_lyrics: synced_line += f"<{self.ts_format(line['@begin'])}>"
                    if line.get('@prespaced'): synced_line += ' '
                    synced_line += line['#text']

                    if custom_lyrics and add_timestamps: synced_line += f"<{self.ts_format(line['@end'])}>"
                    synced_lyrics_list.append((self.get_timestamp(line['@begin']), self.get_timestamp(line['@end']), synced_line))

                    unsynced_line = f'{agent_num}: ' if multiple_agents else ''
                    unsynced_line += line['#text']
                    unsynced_lyrics_list.append(unsynced_line)
                else:
                    raise self.exception(f'Unknown lyrics data: {line}')
            elif isinstance(line, str):
                # TODO: more research needed on Apple + Genius sourced unsynced lyrics
                # there are some random unicode things like ’ which we might want to filter out
                unsynced_lyrics_list.append(line)
            else:
                raise self.exception(f'Invalid lyrics type? {line}, type {type(line)}')
        return unsynced_lyrics_list, synced_lyrics_list
    
    def get_lyrics_xml(self, track_id, data = {}):
        # in theory the case where the lyrics and set storefronts differ this is inefficient
        # but it is simpler this way
        track_data = data[track_id] if track_id in data else self.session.get_track(track_id)

        lyrics_data_dict = track_data['relationships'].get(self.lyrics_resource)
        if lyrics_data_dict and lyrics_data_dict.get('data') and lyrics_data_dict['data'][0].get('attributes'):
            lyrics_xml = lyrics_data_dict['data'][0]['attributes']['ttml']
        elif track_data['attributes']['hasLyrics']:
            lyrics_data_dict = self.session.get_lyrics(track_id)
            track_data['relationships'][self.lyrics_resource] = lyrics_data_dict
            lyrics_xml = lyrics_data_dict['data'][0]['attributes']['ttml'] if lyrics_data_dict and lyrics_data_dict.get('data') else None
            if not lyrics_xml:
                if self.lyrics_resource != 'lyrics':
                    # unlikely to work, but try it anyway
                    self.oprint("Warning: lyrics resource not found, trying fallback")
                    lyrics_data_dict = self.session.get_lyrics(track_id, 'lyrics')
                    track_data['relationships'][self.lyrics_resource] = lyrics_data_dict
                    lyrics_xml = lyrics_data_dict['data'][0]['attributes']['ttml'] if lyrics_data_dict and lyrics_data_dict.get('data') else None

                if not lyrics_xml:
                    self.oprint("Warning: lyrics for this track are not available to this Apple Music account.")
        else:
            lyrics_xml = None
        
        return lyrics_xml
    
    def get_track_lyrics(self, track_id, data = {}):
        lyrics_xml = self.get_lyrics_xml(track_id, data)
        if not lyrics_xml: return LyricsInfo(embedded=None, synced=None)

        lyrics_dict = xmltodict.parse(lyrics_xml.replace('> <span', '><span prespaced="true"'))
        # print(json.dumps(lyrics_dict, indent=4, sort_keys=True))
        if lyrics_dict['tt']['@itunes:timing'] not in ['None', 'Line', 'Word']: raise Exception(f"Unknown lyrics format {lyrics_dict['tt']['@itunes:timing']}")
        is_synced = lyrics_dict['tt']['@itunes:timing'] != 'None'
        multiple_agents = isinstance(lyrics_dict['tt'].get('head', {}).get('metadata', {}).get('ttm:agent'), list)
        custom_lyrics = self.msettings['lyrics_type'] == 'custom'

        synced_lyrics_list = []
        unsynced_lyrics_list = []
        
        verses = lyrics_dict['tt']['body']['div']
        if not isinstance(verses, list): verses = [verses]
        
        for verse in verses:
            lines = verse['p']
            if not isinstance(lines, list): lines = [lines]

            verse_unsynced_lyrics_list, verse_synced_lyrics_list = self.parse_lyrics_verse(lines, multiple_agents, custom_lyrics)
            unsynced_lyrics_list += verse_unsynced_lyrics_list
            synced_lyrics_list += verse_synced_lyrics_list
        
            if is_synced: synced_lyrics_list.append((self.get_timestamp(verse['@end']), self.get_timestamp(verse['@end']), f"[{self.ts_format(verse['@end'])}]"))
            unsynced_lyrics_list.append('')

        sorted_synced_lyrics_list = [i[2] for i in sorted(synced_lyrics_list, key=lambda x: x[0])]

        return LyricsInfo(
            embedded = '\n'.join(unsynced_lyrics_list[:-1]),
            synced = '\n'.join(sorted_synced_lyrics_list[:-1])
        )

    def get_track_credits(self, track_id, data = {}):
        lyrics_xml = self.get_lyrics_xml(track_id, data)
        if not lyrics_xml: return []

        try:
            songwriters = lyrics_dict['tt']['head']['metadata']['iTunesMetadata']['songwriters']['songwriter']
        except:
            return []
        
        lyrics_dict = xmltodict.parse(lyrics_xml)
        return [CreditsInfo('Lyricist', songwriters)]

    def search(self, query_type: DownloadTypeEnum, query, track_info: TrackInfo = None, limit = 10):
        results = self.session.get_track_by_isrc(track_info.tags.isrc, track_info.album) if track_info and track_info.tags.isrc else self.session.search(query_type.name + 's' if query_type is not DownloadTypeEnum.track else 'songs', query, limit)
        if not results: return []

        return [SearchResult(
                name = i['attributes']['name'],
                artists = [j['attributes']['name'] for j in i['relationships']['artists']['data']] if query_type in [DownloadTypeEnum.album, DownloadTypeEnum.track] else [i['attributes']['curatorName']] if query_type is DownloadTypeEnum.playlist else [],
                result_id = str(i['id']),
                explicit = i['attributes'].get('contentRating') == 'explicit',
                additional = [format_ for format_ in i['attributes']['audioTraits']] if 'audioTraits' in i['attributes'] else None,
                extra_kwargs = {'data': {i['id']: i}}
            ) for i in results]
