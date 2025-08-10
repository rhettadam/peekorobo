#!/usr/bin/env python3


from tqdm import tqdm
from tenacity import retry, stop_never, wait_exponential, retry_if_exception_type
import requests
import os
import concurrent.futures
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
import random
import signal
import sys
import threading
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from datagather import return_pg_connection, close_connection_pool

load_dotenv()

TBA_BASE_URL = "https://www.thebluealliance.com/api/v3"
API_KEYS = os.getenv("TBA_API_KEYS").split(',')

# Global variables for cleanup
active_executors = []
shutdown_event = threading.Event()

def signal_handler(signum, frame):
    # Handle Ctrl+C and other termination signals
    print(f"\nReceived signal {signum}. Shutting down...")
    shutdown_event.set()
    
    # Cancel all running futures
    for executor in active_executors:
        if hasattr(executor, 'shutdown'):
            executor.shutdown(wait=False, cancel_futures=True)
    
    # Close the connection pool
    close_connection_pool()
    
    print("Cleanup complete. Exiting.")
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def cleanup_executor(executor):
    # Safely shutdown an executor
    if executor and hasattr(executor, 'shutdown'):
        try:
            executor.shutdown(wait=False, cancel_futures=True)
        except Exception as e:
            print(f"Warning: Error shutting down executor: {e}")

# Context manager for database connections
class DatabaseConnection:
    """Context manager for database connections from the pool."""
    
    def __init__(self):
        self.conn = None
        
    def __enter__(self):
        from datagather import get_pg_connection
        self.conn = get_pg_connection()
        return self.conn
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            return_pg_connection(self.conn)

@retry(stop=stop_never, wait=wait_exponential(min=0.5, max=5), retry=retry_if_exception_type(Exception))
def tba_get(endpoint: str):
    api_key = random.choice(API_KEYS)
    headers = {"X-TBA-Auth-Key": api_key}
    url = f"{TBA_BASE_URL}/{endpoint}"
    try:
        r = requests.get(url, headers=headers, timeout=30)
        if r.status_code == 200:
            return r.json()
        else:
            print(f"TBA API error for {endpoint}: {r.status_code}")
            return None
    except requests.exceptions.Timeout:
        print(f"Timeout for {endpoint}")
        raise
    except requests.exceptions.RequestException as e:
        print(f"Request error for {endpoint}: {e}")
        raise
    except Exception as e:
        print(f"Unexpected error for {endpoint}: {e}")
        raise

