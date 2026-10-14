"""Reference data for occasion posts: target countries, their tone, national days and the
international / commercial days a company can post about.

Public holidays of every country come from the `holidays` package (offline, maintained); Islamic
dates are computed with the Umm al-Qura calendar (`hijridate`). This file only holds what those
packages do not know: Arabic names, anniversary numbers, tone notes, colours and world days.
"""
from __future__ import annotations

ARAB = ("SA", "AE", "KW", "QA", "BH", "OM", "YE", "IQ", "JO", "LB", "SY", "PS", "EG", "SD", "LY", "TN", "DZ",
        "MA", "MR", "SO", "DJ", "KM")
GULF = ("SA", "AE", "KW", "QA", "BH", "OM")
MUSLIM = ARAB + ("MY", "ID", "BN", "TR", "PK")
MAGHREB = ("MA", "DZ", "TN", "MR")

# code: (Arabic name, English name, flag, Arabic dialect for posts aimed at this country, flag colours)
COUNTRIES: dict[str, tuple[str, str, str, str, tuple[str, ...]]] = {
    "SA": ("السعودية", "Saudi Arabia", "🇸🇦", "gulf", ("#006C35", "#FFFFFF")),
    "AE": ("الإمارات", "United Arab Emirates", "🇦🇪", "gulf", ("#00732F", "#FFFFFF", "#000000", "#FF0000")),
    "KW": ("الكويت", "Kuwait", "🇰🇼", "gulf", ("#007A3D", "#FFFFFF", "#CE1126", "#000000")),
    "QA": ("قطر", "Qatar", "🇶🇦", "gulf", ("#8A1538", "#FFFFFF")),
    "BH": ("البحرين", "Bahrain", "🇧🇭", "gulf", ("#CE1126", "#FFFFFF")),
    "OM": ("عُمان", "Oman", "🇴🇲", "gulf", ("#DB161B", "#FFFFFF", "#008000")),
    "YE": ("اليمن", "Yemen", "🇾🇪", "msa", ("#CE1126", "#FFFFFF", "#000000")),
    "IQ": ("العراق", "Iraq", "🇮🇶", "msa", ("#CE1126", "#FFFFFF", "#000000", "#007A3D")),
    "JO": ("الأردن", "Jordan", "🇯🇴", "msa", ("#000000", "#FFFFFF", "#007A3D", "#CE1126")),
    "LB": ("لبنان", "Lebanon", "🇱🇧", "msa", ("#ED1C24", "#FFFFFF", "#00A651")),
    "SY": ("سوريا", "Syria", "🇸🇾", "msa", ("#007A3D", "#FFFFFF", "#000000", "#CE1126")),
    "PS": ("فلسطين", "Palestine", "🇵🇸", "msa", ("#000000", "#FFFFFF", "#009639", "#ED2E38")),
    "EG": ("مصر", "Egypt", "🇪🇬", "egyptian", ("#CE1126", "#FFFFFF", "#000000")),
    "SD": ("السودان", "Sudan", "🇸🇩", "msa", ("#D21034", "#FFFFFF", "#000000", "#007229")),
    "LY": ("ليبيا", "Libya", "🇱🇾", "msa", ("#E70013", "#000000", "#239E46")),
    "TN": ("تونس", "Tunisia", "🇹🇳", "maghreb", ("#E70013", "#FFFFFF")),
    "DZ": ("الجزائر", "Algeria", "🇩🇿", "maghreb", ("#006233", "#FFFFFF", "#D21034")),
    "MA": ("المغرب", "Morocco", "🇲🇦", "maghreb", ("#C1272D", "#006233")),
    "MR": ("موريتانيا", "Mauritania", "🇲🇷", "msa", ("#00A95C", "#FFD700", "#D01C1F")),
    "SO": ("الصومال", "Somalia", "🇸🇴", "msa", ("#4189DD", "#FFFFFF")),
    "DJ": ("جيبوتي", "Djibouti", "🇩🇯", "msa", ("#6AB2E7", "#12AD2B", "#FFFFFF", "#D7141A")),
    "KM": ("جزر القمر", "Comoros", "🇰🇲", "msa", ("#3A75C4", "#FFC61E", "#FFFFFF", "#CE1126", "#3D8E33")),
    "MY": ("ماليزيا", "Malaysia", "🇲🇾", "msa", ("#010066", "#CC0001", "#FFFFFF", "#FFCC00")),
    "ID": ("إندونيسيا", "Indonesia", "🇮🇩", "msa", ("#FF0000", "#FFFFFF")),
    "BN": ("بروناي", "Brunei", "🇧🇳", "msa", ("#F7E017", "#FFFFFF", "#000000", "#CF1126")),
    "SG": ("سنغافورة", "Singapore", "🇸🇬", "msa", ("#EF3340", "#FFFFFF")),
    "TH": ("تايلاند", "Thailand", "🇹🇭", "msa", ("#A51931", "#FFFFFF", "#2D2A4A")),
    "PH": ("الفلبين", "Philippines", "🇵🇭", "msa", ("#0038A8", "#CE1126", "#FFFFFF", "#FCD116")),
    "TR": ("تركيا", "Türkiye", "🇹🇷", "msa", ("#E30A17", "#FFFFFF")),
    "PK": ("باكستان", "Pakistan", "🇵🇰", "msa", ("#01411C", "#FFFFFF")),
    "IN": ("الهند", "India", "🇮🇳", "msa", ("#FF9933", "#FFFFFF", "#138808")),
    "CN": ("الصين", "China", "🇨🇳", "msa", ("#EE1C25", "#FFFF00")),
    "JP": ("اليابان", "Japan", "🇯🇵", "msa", ("#FFFFFF", "#BC002D")),
    "KR": ("كوريا الجنوبية", "South Korea", "🇰🇷", "msa", ("#FFFFFF", "#CD2E3A", "#0047A0")),
    "GB": ("المملكة المتحدة", "United Kingdom", "🇬🇧", "msa", ("#012169", "#FFFFFF", "#C8102E")),
    "IE": ("أيرلندا", "Ireland", "🇮🇪", "msa", ("#169B62", "#FFFFFF", "#FF883E")),
    "US": ("الولايات المتحدة", "United States", "🇺🇸", "msa", ("#B22234", "#FFFFFF", "#3C3B6E")),
    "CA": ("كندا", "Canada", "🇨🇦", "msa", ("#D80621", "#FFFFFF")),
    "AU": ("أستراليا", "Australia", "🇦🇺", "msa", ("#012169", "#FFFFFF", "#E4002B")),
    "NZ": ("نيوزيلندا", "New Zealand", "🇳🇿", "msa", ("#012169", "#FFFFFF", "#C8102E")),
    "DE": ("ألمانيا", "Germany", "🇩🇪", "msa", ("#000000", "#DD0000", "#FFCE00")),
    "FR": ("فرنسا", "France", "🇫🇷", "msa", ("#0055A4", "#FFFFFF", "#EF4135")),
    "IT": ("إيطاليا", "Italy", "🇮🇹", "msa", ("#009246", "#FFFFFF", "#CE2B37")),
    "ES": ("إسبانيا", "Spain", "🇪🇸", "msa", ("#AA151B", "#F1BF00")),
    "NL": ("هولندا", "Netherlands", "🇳🇱", "msa", ("#AE1C28", "#FFFFFF", "#21468B")),
    "NG": ("نيجيريا", "Nigeria", "🇳🇬", "msa", ("#008751", "#FFFFFF")),
    "ZA": ("جنوب أفريقيا", "South Africa", "🇿🇦", "msa", ("#007A4D", "#FFB612", "#DE3831", "#002395")),
    "KE": ("كينيا", "Kenya", "🇰🇪", "msa", ("#000000", "#BB0000", "#006600", "#FFFFFF")),
}
# fuller holiday lists for countries whose national list leaves out widely celebrated days
SUBDIVISION = {"MY": "14"}          # Kuala Lumpur: adds Deepavali, Thaipusam, Nuzul Al-Quran

