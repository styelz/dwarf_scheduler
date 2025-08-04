#!/usr/bin/env python3
"""
Quick fix for orphaned running sessions
"""
import sys
import os
sys.path.append('.')

from core.config_manager import ConfigManager
from core.scheduler import Scheduler

def main():
    print("Dwarf Scheduler - Orphaned Session Recovery")
    print("=" * 50)
    
    # Initialize components
    config_manager = ConfigManager()
    from core.session_manager import SessionManager
    session_manager = SessionManager()
    scheduler = Scheduler(session_manager, config_manager)
    
    # Check for running sessions
    running_count = scheduler.session_manager.get_running_sessions_count()
    print(f"Found {running_count} orphaned running sessions")
    
    if running_count == 0:
        print("No orphaned sessions found. All good!")
        return
    
    # Show options
    print("\nRecovery Options:")
    print("1. Mark as Failed (sessions recorded as failed)")
    print("2. Return to Queue (sessions will be scheduled again)")
    print("3. Make Available (sessions can be edited and rescheduled)")
    print("4. List sessions first")
    print("5. Exit without changes")
    
    while True:
        choice = input("\nEnter your choice (1-5): ").strip()
        
        if choice == "1":
            # Mark as failed
            recovered = scheduler.recover_running_sessions("fail")
            print(f"✓ Marked {len(recovered)} sessions as failed")
            for session in recovered:
                print(f"  - {session}")
            break
            
        elif choice == "2":
            # Return to queue
            recovered = scheduler.recover_running_sessions("todo")
            print(f"✓ Moved {len(recovered)} sessions back to queue")
            for session in recovered:
                print(f"  - {session}")
            break
            
        elif choice == "3":
            # Make available
            recovered = scheduler.recover_running_sessions("available")
            print(f"✓ Moved {len(recovered)} sessions to available")
            for session in recovered:
                print(f"  - {session}")
            break
            
        elif choice == "4":
            # List sessions
            print("\nOrphaned Running Sessions:")
            running_dir = "Sessions/Running"
            if os.path.exists(running_dir):
                sessions = os.listdir(running_dir)
                for session in sessions:
                    if session.endswith('.json'):
                        print(f"  - {session}")
            continue
            
        elif choice == "5":
            print("Exiting without changes.")
            return
            
        else:
            print("Invalid choice. Please enter 1-5.")
            continue
    
    print("\nRecovery complete! You can now start the GUI application normally.")

if __name__ == "__main__":
    main()
