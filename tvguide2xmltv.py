#!/usr/bin/env python3
"""
TV Guide to XMLTV Converter
Stage 5: Multi-Day Data Collection
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom

try:
    import requests
except ImportError:
    requests = None


class CacheManager:
    """Manages disk cache for API responses"""
    
    def __init__(self, cache_dir="cache"):
        self.cache_dir = cache_dir
        self.metadata_file = os.path.join(cache_dir, "metadata.json")
        self._ensure_cache_dir()
    
    def _ensure_cache_dir(self):
        """Create cache directory if it doesn't exist"""
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
    
    def _get_cache_filename(self, platform, region, date, hour):
        """Generate cache filename for given parameters"""
        return os.path.join(self.cache_dir, f"{platform}_{region}_{date}_{hour}.json")
    
    def _load_metadata(self):
        """Load cache metadata"""
        if os.path.exists(self.metadata_file):
            try:
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {}
    
    def _save_metadata(self, metadata):
        """Save cache metadata"""
        try:
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
        except IOError:
            pass  # Fail silently if we can't write metadata
    
    def _is_cache_valid(self, cache_file, cache_ttl):
        """Check if cache file is valid based on TTL"""
        if not os.path.exists(cache_file):
            return False
        
        # Get file modification time
        mtime = datetime.fromtimestamp(os.path.getmtime(cache_file))
        age = datetime.now() - mtime
        
        return age.total_seconds() < cache_ttl
    
    def get_cached_data(self, platform, region, date, hour, cache_ttl=3600):
        """
        Get cached data if available and valid
        
        Args:
            platform: TV platform
            region: Geographic region
            date: Date string
            hour: Hour number
            cache_ttl: Cache time-to-live in seconds
        
        Returns:
            dict or None: Cached data if valid, None otherwise
        """
        cache_file = self._get_cache_filename(platform, region, date, hour)
        
        if self._is_cache_valid(cache_file, cache_ttl):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        
        return None
    
    def save_cached_data(self, platform, region, date, hour, data):
        """
        Save data to cache
        
        Args:
            platform: TV platform
            region: Geographic region
            date: Date string
            hour: Hour number
            data: Data to cache
        """
        cache_file = self._get_cache_filename(platform, region, date, hour)
        
        try:
            # Save the data
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            # Update metadata
            metadata = self._load_metadata()
            cache_key = f"{platform}_{region}_{date}_{hour}"
            metadata[cache_key] = {
                'timestamp': datetime.now().isoformat(),
                'file': cache_file,
                'platform': platform,
                'region': region,
                'date': date,
                'hour': hour
            }
            self._save_metadata(metadata)
            
        except IOError:
            pass  # Fail silently if we can't write cache
    
    def clear_cache(self):
        """Clear all cached data"""
        if os.path.exists(self.cache_dir):
            for filename in os.listdir(self.cache_dir):
                file_path = os.path.join(self.cache_dir, filename)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                except OSError:
                    pass
    
    def get_cache_stats(self):
        """Get cache statistics"""
        if not os.path.exists(self.cache_dir):
            return {'files': 0, 'total_size': 0}
        
        files = 0
        total_size = 0
        
        for filename in os.listdir(self.cache_dir):
            file_path = os.path.join(self.cache_dir, filename)
            if os.path.isfile(file_path) and filename.endswith('.json'):
                files += 1
                total_size += os.path.getsize(file_path)
        
        return {'files': files, 'total_size': total_size}


