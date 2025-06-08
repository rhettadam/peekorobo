import os
import subprocess
import schedule
import time
from datetime import datetime
from createeventdb import update_database

def update_and_push():
    try:
        # Update the database
        update_database()
        
        # Git commands to push changes
        subprocess.run(['git', 'add', 'events.sqlite'])
        subprocess.run(['git', 'commit', '-m', f'Automated database update: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'])
        subprocess.run(['git', 'push'])
        
        print(f"✅ Database updated and pushed to GitHub at {datetime.now()}")
    except Exception as e:
        print(f"❌ Error during update: {e}")

def main():
    # Run immediately on startup
    update_and_push()
    
    # Schedule to run every 6 hours
    schedule.every(6).hours.do(update_and_push)
    
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main() 