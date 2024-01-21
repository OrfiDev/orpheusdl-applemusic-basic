# This is likely not necessary at all, but I (OrfiDev) decided to reverse engineer and
# reimplement the fingerprinting algorithm used by Apple's web login as used by Apple Music anyways.
#
# I'm not sure if this is reversible (as in even checkable if it's correct)
# maybe the part which I assumed to be a checksum is actually a way to derive some variable required to decode?

import pytz
import random
import datetime
import urllib.parse

timezone = pytz.timezone('America/Los_Angeles')

class Fingerprint:
    def encode(cls, e):
        y = ["%20", ";;;", "%3B", "%2C", "und", "fin", "ed;", "%28", "%29", "%3A", "/53", "ike", "Web", "0;", ".0", "e;", "on", "il", "ck", "01", "in", "Mo", "fa", "00", "32", "la", ".1", "ri", "it", "%u", "le"]
        A = ".0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdefghijklmnopqrstuvwxyz"
        w = {
            1: [4, 15],
            110: [8, 239],
            74: [8, 238],
            57: [7, 118],
            56: [7, 117],
            71: [8, 233],
            25: [8, 232],
            101: [5, 28],
            104: [7, 111],
            4: [7, 110],
            105: [6, 54],
            5: [7, 107],
            109: [7, 106],
            103: [9, 423],
            82: [9, 422],
            26: [8, 210],
            6: [7, 104],
            46: [6, 51],
            97: [6, 50],
            111: [6, 49],
            7: [7, 97],
            45: [7, 96],
            59: [5, 23],
            15: [7, 91],
            11: [8, 181],
            72: [8, 180],
            27: [8, 179],
            28: [8, 178],
            16: [7, 88],
            88: [10, 703],
            113: [11, 1405],
            89: [12, 2809],
            107: [13, 5617],
            90: [14, 11233],
            42: [15, 22465],
            64: [16, 44929],
            0: [16, 44928],
            81: [9, 350],
            29: [8, 174],
            118: [8, 173],
            30: [8, 172],
            98: [8, 171],
            12: [8, 170],
            99: [7, 84],
            117: [6, 41],
            112: [6, 40],
            102: [9, 319],
            68: [9, 318],
            31: [8, 158],
            100: [7, 78],
            84: [6, 38],
            55: [6, 37],
            17: [7, 73],
            8: [7, 72],
            9: [7, 71],
            77: [7, 70],
            18: [7, 69],
            65: [7, 68],
            48: [6, 33],
            116: [6, 32],
            10: [7, 63],
            121: [8, 125],
            78: [8, 124],
            80: [7, 61],
            69: [7, 60],
            119: [7, 59],
            13: [8, 117],
            79: [8, 116],
            19: [7, 57],
            67: [7, 56],
            114: [6, 27],
            83: [6, 26],
            115: [6, 25],
            14: [6, 24],
            122: [8, 95],
            95: [8, 94],
            76: [7, 46],
            24: [7, 45],
            37: [7, 44],
            50: [5, 10],
            51: [5, 9],
            108: [6, 17],
            22: [7, 33],
            120: [8, 65],
            66: [8, 64],
            21: [7, 31],
            106: [7, 30],
            47: [6, 14],
            53: [5, 6],
            49: [5, 5],
            86: [8, 39],
            85: [8, 38],
            23: [7, 18],
            75: [7, 17],
            20: [7, 16],
            2: [5, 3],
            73: [8, 23],
            43: [9, 45],
            87: [9, 44],
            70: [7, 10],
            3: [6, 4],
            52: [5, 1],
            54: [5, 0]
        }
        
        # the actual encoding function
        def main_encode(e):
            def t(r, o, input_tuple, n):
                shift, value = input_tuple
                r = (r << shift) | value
                o += shift
                while o >= 6:
                    e = (r >> (o - 6)) & 63
                    n += A[e]
                    r ^= e << (o - 6)
                    o -= 6
                return n, r, o

            n, r, o = "", 0, 0
            n, r, o = t(r, o, (6, (7 & len(e)) << 3 | 0), n)
            n, r, o = t(r, o, (6, 56 & len(e) | 1), n)

            for char in e:
                char_code = ord(char)
                if char_code not in w:
                    return ""
                n, r, o = t(r, o, w[char_code], n)

            n, r, o = t(r, o, w[0], n)
            if o > 0:
                n, r, o = t(r, o, (6 - o, 0), n)

            return n

        # replacing some stuff in the string?
        n = e
        for r, rep in enumerate(y):
            n = n.replace(rep, chr(r + 1))
        
        # checksum calculation I think
        n_val = 65535
        for char in e:
            n_val = ((n_val >> 8) | (n_val << 8)) & 65535
            n_val ^= 255 & ord(char)
            n_val ^= (255 & n_val) >> 4
            n_val ^= (n_val << 12) & 65535
            n_val ^= ((255 & n_val) << 5) & 65535
            n_val &= 65535
        n_val &= 65535
        checksum = A[n_val >> 12] + A[(n_val >> 6) & 63] + A[n_val & 63]

        # adding checksum to the encoded string
        return main_encode(n) + checksum

    def generate(cls):
        def get_timezone_offset(date):
            local_time = timezone.localize(date)
            return int(-local_time.utcoffset().total_seconds() / 60)

        t1 = get_timezone_offset(datetime.datetime(2005, 1, 15))
        t2 = get_timezone_offset(datetime.datetime(2005, 7, 15))

        def base_is_dst():
            return abs(t1 - t2) != 0

        def base_is_dst_str():
            return str(base_is_dst()).lower()

        def is_dst(date):
            return base_is_dst and get_timezone_offset(date) == min(t1, t2)

        def is_dst_str(date):
            return str(is_dst(date)).lower()

        def calculate_offset(date):
            return int(-(get_timezone_offset(date) + abs(t2 - t1) * is_dst(date)) / 60)

        # technically not the same as the browser, but close enough
        def get_locale_string(date):
            return urllib.parse.quote(date.strftime("%m/%d/%Y, %I:%M:%S %p"))

        def get_timestamp(date):
            return int(date.timestamp() * 1000)

        current_time = datetime.datetime.now()

        return f'TF1;020;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;{base_is_dst_str()};{is_dst_str(current_time)};{get_timestamp(current_time)};{calculate_offset(current_time)};{get_locale_string(datetime.datetime(2005,6,7,21,33,44,888))};;;;;;;;;{random.randint(1000, 9999)};{t1};{t2};{get_locale_string(current_time)};;;;;;;;;;;;;;;;;;;;;;;;25;;;;;;;;;;;;;;;5.6.1-0;;'
    
    def create_fingerprint(cls):
        return cls.encode(cls.generate())