class TVGuideAPIClient:
    """Client for fetching data from TV Guide API"""
    
    def __init__(self, base_url="https://api-2.tvguide.co.uk/listings", cache_dir="cache"):
        if requests is None:
            raise ImportError("requests library is required for API functionality. Install with: pip install requests")
        
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        self.cache = CacheManager(cache_dir)
    
    def fetch_listings(self, platform, region, date, hour, view="grid", details=False, timeout=30, max_retries=3, 
                      use_cache=True, cache_ttl=3600, cache_only=False):
        """
        Fetch TV listings from the API with caching support
        
        Args:
            platform: TV platform (e.g., "sky", "freeview")
            region: Geographic region (e.g., "london", "manchester")
            date: Date in YYYY-MM-DD format
            hour: Hour in 24-hour format (0-23)
            view: Display format (default: "grid")
            details: Include additional details (default: False)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            use_cache: Whether to use cache (default: True)
            cache_ttl: Cache time-to-live in seconds (default: 3600)
            cache_only: Only use cache, don't make API calls (default: False)
        
        Returns:
            dict: JSON response from API or cache
        
        Raises:
            requests.RequestException: If API request fails
            ValueError: If response format is invalid or cache_only with no cache
        """
        # Try cache first if enabled
        if use_cache:
            cached_data = self.cache.get_cached_data(platform, region, date, hour, cache_ttl)
            if cached_data is not None:
                return cached_data
        
        # If cache_only mode and no cache hit, raise error
        if cache_only:
            raise ValueError(f"No cached data available for {platform}_{region}_{date}_{hour} and cache_only mode is enabled")
        params = {
            'platform': platform,
            'region': region,
            'view': view,
            'date': date,
            'hour': str(hour),
            'details': str(details).lower()
        }
        
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                response = self.session.get(
                    self.base_url,
                    params=params,
                    timeout=timeout
                )
                response.raise_for_status()
                
                # Validate JSON response
                try:
                    data = response.json()
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON response from API: {e}")
                
                if not isinstance(data, list):
                    raise ValueError("Expected JSON array from API response")
                
                # Cache the successful response if caching is enabled
                if use_cache:
                    self.cache.save_cached_data(platform, region, date, hour, data)
                
                return data
                
            except requests.RequestException as e:
                last_exception = e
                if attempt < max_retries:
                    # Exponential backoff: 1s, 2s, 4s
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
                    continue
                else:
                    break
        
        # If we get here, all retries failed
        raise requests.RequestException(f"API request failed after {max_retries + 1} attempts: {last_exception}")