# How posts for this audience should sound (goes into the AI brief).
_GULF_TONE = ("Gulf audience: warm, generous and dignified; pride in the country and its leadership is natural "
              "but never exaggerated or political. Family, hospitality and gratitude are the right notes.")
TONE: dict[str, str] = {
    "SA": _GULF_TONE + " Saudi identity and Vision 2030 may be mentioned only when natural. The Saudi flag carries the "
                       "Shahada: never pair it with music, dancing or party imagery.",
    "AE": _GULF_TONE + " Since 2023 the National Day is officially called Eid Al Etihad (عيد الاتحاد); honouring the "
                       "Union and its founders is natural. Modern, optimistic, tolerant tone.",
    "KW": _GULF_TONE + " Kuwait celebrates National Day (25 Feb) and Liberation Day (26 Feb) together.",
    "QA": _GULF_TONE + " Qatar National Day is about unity, loyalty and heritage.",
    "BH": _GULF_TONE, "OM": _GULF_TONE + " Omani tone: calm, modest, respectful, proud of heritage.",
    "EG": "Egyptian audience: warm, close and witty, family-centred; Muslim and Coptic occasions are both part of "
          "Egyptian life — congratulate everyone respectfully.",
    "JO": "Jordanian audience: warm, respectful, proud; Hashemite leadership is mentioned with respect only.",
    "LB": "Lebanese audience: warm, lively, elegant, multi-faith; hopeful, never political.",
    "SY": "Syrian audience: warm, hopeful, dignified; never political.",
    "PS": "Palestinian audience: dignified, warm and steadfast; avoid light party tone, never trivialise.",
    "IQ": "Iraqi audience: warm, proud of history; respectful of all communities; never sectarian or political.",
    "YE": "Yemeni audience: warm, faithful, proud of heritage; hopeful, never political.",
    "SD": "Sudanese audience: warm, hopeful, dignified; never political.", "LY": "Libyan audience: warm, hopeful; never political.",
    "MA": "Moroccan audience: warm, lively; light Darija or simple Arabic, a few French words are natural; the King "
          "is mentioned with respect only.",
    "DZ": "Algerian audience: proud of the revolution and independence, warm and direct; simple Arabic, a few French "
          "words are natural.",
    "TN": "Tunisian audience: warm, modern, simple Arabic; a few French words are natural.",
    "MR": "Mauritanian audience: warm, faithful, simple Arabic.",
    "MY": "Malaysian audience: multicultural and harmonious — respect every race and faith; Malay greetings are natural "
          "(Selamat Hari Raya, Maaf Zahir Batin, Merdeka!, Salam Maal Hijrah); open-house and family culture.",
    "ID": "Indonesian audience: warm and family-centred; Indonesian greetings are natural (Selamat Idul Fitri, Mohon Maaf "
          "Lahir dan Batin, Dirgahayu Republik Indonesia); mudik and togetherness.",
    "BN": "Bruneian audience: courteous, respectful of the Sultan and of Malay Islamic Monarchy values.",
    "SG": "Singaporean audience: multicultural, modern and concise; respect every community.",
    "TH": "Thai audience: polite and warm; the royal family is mentioned only with the highest respect.",
    "TR": "Turkish audience: warm and proud; Turkish greetings are natural (Bayramınız mübarek olsun, Cumhuriyet Bayramı).",
    "PK": "Pakistani audience: warm, patriotic and faithful; Quaid-e-Azam and Iqbal are mentioned with respect.",
}
TONE_DEFAULT = "International audience: warm, inclusive and respectful; make no assumption about faith or politics."

