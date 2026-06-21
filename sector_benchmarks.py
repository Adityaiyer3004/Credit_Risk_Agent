"""
UK SIC 2007 sector risk profiles.
Failure rates derived from ONS Business Demography 5-year survival data
and Bank of England research on SME default rates by sector.
score_adjustment is applied to the base credit score.
"""

# SIC 2-digit prefix → (5yr_failure_rate_pct, industry_label, score_adjustment)
SECTOR_RISK = {
    "01": (12, "Agriculture",             -4),
    "02": (10, "Forestry",                -3),
    "03": (11, "Fishing",                 -4),
    "05": (14, "Mining",                  -7),
    "06": (13, "Oil & gas extraction",    -6),
    "07": (14, "Metal ore mining",        -7),
    "08": (12, "Quarrying",               -5),
    "09": (13, "Mining support",          -6),
    "10": (11, "Food manufacturing",      -4),
    "11": (13, "Beverage manufacturing",  -6),
    "12": (11, "Tobacco",                 -4),
    "13": (11, "Textiles",                -4),
    "14": (13, "Apparel",                 -6),
    "15": (11, "Leather goods",           -4),
    "16": (10, "Wood products",           -3),
    "17": (10, "Paper products",          -3),
    "18": ( 9, "Printing",                -2),
    "19": ( 8, "Petroleum products",       0),
    "20": (10, "Chemicals",               -3),
    "21": ( 7, "Pharmaceuticals",         +2),
    "22": (10, "Rubber/plastics",         -3),
    "23": (10, "Non-metallic minerals",   -3),
    "24": ( 9, "Basic metals",            -2),
    "25": (11, "Fabricated metals",       -4),
    "26": ( 8, "Electronics",              0),
    "27": ( 9, "Electrical equipment",    -2),
    "28": ( 9, "Machinery",               -2),
    "29": (10, "Motor vehicles",          -3),
    "30": (10, "Other transport equip.",  -3),
    "31": (13, "Furniture",               -6),
    "32": (11, "Other manufacturing",     -4),
    "33": ( 9, "Repair of machinery",     -2),
    "35": ( 6, "Energy supply",           +3),
    "36": ( 7, "Water supply",            +2),
    "37": ( 7, "Sewerage",                +2),
    "38": ( 8, "Waste management",         0),
    "39": ( 8, "Remediation",              0),
    "41": (18, "Building construction",  -12),
    "42": (16, "Civil engineering",       -9),
    "43": (19, "Specialist construction",-13),
    "45": (16, "Motor vehicle trade",     -9),
    "46": (15, "Wholesale trade",         -8),
    "47": (18, "Retail",                 -12),
    "49": (15, "Land transport",          -8),
    "50": (12, "Water transport",         -5),
    "51": (10, "Air transport",           -3),
    "52": (11, "Warehousing",             -4),
    "53": (13, "Postal/courier",          -6),
    "55": (24, "Hotels/accommodation",   -18),
    "56": (25, "Restaurants/food svc",   -19),
    "58": (11, "Publishing",              -4),
    "59": (13, "Film/video production",   -6),
    "60": (12, "Broadcasting",            -5),
    "61": ( 8, "Telecoms",                 0),
    "62": (10, "Software development",    -3),
    "63": (11, "IT/data services",        -4),
    "64": ( 7, "Banking/financial svcs",  +2),
    "65": ( 6, "Insurance",               +3),
    "66": ( 7, "Auxiliary financial",     +2),
    "68": ( 9, "Real estate",             -2),
    "69": ( 8, "Legal services",           0),
    "70": ( 8, "Management consulting",    0),
    "71": ( 9, "Architecture/engineering",-2),
    "72": ( 7, "Scientific R&D",          +2),
    "73": (11, "Advertising/marketing",   -4),
    "74": (11, "Other professional svcs", -4),
    "75": ( 9, "Veterinary",              -2),
    "77": (13, "Rental/leasing",          -6),
    "78": (14, "Employment agencies",     -7),
    "79": (14, "Travel agencies",         -7),
    "80": (10, "Security services",       -3),
    "81": (12, "Building/FM services",    -5),
    "82": (11, "Office admin support",    -4),
    "84": ( 2, "Public admin/defence",    +8),
    "85": ( 4, "Education",               +5),
    "86": ( 5, "Human health activities", +4),
    "87": ( 5, "Residential care",        +4),
    "88": ( 6, "Social work",             +3),
    "90": (20, "Creative arts",          -14),
    "91": (14, "Libraries/museums",       -7),
    "92": (16, "Gambling",                -9),
    "93": (18, "Sports/recreation",      -12),
    "94": (12, "Membership orgs",         -5),
    "95": (14, "Computer repair",         -7),
    "96": (15, "Other personal svcs",     -8),
}

_DEFAULT = (12, "Unknown sector", -4)


def get_sector_risk(sic_codes: list) -> dict:
    """Return the worst-case sector risk profile across all SIC codes supplied."""
    if not sic_codes:
        return {"failure_rate": _DEFAULT[0], "label": _DEFAULT[1], "score_adjustment": _DEFAULT[2]}

    matches = []
    for code in sic_codes:
        prefix = str(code)[:2]
        if prefix in SECTOR_RISK:
            matches.append(SECTOR_RISK[prefix])

    if not matches:
        return {"failure_rate": _DEFAULT[0], "label": _DEFAULT[1], "score_adjustment": _DEFAULT[2]}

    worst = max(matches, key=lambda x: x[0])
    return {
        "failure_rate": worst[0],
        "label": worst[1],
        "score_adjustment": worst[2],
    }