class TVGuideConverter:
    """Converts TV Guide JSON format to XMLTV format"""
    
    def __init__(self):
        self.channels = {}
        self.programmes = []
    
    def parse_json(self, json_data):
        """Parse TV Guide JSON data and extract channels and programmes"""
        try:
            data = json.loads(json_data) if isinstance(json_data, str) else json_data
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON data: {e}")
        
        if not isinstance(data, list):
            raise ValueError("Expected JSON array of channel objects")
        
        for channel_data in data:
            self._parse_channel(channel_data)
    
    def _parse_channel(self, channel_data):
        """Parse a single channel object"""
        required_fields = ['pa_id', 'title', 'schedules']
        for field in required_fields:
            if field not in channel_data:
                raise ValueError(f"Missing required field '{field}' in channel data")
        
        # Use slug as channel ID, fallback to pa_id if slug not available
        channel_id = channel_data.get('slug', channel_data['pa_id'])
        
        # Store channel information
        self.channels[channel_id] = {
            'id': channel_id,
            'title': channel_data['title'],
            'slug': channel_data.get('slug', ''),
            'logo_url': channel_data.get('logo_url', ''),
            'epg': channel_data.get('epg', ''),
            'pa_id': channel_data['pa_id']
        }
        
        # Parse programmes for this channel
        for schedule in channel_data.get('schedules', []):
            self._parse_programme(schedule, channel_id)
    
    def _parse_programme(self, schedule, channel_id):
        """Parse a single programme/schedule object"""
        required_fields = ['pa_id', 'title', 'start_at', 'duration']
        for field in required_fields:
            if field not in schedule:
                raise ValueError(f"Missing required field '{field}' in schedule data")
        
        # Parse start time
        try:
            start_time = datetime.fromisoformat(schedule['start_at'].replace('Z', '+00:00'))
        except ValueError as e:
            raise ValueError(f"Invalid start_at format: {e}")
        
        # Calculate stop time
        duration_minutes = schedule['duration']
        stop_time = start_time.replace(microsecond=0)
        stop_time = stop_time.replace(second=0)
        # Add duration
        stop_time = datetime.fromtimestamp(
            stop_time.timestamp() + (duration_minutes * 60),
            tz=start_time.tzinfo
        )
        
        programme = {
            'pa_id': schedule['pa_id'],
            'title': schedule['title'],
            'type': schedule.get('type', ''),
            'start': start_time,
            'stop': stop_time,
            'channel': channel_id,
            'image_url': schedule.get('image_url', ''),
            'new': schedule.get('new', False)
        }
        
        self.programmes.append(programme)
    
    def generate_xmltv(self):
        """Generate XMLTV XML from parsed data"""
        # Create root element
        tv = Element('tv')
        tv.set('date', datetime.now().strftime('%Y%m%d%H%M%S +0000'))
        tv.set('source-info-name', 'TV Guide API')
        tv.set('generator-info-name', 'tvguide2xmltv/1.0')
        
        # Add channel elements
        for channel_id, channel_data in self.channels.items():
            channel_elem = SubElement(tv, 'channel')
            channel_elem.set('id', channel_id)
            
            # Display name
            display_name = SubElement(channel_elem, 'display-name')
            display_name.text = channel_data['title']
            
            # Icon (logo)
            if channel_data['logo_url']:
                icon = SubElement(channel_elem, 'icon')
                icon.set('src', channel_data['logo_url'])
        
        # Add programme elements
        for programme in self.programmes:
            prog_elem = SubElement(tv, 'programme')
            prog_elem.set('start', self._format_xmltv_time(programme['start']))
            prog_elem.set('stop', self._format_xmltv_time(programme['stop']))
            prog_elem.set('channel', programme['channel'])
            
            # Title
            title = SubElement(prog_elem, 'title')
            title.text = programme['title']
            
            # Category (from type)
            if programme['type']:
                category = SubElement(prog_elem, 'category')
                category.text = programme['type']
            
            # Icon (image)
            if programme['image_url']:
                icon = SubElement(prog_elem, 'icon')
                icon.set('src', programme['image_url'])
            
            # New flag
            if programme['new']:
                SubElement(prog_elem, 'new')
        
        return tv
    
    def _format_xmltv_time(self, dt):
        """Format datetime for XMLTV (YYYYMMDDhhmmss +ZZZZ)"""
        return dt.strftime('%Y%m%d%H%M%S %z')
    
    def to_xml_string(self, tv_element):
        """Convert XML element to formatted string with DOCTYPE"""
        # Convert to string
        rough_string = tostring(tv_element, encoding='unicode')
        
        # Parse and format with minidom
        reparsed = minidom.parseString(rough_string)
        
        # Get formatted XML without the default XML declaration
        formatted = reparsed.documentElement.toprettyxml(indent='  ')
        
        # Add proper XML declaration and DOCTYPE
        xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'
        doctype = '<!DOCTYPE tv SYSTEM "xmltv.dtd">\n'
        
        return xml_declaration + doctype + formatted


def fetch_multiple_hours(api_client, platform, region, date, start_hour, end_hour, 
                        view="grid", details=False, timeout=30, max_retries=3,
                        use_cache=True, cache_ttl=3600, cache_only=False, verbose=False):
    """
    Fetch data for multiple hours and combine into a single dataset
    
    Args:
        api_client: TVGuideAPIClient instance
        platform: TV platform
        region: Geographic region
        date: Date in YYYY-MM-DD format
        start_hour: Starting hour (0-23)
        end_hour: Ending hour (0-23)
        view: Display format
        details: Include additional details
        timeout: Request timeout
        max_retries: Maximum retry attempts
        use_cache: Whether to use cache
        cache_ttl: Cache time-to-live
        cache_only: Only use cached data
        verbose: Enable verbose output
    
    Returns:
        list: Combined JSON data from all hours
    """
    if start_hour > end_hour:
        raise ValueError("start_hour must be less than or equal to end_hour")
    
    if verbose:
        print(f"Fetching data for hours {start_hour} to {end_hour} on {date}")
    
    # Dictionary to store channel data by pa_id to avoid duplicates
    channels_dict = {}
    
    # Fetch data for each hour
    for hour in range(start_hour, end_hour + 1):
        if verbose:
            print(f"  Fetching hour {hour}...")
        
        try:
            hour_data = api_client.fetch_listings(
                platform=platform,
                region=region,
                date=date,
                hour=hour,
                view=view,
                details=details,
                timeout=timeout,
                max_retries=max_retries,
                use_cache=use_cache,
                cache_ttl=cache_ttl,
                cache_only=cache_only
            )
            
            # Merge channel data
            for channel in hour_data:
                pa_id = channel['pa_id']
                if pa_id not in channels_dict:
                    channels_dict[pa_id] = channel
                else:
                    # Merge schedules, avoiding duplicates
                    existing_schedules = {(s['pa_id'], s['start_at']) for s in channels_dict[pa_id]['schedules']}
                    for schedule in channel['schedules']:
                        schedule_key = (schedule['pa_id'], schedule['start_at'])
                        if schedule_key not in existing_schedules:
                            channels_dict[pa_id]['schedules'].append(schedule)
                            
        except ValueError as e:
            if cache_only and "No cached data available" in str(e):
                if verbose:
                    print(f"    No cached data for hour {hour}, skipping...")
                continue
            else:
                raise
    
    # Convert back to list format
    return list(channels_dict.values())