# Anniversary numbers: (country, MM-DD) → the year counted from (number = year - base).
# Saudi National Day is numbered by the official count (2025 = 95th).
NUMBERS: dict[tuple[str, str], int] = {
    ("SA", "09-23"): 1930, ("SA", "02-22"): 1727, ("AE", "12-02"): 1971, ("KW", "02-25"): 1961, ("KW", "02-26"): 1991,
    ("BH", "12-16"): 1971, ("MY", "08-31"): 1957, ("MY", "09-16"): 1963, ("ID", "08-17"): 1945, ("EG", "07-23"): 1952,
    ("EG", "10-06"): 1973, ("JO", "05-25"): 1946, ("MA", "11-18"): 1956, ("MA", "07-30"): 1999, ("DZ", "07-05"): 1962,
    ("DZ", "11-01"): 1954, ("TN", "03-20"): 1956, ("SG", "08-09"): 1965, ("BN", "02-23"): 1984, ("LB", "11-22"): 1943,
    ("SY", "04-17"): 1946, ("IQ", "10-03"): 1932, ("LY", "12-24"): 1951, ("SD", "01-01"): 1956, ("YE", "05-22"): 1990,
    ("MR", "11-28"): 1960, ("PK", "08-14"): 1947, ("TR", "10-29"): 1923, ("US", "07-04"): 1776,
    ("PH", "06-12"): 1898, ("IN", "08-15"): 1947,
}

# The names people use for the main national days (the holiday lists' names are generic)
NAME_FIX: dict[tuple[str, str], tuple[str, str]] = {
    ("SA", "09-23"): ("اليوم الوطني السعودي", "Saudi National Day"),
    ("SA", "02-22"): ("يوم التأسيس السعودي", "Saudi Founding Day"),
    ("AE", "12-02"): ("عيد الاتحاد", "Eid Al Etihad (UAE National Day)"),
    ("KW", "02-25"): ("العيد الوطني الكويتي", "Kuwait National Day"), ("KW", "02-26"): ("عيد التحرير", "Liberation Day"),
    ("QA", "12-18"): ("اليوم الوطني القطري", "Qatar National Day"),
    ("BH", "12-16"): ("العيد الوطني البحريني", "Bahrain National Day"),
    ("OM", "11-20"): ("العيد الوطني العُماني", "Oman National Day"),
    ("MY", "08-31"): ("اليوم الوطني الماليزي (ميرديكا)", "Malaysia National Day (Merdeka)"),
    ("ID", "08-17"): ("عيد استقلال إندونيسيا", "Indonesia Independence Day"),
    ("JO", "05-25"): ("عيد الاستقلال الأردني", "Jordan Independence Day"),
    ("TR", "10-29"): ("عيد الجمهورية التركية", "Republic Day (Türkiye)"),
    ("PK", "08-14"): ("عيد استقلال باكستان", "Pakistan Independence Day"),
    ("SG", "08-09"): ("اليوم الوطني السنغافوري", "Singapore National Day"),
    ("US", "07-04"): ("عيد الاستقلال الأمريكي", "US Independence Day"),
}

