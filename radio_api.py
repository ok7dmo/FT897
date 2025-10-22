"""
Radio Browser API Client
Free and open source radio station database
https://www.radio-browser.info/
"""

import requests
import json
from typing import List, Dict, Optional


class RadioBrowserAPI:
    """Client for Radio Browser API"""

    def __init__(self):
        # Use multiple base URLs for redundancy
        self.base_urls = [
            "https://de1.api.radio-browser.info",
            "https://nl1.api.radio-browser.info",
            "https://at1.api.radio-browser.info"
        ]
        self.current_url = self.base_urls[0]
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'RadioStationPlayer/1.0',
            'Content-Type': 'application/json'
        })

    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[List[Dict]]:
        """Make API request with fallback to other servers"""
        for base_url in self.base_urls:
            try:
                url = f"{base_url}/json/{endpoint}"
                response = self.session.get(url, params=params, timeout=10)
                response.raise_for_status()
                self.current_url = base_url
                return response.json()
            except requests.RequestException:
                continue
        return None

    def search_stations(self, name: str = "", country: str = "", language: str = "",
                       tag: str = "", limit: int = 100) -> List[Dict]:
        """
        Search for radio stations

        Args:
            name: Station name to search for
            country: Country code (e.g., 'CZ', 'US', 'GB')
            language: Language code (e.g., 'czech', 'english')
            tag: Genre tag (e.g., 'pop', 'rock', 'news')
            limit: Maximum number of results (default 100)

        Returns:
            List of station dictionaries
        """
        params = {
            'limit': limit,
            'hidebroken': 'true',
            'order': 'votes',
            'reverse': 'true'
        }

        if name:
            params['name'] = name
        if country:
            params['country'] = country
        if language:
            params['language'] = language
        if tag:
            params['tag'] = tag

        result = self._make_request('stations/search', params)
        return result if result else []

    def get_stations_by_country(self, country_code: str, limit: int = 50) -> List[Dict]:
        """Get stations by country code (e.g., 'CZ' for Czech Republic)"""
        return self.search_stations(country=country_code, limit=limit)

    def get_stations_by_language(self, language: str, limit: int = 50) -> List[Dict]:
        """Get stations by language (e.g., 'czech', 'english')"""
        return self.search_stations(language=language, limit=limit)

    def get_top_stations(self, limit: int = 50) -> List[Dict]:
        """Get top voted stations"""
        result = self._make_request('stations/topvote/' + str(limit))
        return result if result else []

    def get_countries(self) -> List[Dict]:
        """Get list of all countries with station counts"""
        result = self._make_request('countries')
        return result if result else []

    def get_languages(self) -> List[Dict]:
        """Get list of all languages with station counts"""
        result = self._make_request('languages')
        return result if result else []

    def get_tags(self) -> List[Dict]:
        """Get list of all tags (genres) with station counts"""
        result = self._make_request('tags')
        return result if result else []

    def click_station(self, station_uuid: str):
        """Register a click/listen event for a station"""
        try:
            url = f"{self.current_url}/json/url/{station_uuid}"
            self.session.get(url, timeout=5)
        except requests.RequestException:
            pass  # Not critical if this fails

    @staticmethod
    def format_station_for_display(station: Dict) -> str:
        """Format station data for display"""
        name = station.get('name', 'Unknown')
        country = station.get('country', '')
        tags = station.get('tags', '')

        parts = [name]
        if country:
            parts.append(f"({country})")
        if tags:
            # Limit tags to avoid too long names
            tag_list = tags.split(',')[:2]
            parts.append(f"[{', '.join(tag_list)}]")

        return ' '.join(parts)

    @staticmethod
    def get_station_url(station: Dict) -> str:
        """Get the streaming URL from station data"""
        return station.get('url_resolved') or station.get('url', '')

    @staticmethod
    def get_station_info(station: Dict) -> str:
        """Get detailed station information"""
        info_parts = []

        name = station.get('name', 'Unknown')
        info_parts.append(f"Name: {name}")

        country = station.get('country', 'Unknown')
        info_parts.append(f"Country: {country}")

        language = station.get('language', 'Unknown')
        info_parts.append(f"Language: {language}")

        tags = station.get('tags', '')
        if tags:
            info_parts.append(f"Tags: {tags}")

        bitrate = station.get('bitrate', 0)
        if bitrate:
            info_parts.append(f"Bitrate: {bitrate} kbps")

        codec = station.get('codec', '')
        if codec:
            info_parts.append(f"Codec: {codec}")

        homepage = station.get('homepage', '')
        if homepage:
            info_parts.append(f"Homepage: {homepage}")

        return '\n'.join(info_parts)