def get_recent_events(year, days_back=7):
    """Get all events for a year that ended within the specified number of days from database."""
    cutoff_date = datetime.now() - timedelta(days=days_back)
    recent_events = []
    
    with DatabaseConnection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT event_key, name, year, start_date, end_date, event_type, city, state_prov, country, website
            FROM events 
            WHERE year = %s AND (end_date IS NULL OR end_date >= %s)
        """, (year, cutoff_date.strftime("%Y-%m-%d")))
        
        for row in cur.fetchall():
            recent_events.append({
                "key": row[0],
                "name": row[1],
                "year": row[2],
                "start_date": row[3],
                "end_date": row[4],
                "event_type": row[5],
                "city": row[6],
                "state_prov": row[7],
                "country": row[8],
                "website": row[9]
            })
        cur.close()
    
    print(f"Found {len(recent_events)} recent events to check for awards")
    return recent_events

def get_existing_awards(event_key):
    """Get existing awards from database for comparison."""
    with DatabaseConnection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT team_number, award_name FROM event_awards WHERE event_key = %s", (event_key,))
        awards = set((row[0], row[1]) for row in cur.fetchall())
        cur.close()
    return awards

def fetch_and_update_awards(event):
    """Fetch and update awards for a single event."""
    if shutdown_event.is_set():
        return None
        
    event_key = event["key"]
    year = event.get("year", event_key[:4])
    
    # Get existing awards for comparison
    existing_awards = get_existing_awards(event_key)
    
    # Fetch new awards
    try:
        awards_data = tba_get(f"event/{event_key}/awards")
        if not awards_data:
            return {"event_key": event_key, "updated": False, "reason": "No awards data"}
        
        new_awards = []
        for award in awards_data:
            for recipient in award.get("recipient_list", []):
                if recipient.get("team_key"):
                    team_key = recipient["team_key"]
                    team_number = int(team_key[3:])  # Remove "frc" prefix
                    award_name = award.get("name", "")
                    
                    new_awards.append((event_key, team_number, award_name, year))
        
        # Check if awards have changed
        new_awards_set = set((award[1], award[2]) for award in new_awards)
        
        if existing_awards == new_awards_set:
            return {"event_key": event_key, "updated": False, "reason": "No changes"}
        
        # Update awards in database
        with DatabaseConnection() as conn:
            cur = conn.cursor()
            
            # Delete existing awards for this event
            cur.execute("DELETE FROM event_awards WHERE event_key = %s", (event_key,))
            
            # Insert new awards (deduplicate first)
            seen = set()
            deduped_awards = []
            for award in new_awards:
                key = (award[0], award[1], award[2])
                if key not in seen:
                    seen.add(key)
                    deduped_awards.append(award)
            
            if deduped_awards:
                cur.executemany("""
                    INSERT INTO event_awards (event_key, team_number, award_name, year)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (event_key, team_number, award_name) DO NOTHING
                """, deduped_awards)
            
            conn.commit()
            cur.close()
        
        return {
            "event_key": event_key, 
            "updated": True, 
            "awards_count": len(deduped_awards),
            "reason": f"Updated {len(deduped_awards)} awards"
        }
        
    except Exception as e:
        print(f"Error processing awards for event {event_key}: {e}")
        return {"event_key": event_key, "updated": False, "reason": f"Error: {e}"}

def update_awards_for_year(year, days_back=7):
    """Update awards for all recent events in a given year."""
    print(f"\nUpdating awards for {year} (events within last {days_back} days)...")
    
    # Get recent events
    recent_events = get_recent_events(year, days_back)
    
    if not recent_events:
        print("No recent events found to update awards for.")
        return
    
    # Process events in parallel
    updated_count = 0
    skipped_count = 0
    failed_events = []
    executor = None
    
    try:
        executor = ThreadPoolExecutor(max_workers=5)  # Lower concurrency for awards
        active_executors.append(executor)
        
        futures = [executor.submit(fetch_and_update_awards, event) for event in recent_events]
        
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(recent_events), desc="Updating awards"):
            if shutdown_event.is_set():
                print("Shutdown requested, stopping award updates...")
                break
                
            try:
                result = future.result()
                if result is None:
                    failed_events.append("Unknown event (result was None)")
                elif result["updated"]:
                    updated_count += 1
                    print(f"Updated awards for {result['event_key']}: {result['reason']}")
                else:
                    skipped_count += 1
                    
            except Exception as e:
                event_info = "Unknown event"
                try:
                    if hasattr(future, '_args') and future._args:
                        event_info = f"Event {future._args[0].get('key', 'Unknown')}"
                except:
                    pass
                failed_events.append(f"{event_info}: {str(e)}")
                print(f"Failed to process {event_info}: {e}")
                continue
    finally:
        if executor:
            cleanup_executor(executor)
            if executor in active_executors:
                active_executors.remove(executor)
    
    if shutdown_event.is_set():
        print("Shutdown requested, stopping award updates...")
        return
    
    print(f"\nAward Update Summary for {year}:")
    print(f"  Total events processed: {len(recent_events)}")
    print(f"  Events updated: {updated_count}")
    print(f"  Events skipped (no changes): {skipped_count}")
    print(f"  Events failed: {len(failed_events)}")
    
    if failed_events:
        print(f"Failed to process {len(failed_events)} events:")
        for failed in failed_events[:10]:
            print(f"  - {failed}")
        if len(failed_events) > 10:
            print(f"  ... and {len(failed_events) - 10} more")

def main():
    print("\nAwards Update Tool")
    print("="*40)
    
    try:
        year = input("Enter year (e.g., 2025): ").strip()
        try:
            year = int(year)
        except ValueError:
            print("Invalid year. Please enter a valid year.")
            return
        
        days_back = input("Enter days back to check (default 7): ").strip()
        if not days_back:
            days_back = 7
        else:
            try:
                days_back = int(days_back)
            except ValueError:
                print("Invalid days. Using default of 7.")
                days_back = 7
            
        update_awards_for_year(year, days_back)
            
    except KeyboardInterrupt:
        print("\nInterrupted by user (Ctrl+C)")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
    finally:
        # Final cleanup
        print("\nPerforming final cleanup...")
        for executor in active_executors:
            cleanup_executor(executor)
        print("Cleanup complete.")

if __name__ == "__main__":
    try:
        if len(sys.argv) > 1:
            # Command-line mode: python update_awards.py <year> [days_back]
            if len(sys.argv) < 2:
                print("Usage: python update_awards.py <year> [days_back]")
                sys.exit(1)
            try:
                year = int(sys.argv[1])
                days_back = int(sys.argv[2]) if len(sys.argv) > 2 else 7
            except ValueError:
                print("Year and days_back must be integers.")
                sys.exit(1)
            update_awards_for_year(year, days_back)
        else:
            main()
    except KeyboardInterrupt:
        print("\nInterrupted by user (Ctrl+C)")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
    finally:
        # Final cleanup
        print("\nPerforming final cleanup...")
        for executor in active_executors:
            cleanup_executor(executor)
        print("Cleanup complete.")