def fetch_multiple_days(api_client, platform, region, start_date, end_date, start_hour, end_hour,
                       view="grid", details=False, timeout=30, max_retries=3,
                       use_cache=True, cache_ttl=3600, cache_only=False, verbose=False):
    """
    Fetch data for multiple days and combine into a single dataset
    
    Args:
        api_client: TVGuideAPIClient instance
        platform: TV platform
        region: Geographic region
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        start_hour: Starting hour (0-23)
        end_hour: Ending hour (0-23)
        view: Display format
        details: Include additional details
        timeout: Request timeout
        max_retries: Maximum retry attempts
        use_cache: Whether to use cache
        cache_ttl: Cache time-to-live
        cache_only: Only use cached data
        verbose: Enable verbose output
    
    Returns:
        list: Combined JSON data from all days and hours
    """
    # Parse dates
    try:
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
    except ValueError as e:
        raise ValueError(f"Invalid date format: {e}")
    
    if start_dt > end_dt:
        raise ValueError("start_date must be less than or equal to end_date")
    
    if verbose:
        print(f"Fetching data for dates {start_date} to {end_date}")
    
    # Dictionary to store channel data by pa_id to avoid duplicates
    channels_dict = {}
    
    # Iterate through each day
    current_date = start_dt
    while current_date <= end_dt:
        date_str = current_date.strftime('%Y-%m-%d')
        if verbose:
            print(f"  Processing date {date_str}...")
        
        # For the last day, we might want to limit the end hour
        current_end_hour = end_hour
        if current_date.date() == end_dt.date():
            current_end_hour = end_hour
            
        try:
            # Fetch data for this day
            day_data = fetch_multiple_hours(
                api_client=api_client,
                platform=platform,
                region=region,
                date=date_str,
                start_hour=start_hour,
                end_hour=current_end_hour,
                view=view,
                details=details,
                timeout=timeout,
                max_retries=max_retries,
                use_cache=use_cache,
                cache_ttl=cache_ttl,
                cache_only=cache_only,
                verbose=verbose
            )
            
            # Merge channel data
            for channel in day_data:
                pa_id = channel['pa_id']
                if pa_id not in channels_dict:
                    channels_dict[pa_id] = channel
                else:
                    # Merge schedules
                    existing_schedules = {(s['pa_id'], s['start_at']) for s in channels_dict[pa_id]['schedules']}
                    for schedule in channel['schedules']:
                        schedule_key = (schedule['pa_id'], schedule['start_at'])
                        if schedule_key not in existing_schedules:
                            channels_dict[pa_id]['schedules'].append(schedule)
        except ValueError as e:
            if cache_only and "No cached data available" in str(e):
                if verbose:
                    print(f"    No cached data for date {date_str}, skipping...")
                current_date += timedelta(days=1)
                continue
            else:
                raise
        
        current_date += timedelta(days=1)
    
    # Convert back to list format
    return list(channels_dict.values())