# Celebrated national days that are not public holidays (so not in the holiday lists).
NATIONAL_EXTRA: dict[str, list[tuple[str, str, str, str]]] = {
    # country: [(MM-DD, key, Arabic, English)]
    "SA": [("03-11", "flag_day", "يوم العلم السعودي", "Saudi Flag Day")],
    "AE": [("11-03", "flag_day", "يوم العلم الإماراتي", "UAE Flag Day"),
           ("11-30", "commemoration", "يوم الشهيد", "Commemoration Day")],
    "QA": [("12-18", "national_day", "اليوم الوطني القطري", "Qatar National Day")],
    "MA": [("07-30", "throne_day", "عيد العرش", "Throne Day")],
}

# English holiday names → Arabic, for countries whose holiday list has no Arabic.
AR_NAMES = {
    "New Year's Day": "رأس السنة الميلادية", "Chinese New Year": "رأس السنة الصينية",
    "Lunar New Year": "رأس السنة القمرية", "Labor Day": "عيد العمال", "Labour Day": "عيد العمال",
    "International Labor Day": "عيد العمال", "National Labor Day": "عيد العمال", "May Day": "عيد العمال",
    "Labour and Solidarity Day": "عيد العمال", "Vesak Day": "يوم فيساك", "Visakha Bucha": "يوم فيساك",
    "Birthday of HM Yang di-Pertuan Agong": "عيد ميلاد ملك ماليزيا", "National Day": "اليوم الوطني",
    "Malaysia Day": "يوم ماليزيا", "Christmas Day": "عيد الميلاد المجيد", "Diwali": "ديوالي (عيد الأنوار)",
    "Deepavali": "ديوالي (عيد الأنوار)", "Thaipusam": "تايبوسام", "Federal Territory Day": "يوم الأقاليم الاتحادية",
    "Good Friday": "الجمعة العظيمة", "Easter Sunday": "عيد الفصح", "Easter Monday": "اثنين الفصح",
    "Ascension Day": "عيد الصعود", "Pancasila Day": "يوم البانشاسيلا", "Independence Day": "عيد الاستقلال",
    "Day of Silence": "يوم الصمت (نيبي)", "National Sovereignty and Children's Day": "عيد السيادة الوطنية والطفل",
    "Commemoration of Atatürk, Youth and Sports Day": "عيد الشباب والرياضة",
    "Democracy and National Unity Day": "يوم الديمقراطية والوحدة الوطنية", "Victory Day": "عيد النصر",
    "Republic Day": "عيد الجمهورية", "Armed Forces Day": "يوم القوات المسلحة",
    "Sultan Hassanal Bolkiah's Birthday": "عيد ميلاد سلطان بروناي", "Kashmir Solidarity Day": "يوم التضامن مع كشمير",
    "Pakistan Day": "يوم باكستان", "Youm-e-Takbeer": "يوم التكبير", "Iqbal Day": "يوم إقبال",
    "Quaid-e-Azam Day": "يوم القائد الأعظم", "National Children's Day": "يوم الطفل", "Songkran Festival": "مهرجان سونغكران",
    "Coronation Day": "يوم التتويج", "Constitution Day": "يوم الدستور", "National Mother's Day": "عيد الأم",
    "National Father's Day": "عيد الأب", "Thanksgiving Day": "عيد الشكر", "Memorial Day": "يوم الذكرى",
    "Martin Luther King Jr. Day": "يوم مارتن لوثر كينغ", "Veterans Day": "يوم المحاربين القدامى",
    "Columbus Day": "يوم كولومبوس", "Washington's Birthday": "يوم الرؤساء", "Boxing Day": "يوم الصناديق",
    "Chakri Memorial Day": "يوم ذكرى تشاكري", "Makha Bucha": "ماخا بوتشا", "Asarnha Bucha": "أسانها بوتشا",
    "Buddhist Lent Day": "بداية الصوم البوذي", "Juneteenth National Independence Day": "يوم جونتينث",
    "Rizal Day": "يوم ريزال", "Bonifacio Day": "يوم بونيفاسيو", "National Heroes Day": "يوم الأبطال الوطنيين",
    "Holi": "مهرجان هولي", "Gandhi Jayanti": "ذكرى ميلاد غاندي", "Dragon Boat Festival": "مهرجان قوارب التنين",
    "Mid-Autumn Festival": "مهرجان منتصف الخريف", "Hari Raya Haji": "عيد الأضحى", "Hari Raya Puasa": "عيد الفطر",
}

# Corrections to names in the holiday lists
AR_FIX = {"يوم التأسيسي": "يوم التأسيس", "يوم وطني": "اليوم الوطني"}

# Holiday-list entries that are days off, not occasions.
SKIP_WORDS = ("bridge", "bank holiday", "substitute", "additional holiday", "day off", "second day", "third day",
              "fourth day", "eve", "in lieu", "replacement", "election", "polling")

