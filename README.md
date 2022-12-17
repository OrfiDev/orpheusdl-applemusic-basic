<!-- PROJECT INTRO -->

OrpheusDL - Apple Music (Basic Support)
=======================================

An Apple Music module for the OrpheusDL modular archival music program,
for playlists, lyrics and covers only.

[Report Bug](https://github.com/yarrm80s/orpheusdl-applemusic-basic/issues)
·
[Request Feature](https://github.com/yarrm80s/orpheusdl-applemusic-basic/issues)


## Table of content

- [About OrpheusDL - Apple Music](#about-orpheusdl-applemusic)
- [Getting Started](#getting-started)
    - [Prerequisites](#prerequisites)
    - [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
    - [Global](#global)
    - [Apple Music](#applemusic)
- [Contact](#contact)
- [Credits](#credits)


<!-- ABOUT APPLEMUSIC -->
## About OrpheusDL - Apple Music

OrpheusDL - Apple Music is a module written in Python which allows getting playlists, lyrics and covers from **Apple Music** for the modular music archival program.


<!-- GETTING STARTED -->
## Getting Started

Follow these steps to get a local copy of this module up and running:

### Prerequisites

* Already have [OrpheusDL](https://github.com/yarrm80s/orpheusdl) installed

### Installation

1. Clone the repo inside the folder `orpheusdl/modules/`
   ```sh
   git clone https://github.com/yarrm80s/orpheusdl-applemusic-basic.git applemusic
   ```
2. Execute:
   ```sh
   python orpheus.py
   ```
3. Now the `config/settings.json` file should be updated with the Apple Music settings

<!-- USAGE EXAMPLES -->
## Usage

Just call `orpheus.py` with any playlist you want to archive, along with specifying a separate download module:

```sh
python orpheus.py https://music.apple.com/us/playlist/beat-saber-x-monstercat/pl.0ccb67a275dc416c9dadd6fe1f80d518 -sd qobuz
```

<!-- CONFIGURATION -->
## Configuration

You can customize every module from Orpheus individually and also set general/global settings which are active in every
loaded module. You'll find the configuration file here: `config/settings.json`

### Global

TODO

### Apple Music
```json5
"applemusic": {
    "force_region": "us",
    "selected_language": "en",
    "get_original_cover": true,
    "print_original_cover_url": true,
    "lyrics_type": "custom",
    "lyrics_custom_ms_sync": false,
    "lyrics_language_override": "en",
    "lyrics_syllable_sync": true,
    "user_token": "base64 encoded token"
},
```
`force_region`: Select a region to get everything except lyrics data from

`selected_language`: In the region selected, get the language specified

`get_original_cover`: Download the original cover file Apple recieved from the label

`print_original_cover_url`: Prints a link to the original cover file

`lyrics_type`: Can be chosen between standard and custom, standard is highly recommended for compatibility although custom saves all available data

`lyrics_custom_ms_sync`: Lets you save milliseconds instead of seconds to preserve all data, although players usually only accept the default 10ms synced data, leave this disabled unless you know what you're doing

`lyrics_language_override`: Since lyrics require you to request in the region of your account, choose a language from that region to use with lyrics

`lyrics_syllable_sync`: Enable downloading lyrics data with word or even syllable sync, multiple vocalists, overlapping vocals, etc, will need my custom format to work

`user_token`: Most important, you must input your user token from the web player

<!-- Contact -->
## Contact

Yarrm80s - [@yarrm80s](https://github.com/yarrm80s)

Dniel97 - [@Dniel97](https://github.com/Dniel97)

Project Link: [OrpheusDL Apple Music Public GitHub Repository](https://github.com/yarrm80s/orpheusdl-applemusic-basic)


<!-- Credits -->
## Credits

R3AP3 - [@R3AP3](https://github.com/R3AP3) for helping out with in-depth research related to covers
