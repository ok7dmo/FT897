# Radio Browser API Fix Notes

## Problem
The Radio Browser API wasn't returning any stations due to incorrect endpoint usage.

## Changes Made

### 1. Fixed Country Code Search
**Before:**
```python
def get_stations_by_country(self, country_code: str, limit: int = 50):
    return self.search_stations(country=country_code, limit=limit)
```

**After:**
```python
def get_stations_by_country(self, country_code: str, limit: int = 50):
    endpoint = f'stations/bycountrycodeexact/{country_code.upper()}'
    result = self._make_request(endpoint)
    if result:
        result.sort(key=lambda x: x.get('votes', 0), reverse=True)
        return result[:limit]
    return []
```

**Why:** The API uses specific endpoints like `/json/stations/bycountrycodeexact/CZ` instead of search parameters.

### 2. Fixed Language Search
**Before:**
```python
def get_stations_by_language(self, language: str, limit: int = 50):
    return self.search_stations(language=language, limit=limit)
```

**After:**
```python
def get_stations_by_language(self, language: str, limit: int = 50):
    endpoint = f'stations/bylanguageexact/{language.lower()}'
    result = self._make_request(endpoint)
    if result:
        result.sort(key=lambda x: x.get('votes', 0), reverse=True)
        return result[:limit]
    return []
```

**Why:** Using dedicated language endpoint for more reliable results.

### 3. Fixed Search Parameters
**Before:**
```python
if country:
    params['country'] = country
if language:
    params['language'] = language
```

**After:**
```python
if country:
    params['countrycode'] = country.upper()
if language:
    params['language'] = language.lower()
```

**Why:** The API expects `countrycode` parameter, not `country`.

### 4. Improved Error Handling
**Before:**
```python
def _make_request(self, endpoint: str, params: Optional[Dict] = None):
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
```

**After:**
```python
def _make_request(self, endpoint: str, params: Optional[Dict] = None):
    last_error = None
    for base_url in self.base_urls:
        try:
            url = f"{base_url}/json/{endpoint}"
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            self.current_url = base_url
            data = response.json()
            if isinstance(data, list):
                return data
            return []
        except requests.RequestException as e:
            last_error = e
            continue
        except (ValueError, KeyError):
            continue
    return []
```

**Why:**
- Always returns a list (never None) for consistency
- Better JSON parsing error handling
- Validates response data type

### 5. Added Fallback for Top Stations
```python
def get_top_stations(self, limit: int = 50):
    # Try topvote endpoint first
    result = self._make_request(f'stations/topvote/{limit}')
    if result:
        return result

    # Fallback: use search with votes ordering
    params = {
        'limit': limit,
        'hidebroken': 'true',
        'order': 'votes',
        'reverse': 'true'
    }
    return self._make_request('stations/search', params)
```

**Why:** Provides fallback if topvote endpoint fails.

## API Endpoints Reference

Based on Radio Browser API documentation:

### Country Search
- Endpoint: `/json/stations/bycountrycodeexact/{countrycode}`
- Example: `/json/stations/bycountrycodeexact/CZ`
- Returns: List of stations in Czech Republic

### Language Search
- Endpoint: `/json/stations/bylanguageexact/{language}`
- Example: `/json/stations/bylanguageexact/czech`
- Returns: List of Czech language stations

### Name Search
- Endpoint: `/json/stations/search?name={name}&limit={limit}`
- Example: `/json/stations/search?name=BBC&limit=10`
- Returns: List of stations matching the name

### Top Voted
- Endpoint: `/json/stations/topvote/{limit}`
- Example: `/json/stations/topvote/50`
- Returns: Top 50 voted stations

### Search with Filters
- Endpoint: `/json/stations/search`
- Parameters:
  - `name` - Station name
  - `countrycode` - Country code (e.g., "CZ", "US")
  - `language` - Language name (e.g., "czech", "english")
  - `tag` - Genre tag
  - `limit` - Maximum results
  - `order` - Sort field (e.g., "votes")
  - `reverse` - Sort direction ("true" for descending)

## Testing

Run the test script on Windows with internet access:

```bash
python test_api_connection.py
```

This will test all API endpoints and show results.

## Troubleshooting

If API still doesn't work:

1. **Check Internet Connection**
   - Ensure you can access https://www.radio-browser.info

2. **Check Firewall**
   - Allow access to `*.api.radio-browser.info`
   - Ports: 80 (HTTP) and 443 (HTTPS)

3. **Test Manually**
   ```bash
   curl "https://de1.api.radio-browser.info/json/stations/bycountrycodeexact/CZ"
   ```

4. **Check API Status**
   - Visit https://www.radio-browser.info
   - Check if the service is operational

## References

- Radio Browser API Docs: https://api.radio-browser.info/
- GitHub: https://github.com/segler-alex/radiobrowser-api-rust
- Example Python client: https://github.com/andreztz/pyradios