# ------------------------------------------------------------------ Islamic occasions (Umm al-Qura)
# key: (hijri month, day, Arabic, English, motif, tone, always (True) or only when a target country marks it,
#       on by default)
ISLAMIC: dict[str, tuple[int, int, str, str, str, str, bool, bool]] = {
    "ramadan_start": (9, 1, "بداية شهر رمضان المبارك", "Start of Ramadan", "lantern", "spiritual", True, True),
    "nuzul_quran": (9, 17, "ذكرى نزول القرآن", "Nuzul Al-Quran", "lantern", "spiritual", False, True),
    "last_ten": (9, 21, "العشر الأواخر من رمضان", "Last ten nights of Ramadan", "lantern", "spiritual", True, False),
    "eid_fitr": (10, 1, "عيد الفطر المبارك", "Eid al-Fitr", "crescent", "festive", True, True),
    "dhul_hijjah": (12, 1, "العشر الأوائل من ذي الحجة", "First ten days of Dhul Hijjah", "crescent", "spiritual", True, True),
    "arafah": (12, 9, "يوم عرفة", "Day of Arafah", "crescent", "spiritual", True, True),
    "eid_adha": (12, 10, "عيد الأضحى المبارك", "Eid al-Adha", "crescent", "festive", True, True),
    "hijri_new_year": (1, 1, "رأس السنة الهجرية", "Islamic New Year", "crescent", "spiritual", True, True),
    "ashura": (1, 10, "يوم عاشوراء", "Day of Ashura", "crescent", "spiritual", False, False),
    "mawlid": (3, 12, "المولد النبوي الشريف", "Prophet's Birthday (Mawlid)", "mosque", "spiritual", False, True),
    "isra_miraj": (7, 27, "الإسراء والمعراج", "Isra and Mi'raj", "mosque", "spiritual", False, True),
}
# words in holiday names → Islamic key (these holidays are taken from the Hijri set above instead)
ISLAMIC_WORDS = (("eid al-fitr", "eid_fitr"), ("eid al-adha", "eid_adha"), ("arafah", "arafah"),
                 ("islamic new year", "hijri_new_year"), ("hijri new year", "hijri_new_year"),
                 ("prophet", "mawlid"), ("mawlid", "mawlid"), ("maulid", "mawlid"), ("isra", "isra_miraj"),
                 ("ashura", "ashura"), ("nuzul", "nuzul_quran"), ("revelation of the quran", "nuzul_quran"),
                 ("ramadan", "ramadan_start"), ("hari raya puasa", "eid_fitr"), ("hari raya haji", "eid_adha"),
                 ("idul fitri", "eid_fitr"), ("idul adha", "eid_adha"))
OTHER_FAITH_WORDS = ("christmas", "easter", "good friday", "ascension", "vesak", "visakha", "bucha", "diwali",
                     "deepavali", "thaipusam", "holi", "lent", "day of silence", "coptic", "epiphany", "pentecost",
                     "assumption", "all saints", "whit")
MEMORIAL_WORDS = ("memorial", "commemoration", "martyr", "remembrance")

WEEKLY = {
    # key: (weekday 0=Mon, Arabic, English, motif, tone, for Muslim audiences only)
    "friday": (4, "جمعة مباركة", "Jumu'ah Mubarak", "mosque", "spiritual", True),
}

# ------------------------------------------------------------------ world & commercial days
# Rules: ("fixed", MM, DD) | ("nth", month, weekday 0=Mon, n; -1 = last, +offset days) | ("easter", offset)
#        | ("dayofyear", n)
# Each day: key → {ar, en, kind, tone, motif, industries (None = every field), on (default), rules:
#   [(countries or "*", rule, optional (ar, en) name override)], only (limit to these countries)}
ALL_FIELDS = None
_HEALTH = ("health", "nonprofit", "beauty")
_EDU = ("education", "training")
_SHOP = ("ecommerce", "fashion", "beauty", "restaurants", "travel", "automotive", "car_rental", "tech", "general",
         "realestate", "events")

