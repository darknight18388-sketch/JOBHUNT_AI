COUNTRIES = {
    "LK": "Sri Lanka", "IN": "India", "PK": "Pakistan", "BD": "Bangladesh", "NP": "Nepal", "MV": "Maldives",
    "AE": "United Arab Emirates", "QA": "Qatar", "SA": "Saudi Arabia", "KW": "Kuwait", "OM": "Oman", "BH": "Bahrain",
    "SG": "Singapore", "MY": "Malaysia", "JP": "Japan", "AU": "Australia", "NZ": "New Zealand",
    "GB": "United Kingdom", "IE": "Ireland", "DE": "Germany", "FR": "France", "NL": "Netherlands", "IT": "Italy",
    "ES": "Spain", "PL": "Poland", "AT": "Austria", "CH": "Switzerland", "SE": "Sweden", "NO": "Norway",
    "US": "United States", "CA": "Canada", "MX": "Mexico", "BR": "Brazil", "ZA": "South Africa",
}
# Countries the free Adzuna API documents (verify at developer.adzuna.com; it can change).
ADZUNA = {"GB": "gb", "US": "us", "AU": "au", "CA": "ca", "DE": "de", "FR": "fr", "IN": "in", "IT": "it", "NL": "nl",
          "NZ": "nz", "PL": "pl", "SG": "sg", "ZA": "za", "BR": "br", "AT": "at", "CH": "ch", "MX": "mx", "ES": "es"}
ANY = "ANY"  # worldwide-remote jobs


def valid_country(code: str) -> bool:
    return code == "ALL" or code in COUNTRIES