# all the garbage that is tracked for fingerprinting if you're curious
'''
                var t = new Date
                  , r = new Date
                  , o = [u("TF1"), u("020"), function() {
                    return ScriptEngineMajorVersion()
                }
                , function() {
                    return ScriptEngineMinorVersion()
                }
                , function() {
                    return ScriptEngineBuildVersion()
                }
                , function() {
                    return c("{7790769C-0471-11D2-AF11-00C04FA35D02}")
                }
                , function() {
                    return c("{89820200-ECBD-11CF-8B85-00AA005B4340}")
                }
                , function() {
                    return c("{283807B5-2C60-11D0-A31D-00AA00B92C03}")
                }
                , function() {
                    return c("{4F216970-C90C-11D1-B5C7-0000F8051515}")
                }
                , function() {
                    return c("{44BBA848-CC51-11CF-AAFA-00AA00B6015C}")
                }
                , function() {
                    return c("{9381D8F2-0288-11D0-9501-00AA00B911A5}")
                }
                , function() {
                    return c("{4F216970-C90C-11D1-B5C7-0000F8051515}")
                }
                , function() {
                    return c("{5A8D6EE0-3E18-11D0-821E-444553540000}")
                }
                , function() {
                    return c("{89820200-ECBD-11CF-8B85-00AA005B4383}")
                }
                , function() {
                    return c("{08B0E5C0-4FCB-11CF-AAA5-00401C608555}")
                }
                , function() {
                    return c("{45EA75A0-A269-11D1-B5BF-0000F8051515}")
                }
                , function() {
                    return c("{DE5AED00-A4BF-11D1-9948-00C04F98BBC9}")
                }
                , function() {
                    return c("{22D6F312-B0F6-11D0-94AB-0080C74C7E95}")
                }
                , function() {
                    return c("{44BBA842-CC51-11CF-AAFA-00AA00B6015B}")
                }
                , function() {
                    return c("{3AF36230-A269-11D1-B5BF-0000F8051515}")
                }
                , function() {
                    return c("{44BBA840-CC51-11CF-AAFA-00AA00B6015C}")
                }
                , function() {
                    return c("{CC2A9BA0-3BDD-11D0-821E-444553540000}")
                }
                , function() {
                    return c("{08B0E5C0-4FCB-11CF-AAA5-00401C608500}")
                }
                , function() {
                    return ""
                }
                , function() {
                    return ""
                }
                , function() {
                    return ""
                }
                , function() {
                    return s(["navigator.productSub", "navigator.appMinorVersion"])
                }
                , function() {
                    return ""
                }
                , function() {
                    return ""
                }
                , function() {
                    return s(["navigator.oscpu", "navigator.cpuClass"])
                }
                , function() {
                    return ""
                }
                , function() {
                    return ""
                }
                , function() {
                    return ""
                }
                , function() {
                    return ""
                }
                , function() {
                    return s(["navigator.language", "navigator.userLanguage"])
                }
                , function() {
                    return ""
                }
                , function() {
                    return ""
                }
                , function() {
                    return ""
                }
                , function() {
                    return ""
                }
                , function() {
                    return ""
                }
                , function() {
                    return ""
                }
                , function() {
                    return 0 !== Math.abs(h - g)
                }
                , function() {
                    return a(t)
                }
                , function() {
                    return "@UTC@"
                }
                , function() {
                    var e = 0;
                    return e = 0,
                    a(t) && (e = Math.abs(h - g)),
                    -(t.getTimezoneOffset() + e) / 60
                }
                , function() {
                    return new Date(2005,5,7,21,33,44,888).toLocaleString()
                }
                , function() {
                    return ""
                }
                , function() {
                    return ""
                }
                , function() {
                    return v.Acrobat
                }
                , function() {
                    return v.Flash
                }
                , function() {
                    return v.QuickTime
                }
                , function() {
                    return v["Java Plug-in"]
                }
                , function() {
                    return v.Director
                }
                , function() {
                    return v.Office
                }
                , function() {
                    return "@CT@"
                }
                , function() {
                    return h
                }
                , function() {
                    return g
                }
                , function() {
                    return t.toLocaleString()
                }
                , function() {
                    return ""
                }
                , function() {
                    return ""
                }
                , function() {
                    return ""
                }
                , function() {
                    return ""
                }
                , function() {
                    return ""
                }
                , function() {
                    return n("Acrobat")
                }
                , function() {
                    return n("Adobe SVG")
                }
                , function() {
                    return n("Authorware")
                }
                , function() {
                    return n("Citrix ICA")
                }
                , function() {
                    return n("Director")
                }
                , function() {
                    return n("Flash")
                }
                , function() {
                    return n("MapGuide")
                }
                , function() {
                    return n("MetaStream")
                }
                , function() {
                    return n("PDFViewer")
                }
                , function() {
                    return n("QuickTime")
                }
                , function() {
                    return n("RealOne")
                }
                , function() {
                    return n("RealPlayer Enterprise")
                }
                , function() {
                    return n("RealPlayer Plugin")
                }
                , function() {
                    return n("Seagate Software Report")
                }
                , function() {
                    return n("Silverlight")
                }
                , function() {
                    return n("Windows Media")
                }
                , function() {
                    return n("iPIX")
                }
                , function() {
                    return n("nppdf.so")
                }
                , function() {
                    var e = document.createElement("span");
                    e.innerHTML = "&nbsp;",
                    e.style.position = "absolute",
                    e.style.left = "-9999px",
                    document.body.appendChild(e);
                    var t = e.offsetHeight;
                    return document.body.removeChild(e),
                    t
                }
                , m(), m(), m(), m(), m(), m(), m(), m(), m(), m(), m(), m(), m(), m(), function() {
                    return "5.6.1-0"
                }
                , m()];
'''