WORLD: dict[str, dict] = {
    "new_year": {"ar": "رأس السنة الميلادية", "en": "New Year's Day", "kind": "international", "tone": "festive",
                 "motif": "sparkle", "industries": ALL_FIELDS, "on": True, "rules": [("*", ("fixed", 1, 1))]},
    "education_day": {"ar": "اليوم الدولي للتعليم", "en": "International Day of Education", "kind": "international",
                      "tone": "appreciation", "motif": "book", "industries": _EDU, "on": True,
                      "rules": [("*", ("fixed", 1, 24))]},
    "cancer_day": {"ar": "اليوم العالمي للسرطان", "en": "World Cancer Day", "kind": "international", "tone": "awareness",
                   "motif": "ribbon", "industries": _HEALTH, "on": True, "rules": [("*", ("fixed", 2, 4))]},
    "valentine": {"ar": "عيد الحب", "en": "Valentine's Day", "kind": "commercial", "tone": "commercial", "motif": "heart",
                  "industries": ("fashion", "beauty", "restaurants", "ecommerce", "travel"), "on": False,
                  "rules": [("*", ("fixed", 2, 14))]},
    "mother_language": {"ar": "اليوم الدولي للغة الأم", "en": "International Mother Language Day",
                        "kind": "international", "tone": "appreciation", "motif": "book", "industries": _EDU,
                        "on": False, "rules": [("*", ("fixed", 2, 21))]},
    "womens_day": {"ar": "يوم المرأة العالمي", "en": "International Women's Day", "kind": "international",
                   "tone": "appreciation", "motif": "heart", "industries": ALL_FIELDS, "on": True,
                   "rules": [("*", ("fixed", 3, 8))]},
    "happiness_day": {"ar": "اليوم الدولي للسعادة", "en": "International Day of Happiness", "kind": "international",
                      "tone": "festive", "motif": "sparkle", "industries": ("travel", "restaurants", "events", "beauty"),
                      "on": False, "rules": [("*", ("fixed", 3, 20))]},
    "mothers_day": {"ar": "عيد الأم", "en": "Mother's Day", "kind": "international", "tone": "appreciation",
                    "motif": "heart", "industries": ALL_FIELDS, "on": True,
                    "rules": [(("MA", "DZ", "TN", "MR", "FR"), ("nth", 5, 6, -1)),
                              (("GB", "IE"), ("easter", -21)), (("ID",), ("fixed", 12, 22)),
                              (("TH",), ("fixed", 8, 12)), (("KR",), ("fixed", 5, 8)), (("ES",), ("nth", 5, 6, 1)),
                              (ARAB, ("fixed", 3, 21)), ("*", ("nth", 5, 6, 2))]},
    "water_day": {"ar": "اليوم العالمي للمياه", "en": "World Water Day", "kind": "international", "tone": "awareness",
                  "motif": "leaf", "industries": ("nonprofit", "government"), "on": False,
                  "rules": [("*", ("fixed", 3, 22))]},
    "health_day": {"ar": "يوم الصحة العالمي", "en": "World Health Day", "kind": "international", "tone": "awareness",
                   "motif": "ribbon", "industries": _HEALTH, "on": True, "rules": [("*", ("fixed", 4, 7))]},
    "earth_day": {"ar": "يوم الأرض", "en": "Earth Day", "kind": "international", "tone": "awareness", "motif": "leaf",
                  "industries": ("nonprofit", "government", "travel", "education"), "on": False,
                  "rules": [("*", ("fixed", 4, 22))]},
    "book_day": {"ar": "اليوم العالمي للكتاب", "en": "World Book Day", "kind": "international", "tone": "appreciation",
                 "motif": "book", "industries": _EDU + ("news",), "on": True, "rules": [("*", ("fixed", 4, 23))]},
    "labour_day": {"ar": "عيد العمال", "en": "Labour Day", "kind": "international", "tone": "appreciation",
                   "motif": "heart", "industries": ALL_FIELDS, "on": True,
                   "rules": [(("US", "CA"), ("nth", 9, 0, 1)), ("*", ("fixed", 5, 1))]},
    "press_day": {"ar": "اليوم العالمي لحرية الصحافة", "en": "World Press Freedom Day", "kind": "international",
                  "tone": "appreciation", "motif": "book", "industries": ("news",), "on": True,
                  "rules": [("*", ("fixed", 5, 3))]},
    "nurses_day": {"ar": "اليوم العالمي للتمريض", "en": "International Nurses Day", "kind": "international",
                   "tone": "appreciation", "motif": "heart", "industries": ("health",), "on": True,
                   "rules": [("*", ("fixed", 5, 12))]},
    "family_day": {"ar": "اليوم الدولي للأسر", "en": "International Day of Families", "kind": "international",
                   "tone": "appreciation", "motif": "heart", "industries": ("travel", "restaurants", "realestate",
                                                                          "education", "nonprofit"),
                   "on": True, "rules": [("*", ("fixed", 5, 15))]},
    "environment_day": {"ar": "يوم البيئة العالمي", "en": "World Environment Day", "kind": "international",
                        "tone": "awareness", "motif": "leaf", "industries": ("nonprofit", "government", "automotive"),
                        "on": False, "rules": [("*", ("fixed", 6, 5))]},
    "blood_donor_day": {"ar": "اليوم العالمي للمتبرعين بالدم", "en": "World Blood Donor Day", "kind": "international",
                        "tone": "awareness", "motif": "heart", "industries": ("health", "nonprofit"), "on": True,
                        "rules": [("*", ("fixed", 6, 14))]},
    "fathers_day": {"ar": "يوم الأب", "en": "Father's Day", "kind": "international", "tone": "appreciation",
                    "motif": "heart", "industries": ALL_FIELDS, "on": True,
                    "rules": [(("TH",), ("fixed", 12, 5)), (("ID",), ("fixed", 11, 12)),
                              (("AU", "NZ"), ("nth", 9, 6, 1)), (("IT", "ES"), ("fixed", 3, 19)),
                              (tuple(c for c in ARAB if c not in MAGHREB), ("fixed", 6, 21)),
                              ("*", ("nth", 6, 6, 3))]},
    "social_media_day": {"ar": "اليوم العالمي لوسائل التواصل الاجتماعي", "en": "World Social Media Day",
                         "kind": "international", "tone": "festive", "motif": "sparkle",
                         "industries": ("tech", "news", "ecommerce"), "on": False, "rules": [("*", ("fixed", 6, 30))]},
    "youth_day": {"ar": "اليوم الدولي للشباب", "en": "International Youth Day", "kind": "international",
                  "tone": "appreciation", "motif": "sparkle", "industries": _EDU + ("events", "nonprofit", "government"),
                  "on": True, "rules": [("*", ("fixed", 8, 12))]},
    "photography_day": {"ar": "اليوم العالمي للتصوير", "en": "World Photography Day", "kind": "international",
                        "tone": "festive", "motif": "camera", "industries": ("travel", "events", "news"), "on": True,
                        "rules": [("*", ("fixed", 8, 19))]},
    "humanitarian_day": {"ar": "اليوم العالمي للعمل الإنساني", "en": "World Humanitarian Day",
                         "kind": "international", "tone": "appreciation", "motif": "heart",
                         "industries": ("nonprofit", "government", "health"), "on": True,
                         "rules": [("*", ("fixed", 8, 19))]},
    "programmers_day": {"ar": "يوم المبرمج", "en": "Programmers' Day", "kind": "international", "tone": "festive",
                        "motif": "sparkle", "industries": ("tech",), "on": True, "rules": [("*", ("dayofyear", 256))]},
    "tourism_day": {"ar": "يوم السياحة العالمي", "en": "World Tourism Day", "kind": "international",
                    "tone": "festive", "motif": "globe", "industries": ("travel", "restaurants", "events", "car_rental",
                                                                       "government"),
                    "on": True, "rules": [("*", ("fixed", 9, 27))]},
    "heart_day": {"ar": "اليوم العالمي للقلب", "en": "World Heart Day", "kind": "international", "tone": "awareness",
                  "motif": "heart", "industries": ("health",), "on": True, "rules": [("*", ("fixed", 9, 29))]},
    "coffee_day": {"ar": "اليوم العالمي للقهوة", "en": "International Coffee Day", "kind": "international",
                   "tone": "festive", "motif": "cup", "industries": ("restaurants", "ecommerce"), "on": True,
                   "rules": [("*", ("fixed", 10, 1))]},
    "pink_october": {"ar": "أكتوبر الوردي للتوعية بسرطان الثدي", "en": "Breast Cancer Awareness Month",
                     "kind": "international", "tone": "awareness", "motif": "ribbon", "industries": _HEALTH,
                     "on": True, "rules": [("*", ("fixed", 10, 1))]},
    "older_persons_day": {"ar": "اليوم الدولي لكبار السن", "en": "International Day of Older Persons",
                          "kind": "international", "tone": "appreciation", "motif": "heart",
                          "industries": ("health", "nonprofit"), "on": False, "rules": [("*", ("fixed", 10, 1))]},
    "habitat_day": {"ar": "اليوم العالمي للموئل", "en": "World Habitat Day", "kind": "international",
                    "tone": "awareness", "motif": "home", "industries": ("realestate",), "on": True,
                    "rules": [("*", ("nth", 10, 0, 1))]},
    "teachers_day": {"ar": "يوم المعلم", "en": "Teachers' Day", "kind": "international", "tone": "appreciation",
                     "motif": "book", "industries": ALL_FIELDS, "on": True,
                     "rules": [(("MY",), ("fixed", 5, 16)), (("ID",), ("fixed", 11, 25)), (("TR",), ("fixed", 11, 24)),
                               (("TH",), ("fixed", 1, 16)), (("SG",), ("nth", 9, 4, 1)), (("IN",), ("fixed", 9, 5)),
                               (("CN",), ("fixed", 9, 10)), (("KR",), ("fixed", 5, 15)), ("*", ("fixed", 10, 5))]},
    "mental_health_day": {"ar": "اليوم العالمي للصحة النفسية", "en": "World Mental Health Day",
                          "kind": "international", "tone": "awareness", "motif": "heart", "industries": _HEALTH,
                          "on": True, "rules": [("*", ("fixed", 10, 10))]},
    "food_day": {"ar": "يوم الأغذية العالمي", "en": "World Food Day", "kind": "international", "tone": "festive",
                 "motif": "cup", "industries": ("restaurants", "nonprofit"), "on": True,
                 "rules": [("*", ("fixed", 10, 16))]},
    "singles_day": {"ar": "عروض 11.11", "en": "11.11 Sale", "kind": "commercial", "tone": "commercial", "motif": "tag",
                    "industries": _SHOP, "on": True, "only": ("MY", "SG", "ID", "TH", "PH", "CN", "BN"),
                    "rules": [("*", ("fixed", 11, 11))]},
    "kindness_day": {"ar": "اليوم العالمي للّطف", "en": "World Kindness Day", "kind": "international",
                     "tone": "appreciation", "motif": "heart", "industries": ("nonprofit", "education"), "on": False,
                     "rules": [("*", ("fixed", 11, 13))]},
    "diabetes_day": {"ar": "اليوم العالمي للسكري", "en": "World Diabetes Day", "kind": "international",
                     "tone": "awareness", "motif": "ribbon", "industries": ("health",), "on": True,
                     "rules": [("*", ("fixed", 11, 14))]},
    "children_day": {"ar": "اليوم العالمي للطفل", "en": "World Children's Day", "kind": "international",
                     "tone": "appreciation", "motif": "heart", "industries": _EDU + ("health", "nonprofit", "fashion"),
                     "on": True, "rules": [("*", ("fixed", 11, 20))]},
    "black_friday": {"ar": "الجمعة السوداء (بلاك فرايدي)", "en": "Black Friday", "kind": "commercial",
                     "tone": "commercial", "motif": "tag", "industries": _SHOP, "on": True,
                     "rules": [(GULF, ("nth", 11, 3, 4, 1), ("الجمعة البيضاء", "White Friday")),
                               ("*", ("nth", 11, 3, 4, 1))]},
    "cyber_monday": {"ar": "الاثنين الإلكتروني (سايبر مونداي)", "en": "Cyber Monday", "kind": "commercial",
                     "tone": "commercial", "motif": "tag", "industries": ("ecommerce", "tech", "fashion"), "on": True,
                     "rules": [("*", ("nth", 11, 3, 4, 4))]},
    "disability_day": {"ar": "اليوم الدولي للأشخاص ذوي الإعاقة", "en": "International Day of Persons with Disabilities",
                       "kind": "international", "tone": "appreciation", "motif": "heart",
                       "industries": ("nonprofit", "health", "government", "education"), "on": True,
                       "rules": [("*", ("fixed", 12, 3))]},
    "volunteer_day": {"ar": "اليوم الدولي للمتطوعين", "en": "International Volunteer Day", "kind": "international",
                      "tone": "appreciation", "motif": "heart", "industries": ("nonprofit", "government"), "on": True,
                      "rules": [("*", ("fixed", 12, 5))]},
    "sale_1212": {"ar": "عروض 12.12", "en": "12.12 Sale", "kind": "commercial", "tone": "commercial", "motif": "tag",
                  "industries": ("ecommerce", "fashion", "beauty"), "on": True,
                  "only": ("MY", "SG", "ID", "TH", "PH", "BN"), "rules": [("*", ("fixed", 12, 12))]},
    "arabic_day": {"ar": "اليوم العالمي للغة العربية", "en": "World Arabic Language Day", "kind": "international",
                   "tone": "appreciation", "motif": "book", "industries": _EDU + ("news", "government"), "on": True,
                   "only": ARAB, "rules": [("*", ("fixed", 12, 18))]},
}
# words in holiday names that already are one of the world days above (the holiday list's date wins)
WORLD_WORDS = (("labo", "labour_day"), ("may day", "labour_day"), ("new year's day", "new_year"),
               ("mother", "mothers_day"), ("father", "fathers_day"), ("teacher", "teachers_day"))