def calculate_now_range(days=7):
    """
    Calculate the date and hour range for "now" mode:
    From (now - 1 hour) to (now + N days)
    Uses UTC time for consistency with API expectations.
    
    Args:
        days: Number of days to fetch (default: 7)
    
    Returns:
        tuple: (start_date, end_date, start_hour, end_hour)
    """
    now = datetime.utcnow()
    start_time = now - timedelta(hours=1)
    end_time = now + timedelta(days=days)
    
    start_date = start_time.strftime('%Y-%m-%d')
    end_date = end_time.strftime('%Y-%m-%d')
    start_hour = start_time.hour
    end_hour = 23  # We'll fetch through the end of each day
    
    return start_date, end_date, start_hour, end_hour


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Convert TV Guide JSON to XMLTV format',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert from JSON file
  %(prog)s --input input.json --output output.xml
  %(prog)s --input data.json --output guide.xml
  
  # Fetch from API (single hour)
  %(prog)s --api --platform sky --region london --date 2025-01-15 --hour 21 --output output.xml
  %(prog)s --api --platform freeview --region manchester --date 2025-01-16 --hour 19 --output guide.xml
  
  # Fetch from API (multiple hours)
  %(prog)s --api --platform sky --region london --date 2025-01-15 --start-hour 18 --end-hour 23 --output output.xml
  
  # Fetch from API (multiple days)
  %(prog)s --api --platform sky --region london --start-date 2025-01-15 --end-date 2025-01-17 --start-hour 18 --end-hour 23 --output output.xml
  
  # Fetch from API (now mode: last hour to next 7 days)
  %(prog)s --api --platform sky --region london --now --output output.xml
  
  # Fetch from API (now mode: last hour to next 3 days)
  %(prog)s --api --platform sky --region london --now --now-days 3 --output output.xml
        """
    )
    
    # Input source
    parser.add_argument('--input', help='Input JSON file path')
    parser.add_argument('--api', action='store_true', help='Fetch data from TV Guide API')
    
    # Output file path (optional for cache management commands)
    parser.add_argument('--output', help='Output XMLTV file path')
    
    # API parameters (required when --api is used)
    api_group = parser.add_argument_group('API options')
    api_group.add_argument('--platform', help='TV platform (e.g., sky, freeview)')
    api_group.add_argument('--region', help='Geographic region (e.g., london, manchester)')
    api_group.add_argument('--date', help='Date in YYYY-MM-DD format (for single day)')
    api_group.add_argument('--start-date', help='Start date in YYYY-MM-DD format (for multi-day)')
    api_group.add_argument('--end-date', help='End date in YYYY-MM-DD format (for multi-day)')
    api_group.add_argument('--hour', type=int, help='Hour in 24-hour format (0-23)')
    api_group.add_argument('--start-hour', type=int, help='Starting hour for fetch (0-23)')
    api_group.add_argument('--end-hour', type=int, help='Ending hour for fetch (0-23)')
    api_group.add_argument('--now', action='store_true', help='Fetch guide from (now - 1 hour) to (now + 7 days)')
    api_group.add_argument('--now-days', type=int, default=7, help='Number of days to fetch in --now mode (default: 7)')
    api_group.add_argument('--view', default='grid', help='Display format (default: grid)')
    api_group.add_argument('--details', action='store_true', help='Include additional details')
    
    # Cache options
    cache_group = parser.add_argument_group('Cache options')
    cache_group.add_argument('--cache-ttl', type=int, default=3600,
                           help='Cache time-to-live in seconds (default: 3600)')
    cache_group.add_argument('--no-cache', action='store_true',
                           help='Disable cache usage')
    cache_group.add_argument('--cache-only', action='store_true',
                           help='Only use cached data, do not make API calls')
    cache_group.add_argument('--clear-cache', action='store_true',
                           help='Clear all cached data and exit')
    cache_group.add_argument('--cache-stats', action='store_true',
                           help='Show cache statistics and exit')
    
    # General options
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Enable verbose output')
    parser.add_argument('--timeout', type=int, default=30,
                       help='API request timeout in seconds (default: 30)')
    parser.add_argument('--retries', type=int, default=3,
                       help='Maximum API retry attempts (default: 3)')
    
    args = parser.parse_args()
    
    # Handle cache management commands
    if args.clear_cache:
        cache = CacheManager()
        cache.clear_cache()
        print("Cache cleared successfully")
        sys.exit(0)
    
    if args.cache_stats:
        cache = CacheManager()
        stats = cache.get_cache_stats()
        print(f"Cache statistics:")
        print(f"  Files: {stats['files']}")
        print(f"  Total size: {stats['total_size']:,} bytes")
        sys.exit(0)
    
    # Validate that we have an input source and output for non-cache-management operations
    if not args.clear_cache and not args.cache_stats:
        if not args.api and not args.now and args.input is None:
            print("Error: Either provide an input file or use --api with required parameters", file=sys.stderr)
            sys.exit(1)
        if args.output is None:
            print("Error: Output file path is required", file=sys.stderr)
            sys.exit(1)
    
    # Validate API arguments
    if args.api or args.now:
        if requests is None:
            print("Error: requests library is required for API functionality.", file=sys.stderr)
            print("Install with: pip install requests", file=sys.stderr)
            sys.exit(1)
        
        required_api_args = ['platform', 'region']
        missing_args = [arg for arg in required_api_args if getattr(args, arg) is None]
        if missing_args:
            print(f"Error: The following arguments are required when using --api: {', '.join('--' + arg for arg in missing_args)}", file=sys.stderr)
            sys.exit(1)
        
        # Validate conflicting arguments
        date_args = [args.date, args.start_date, args.end_date, args.now]
        date_arg_count = sum(1 for arg in date_args if arg is not None)
        
        hour_args = [args.hour, args.start_hour, args.end_hour, args.now]
        hour_arg_count = sum(1 for arg in hour_args if arg is not None)
        
        # Validate --now-days is only used with --now
        if args.now_days != 7 and not args.now:
            print("Error: --now-days can only be used with --now", file=sys.stderr)
            sys.exit(1)
        
        # Validate --now-days value
        if args.now_days < 1:
            print("Error: --now-days must be at least 1", file=sys.stderr)
            sys.exit(1)
        
        if date_arg_count > 1:
            print("Error: Cannot specify more than one of --date, --start-date/--end-date, or --now", file=sys.stderr)
            sys.exit(1)
        
        if hour_arg_count > 1:
            print("Error: Cannot specify more than one of --hour, --start-hour/--end-hour, or --now", file=sys.stderr)
            sys.exit(1)
        
        # Validate hour ranges
        if args.hour is not None:
            if not (0 <= args.hour <= 23):
                print("Error: --hour must be between 0 and 23", file=sys.stderr)
                sys.exit(1)
        elif args.start_hour is not None or args.end_hour is not None:
            # Multi-hour mode
            if args.start_hour is None or args.end_hour is None:
                print("Error: Both --start-hour and --end-hour must be specified together", file=sys.stderr)
                sys.exit(1)
            if not (0 <= args.start_hour <= 23):
                print("Error: --start-hour must be between 0 and 23", file=sys.stderr)
                sys.exit(1)
            if not (0 <= args.end_hour <= 23):
                print("Error: --end-hour must be between 0 and 23", file=sys.stderr)
                sys.exit(1)
            if args.start_hour > args.end_hour:
                print("Error: --start-hour must be less than or equal to --end-hour", file=sys.stderr)
                sys.exit(1)
        
        # Validate date formats
        if args.date is not None:
            try:
                datetime.strptime(args.date, '%Y-%m-%d')
            except ValueError:
                print("Error: --date must be in YYYY-MM-DD format", file=sys.stderr)
                sys.exit(1)
        elif args.start_date is not None or args.end_date is not None:
            # Multi-day mode
            if args.start_date is None or args.end_date is None:
                print("Error: Both --start-date and --end-date must be specified together", file=sys.stderr)
                sys.exit(1)
            try:
                start_dt = datetime.strptime(args.start_date, '%Y-%m-%d')
                end_dt = datetime.strptime(args.end_date, '%Y-%m-%d')
                if start_dt > end_dt:
                    print("Error: --start-date must be less than or equal to --end-date", file=sys.stderr)
                    sys.exit(1)
            except ValueError:
                print("Error: --start-date and --end-date must be in YYYY-MM-DD format", file=sys.stderr)
                sys.exit(1)
    
    try:
        # Get JSON data (from file or API)
        if args.api:
            # Fetch from API
            if args.verbose:
                if args.now:
                    print(f"Fetching data from API: platform={args.platform}, region={args.region}, "
                          f"mode=now (last hour to next {args.now_days} days)")
                elif args.date is not None:
                    if args.hour is not None:
                        print(f"Fetching data from API: platform={args.platform}, region={args.region}, "
                              f"date={args.date}, hour={args.hour}")
                    else:
                        print(f"Fetching data from API: platform={args.platform}, region={args.region}, "
                              f"date={args.date}, hours={args.start_hour}-{args.end_hour}")
                else:
                    if args.hour is not None:
                        print(f"Fetching data from API: platform={args.platform}, region={args.region}, "
                              f"dates={args.start_date} to {args.end_date}, hour={args.hour}")
                    else:
                        print(f"Fetching data from API: platform={args.platform}, region={args.region}, "
                              f"dates={args.start_date} to {args.end_date}, hours={args.start_hour}-{args.end_hour}")
            
            api_client = TVGuideAPIClient()
            
            if args.now:
                # Now mode: from (now - 1 hour) to (now + N days)
                start_date, end_date, start_hour, end_hour = calculate_now_range(args.now_days)
                json_data = fetch_multiple_days(
                    api_client=api_client,
                    platform=args.platform,
                    region=args.region,
                    start_date=start_date,
                    end_date=end_date,
                    start_hour=start_hour,
                    end_hour=end_hour,
                    view=args.view,
                    details=args.details,
                    timeout=args.timeout,
                    max_retries=args.retries,
                    use_cache=not args.no_cache,
                    cache_ttl=args.cache_ttl,
                    cache_only=args.cache_only,
                    verbose=args.verbose
                )
            elif args.date is not None:
                # Single day mode
                if args.hour is not None:
                    # Single hour mode
                    json_data = api_client.fetch_listings(
                        platform=args.platform,
                        region=args.region,
                        date=args.date,
                        hour=args.hour,
                        view=args.view,
                        details=args.details,
                        timeout=args.timeout,
                        max_retries=args.retries,
                        use_cache=not args.no_cache,
                        cache_ttl=args.cache_ttl,
                        cache_only=args.cache_only
                    )
                else:
                    # Multi-hour mode
                    json_data = fetch_multiple_hours(
                        api_client=api_client,
                        platform=args.platform,
                        region=args.region,
                        date=args.date,
                        start_hour=args.start_hour,
                        end_hour=args.end_hour,
                        view=args.view,
                        details=args.details,
                        timeout=args.timeout,
                        max_retries=args.retries,
                        use_cache=not args.no_cache,
                        cache_ttl=args.cache_ttl,
                        cache_only=args.cache_only,
                        verbose=args.verbose
                    )
            else:
                # Multi-day mode
                json_data = fetch_multiple_days(
                    api_client=api_client,
                    platform=args.platform,
                    region=args.region,
                    start_date=args.start_date,
                    end_date=args.end_date,
                    start_hour=args.start_hour,
                    end_hour=args.end_hour,
                    view=args.view,
                    details=args.details,
                    timeout=args.timeout,
                    max_retries=args.retries,
                    use_cache=not args.no_cache,
                    cache_ttl=args.cache_ttl,
                    cache_only=args.cache_only,
                    verbose=args.verbose
                )
            
            if args.verbose:
                if args.cache_only:
                    print(f"Successfully loaded data from cache")
                else:
                    print(f"Successfully fetched data from API")
        else:
            # Read from file
            if args.verbose:
                print(f"Reading JSON from: {args.input}")
            
            with open(args.input, 'r', encoding='utf-8') as f:
                json_data = f.read()
        
        # Convert to XMLTV
        if args.verbose:
            print("Converting to XMLTV format...")
        
        converter = TVGuideConverter()
        converter.parse_json(json_data)
        tv_element = converter.generate_xmltv()
        xml_output = converter.to_xml_string(tv_element)
        
        # Write output XMLTV file
        if args.verbose:
            print(f"Writing XMLTV to: {args.output}")
        
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(xml_output)
        
        if args.verbose:
            print(f"Successfully converted {len(converter.channels)} channels "
                  f"and {len(converter.programmes)} programmes")
        
    except FileNotFoundError as e:
        print(f"Error: File not found - {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except requests.RequestException as e:
        print(f"Error: API request failed - {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
