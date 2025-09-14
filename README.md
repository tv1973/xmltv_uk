# TV Guide to XMLTV Converter

A Python tool that converts TV Guide API JSON data to XMLTV format.

## Current Features (Stage 5)

- ✅ Convert JSON files to XMLTV format
- ✅ Fetch data directly from TV Guide API
- ✅ Robust error handling and retry logic
- ✅ Support for multiple TV platforms and regions
- ✅ Intelligent disk caching for reduced API usage
- ✅ Offline operation with cached data
- ✅ Cache management and statistics
- ✅ Multi-hour data collection
- ✅ Multi-day data collection

### Installation

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

### Usage

#### Convert from JSON file:
```bash
python tvguide2xmltv.py input.json output.xml
```

#### Fetch from TV Guide API:
```bash
python tvguide2xmltv.py --api --platform sky --region london --date 2025-01-15 --hour 21 output.xml
```

#### Fetch multiple hours from TV Guide API:
```bash
python tvguide2xmltv.py --api --platform sky --region london --date 2025-01-15 --start-hour 18 --end-hour 23 output.xml
```

#### Fetch multiple days from TV Guide API:
```bash
python tvguide2xmltv.py --api --platform sky --region london --start-date 2025-01-15 --end-date 2025-01-17 --start-hour 18 --end-hour 23 output.xml
```

#### Options:
- `-v, --verbose`: Enable verbose output
- `--api`: Fetch data from TV Guide API instead of reading file
- `--platform`: TV platform (sky, freeview, etc.)
- `--region`: Geographic region (london, manchester, etc.)
- `--date`: Date in YYYY-MM-DD format (for single day)
- `--start-date`: Start date in YYYY-MM-DD format (for multi-day)
- `--end-date`: End date in YYYY-MM-DD format (for multi-day)
- `--hour`: Hour in 24-hour format (0-23)
- `--start-hour`: Starting hour for fetch (0-23)
- `--end-hour`: Ending hour for fetch (0-23)
- `--view`: Display format (default: grid)
- `--details`: Include additional programme details
- `--timeout`: API request timeout in seconds (default: 30)
- `--retries`: Maximum API retry attempts (default: 3)
- `--cache-ttl`: Cache time-to-live in seconds (default: 3600)
- `--no-cache`: Disable cache usage
- `--cache-only`: Only use cached data, do not make API calls
- `--clear-cache`: Clear all cached data and exit
- `--cache-stats`: Show cache statistics and exit
- `-h, --help`: Show help message

### Examples

```bash
# Convert from file
python tvguide2xmltv.py test_sample.json tv_guide.xml -v

# Fetch single hour from Sky (uses cache)
python tvguide2xmltv.py --api --platform sky --region london --date 2025-01-15 --hour 21 output.xml -v

# Fetch evening listings from Sky (6 PM to 11 PM)
python tvguide2xmltv.py --api --platform sky --region london --date 2025-01-15 --start-hour 18 --end-hour 23 output.xml -v

# Fetch multiple days from Sky (3 days, evening hours)
python tvguide2xmltv.py --api --platform sky --region london --start-date 2025-01-15 --end-date 2025-01-17 --start-hour 18 --end-hour 23 output.xml -v

# Fetch with custom cache TTL (2 hours)
python tvguide2xmltv.py --api --platform sky --region london --date 2025-01-15 --hour 21 --cache-ttl 7200 output.xml

# Use only cached data (offline mode)
python tvguide2xmltv.py --api --cache-only --platform sky --region london --date 2025-01-15 --hour 21 output.xml

# Disable cache entirely
python tvguide2xmltv.py --api --no-cache --platform freeview --region manchester --date 2025-01-16 --hour 19 guide.xml

# Cache management
python tvguide2xmltv.py --cache-stats
python tvguide2xmltv.py --clear-cache
```

### Input Format

The tool expects JSON data matching the TV Guide API schema as documented in `TVGuide_co_uk.md`.

### Output Format

Generates valid XMLTV files conforming to the `xmltv.dtd` specification.

## Features

- ✅ JSON parsing and validation
- ✅ Channel element generation
- ✅ Programme element generation with start/stop times
- ✅ Timezone handling (UTC to local time conversion)
- ✅ Field mapping (pa_id, title, type, image_url, new flag)
- ✅ Valid XMLTV output with proper DOCTYPE declaration
- ✅ Error handling and validation
- ✅ Command-line interface
- ✅ Multi-hour data collection with deduplication
- ✅ Multi-day data collection with deduplication

## Field Mapping

| TV Guide JSON | XMLTV Element | Notes |
|---------------|---------------|-------|
| `pa_id` | `channel@id`, `programme@channel` | Unique identifiers |
| `title` | `<display-name>`, `<title>` | Channel and programme names |
| `type` | `<category>` | Programme type (episode, movie) |
| `start_at` | `programme@start` | ISO 8601 to XMLTV time format |
| `duration` | `programme@stop` | Calculated from start + duration |
| `image_url`, `logo_url` | `<icon@src>` | Programme and channel images |
| `new` | `<new>` | New programme flag |

## Next Stages

- Stage 6: Production Features