KINDS = ("weekly", "religious", "national", "international", "commercial", "custom")
TONES = ("spiritual", "festive", "pride", "appreciation", "awareness", "commercial", "memorial")

# What each occasion "identity" asks of the writer (goes into the AI brief).
TONE_RULES = {
    "spiritual": "Spiritual occasion: calm, reverent and sincere — blessings and good wishes; no selling, no prices, "
                 "no jokes, no party emojis (🌙 or 🤲 at most).",
    "festive": "Festive occasion: warm congratulations, joy, family and togetherness; the brand is present softly — "
               "no hard selling unless the editor's notes ask for an offer.",
    "pride": "National day: pride, gratitude and belonging to the country and its people; never political or "
             "controversial; never invent official slogans or themes of the year; use the anniversary number if given.",
    "appreciation": "Day of appreciation: honour the people it celebrates sincerely, then link it to the brand's field "
                    "in one natural line.",
    "awareness": "Awareness day: supportive and hopeful; at most one well-known, safe tip from the brand's field; "
                 "no fear, no medical claims, no invented statistics.",
    "commercial": "Shopping day: energetic and inviting; mention an offer ONLY if the editor's notes give one, otherwise "
                  "invite followers to watch for the brand's offers — never invent discounts or prices.",
    "memorial": "Day of remembrance: solemn and respectful; no celebration, no selling, no emojis.",
}

MONTHS_AR = ("يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر",
             "ديسمبر")
HIJRI_MONTHS_AR = ("محرم", "صفر", "ربيع الأول", "ربيع الآخر", "جمادى الأولى", "جمادى الآخرة", "رجب", "شعبان",
                   "رمضان", "شوال", "ذو القعدة", "ذو الحجة")
