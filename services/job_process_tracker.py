"""
Job process tracking service for verifying and managing running job processes
Handles process verification, health checks, and cleanup of stale job entries
"""
import os
import subprocess
from datetime import datetime, timedelta
from typing import List, Dict, Optional


class JobProcessTracker:
    """Service for tracking and verifying job processes"""
    
    def __init__(self):
        self.running_jobs_file = "/var/log/highball/running_jobs.txt"
        self.max_job_age_hours = 24
    
    def register_job(self, job_name: str):
        """Register a job as currently running with timestamp"""
        try:
            os.makedirs(os.path.dirname(self.running_jobs_file), exist_ok=True)
            with open(self.running_jobs_file, 'a') as f:
                f.write(f"{job_name}:{datetime.now().isoformat()}\n")
        except Exception as e:
            print(f"WARNING: Could not register running job {job_name}: {e}")
    
    def unregister_job(self, job_name: str):
        """Remove a job from the running jobs tracking"""
        try:
            if not os.path.exists(self.running_jobs_file):
                return
            
            # Read all lines except the one for this job
            with open(self.running_jobs_file, 'r') as f:
                lines = f.readlines()
            
            # Filter out lines for this job
            filtered_lines = [line for line in lines if not line.startswith(f"{job_name}:")]
            
            # Write back the filtered list
            with open(self.running_jobs_file, 'w') as f:
                f.writelines(filtered_lines)
        except Exception as e:
            print(f"WARNING: Could not unregister running job {job_name}: {e}")
    
    def get_verified_running_jobs(self) -> List[str]:
        """Get list of running jobs with process verification and automatic cleanup"""
        running_jobs = []
        jobs_to_cleanup = []
        
        try:
            if not os.path.exists(self.running_jobs_file):
                return running_jobs
            
            with open(self.running_jobs_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if ':' in line:
                        job_name, timestamp_str = line.split(':', 1)
                        
                        # Parse timestamp
                        try:
                            job_start_time = datetime.fromisoformat(timestamp_str)
                        except ValueError:
                            # Invalid timestamp, mark for cleanup
                            jobs_to_cleanup.append(job_name)
                            continue
                        
                        # Check if job has been running for more than max age
                        now = datetime.now()
                        if now - job_start_time > timedelta(hours=self.max_job_age_hours):
                            # Long-running job - verify it's actually running
                            if self.is_job_process_running(job_name):
                                # Legitimate long-running job - extend tracking
                                self._extend_job_tracking(job_name)
                                running_jobs.append(job_name)
                                print(f"INFO: Long-running job '{job_name}' verified and tracking extended")
                            else:
                                # Stale entry - mark for cleanup
                                jobs_to_cleanup.append(job_name)
                                print(f"INFO: Cleaning stale job entry: '{job_name}' (no active process found)")
                        else:
                            # Recent job - assume it's running (normal case)
                            running_jobs.append(job_name)
            
            # Clean up stale jobs
            for job_name in jobs_to_cleanup:
                self._cleanup_stale_job(job_name)
                        
        except Exception as e:
            print(f"WARNING: Could not read running jobs: {e}")
        
        return running_jobs
    
    def is_job_process_running(self, job_name: str) -> bool:
        """Check if a job process is actually running using HIGHBALL_JOB_ID"""
        try:
            # Use ps to find processes with our job ID environment variable
            # We look for any part of the job name in the HIGHBALL_JOB_ID env var
            result = subprocess.run([
                'ps', 'aux'
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                # Look for processes that contain HIGHBALL_JOB_ID with our job name
                for line in result.stdout.split('\n'):
                    if f'HIGHBALL_JOB_ID={job_name}_' in line:
                        return True
            
            return False
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, Exception) as e:
            print(f"WARNING: Could not check process status for job '{job_name}': {e}")
            # If we can't check, assume it's not running (safer for cleanup)
            return False
    
    def get_job_age(self, job_name: str) -> Optional[timedelta]:
        """Get how long a job has been running based on registration timestamp"""
        try:
            if not os.path.exists(self.running_jobs_file):
                return None
            
            with open(self.running_jobs_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith(f"{job_name}:"):
                        _, timestamp_str = line.split(':', 1)
                        try:
                            job_start_time = datetime.fromisoformat(timestamp_str)
                            return datetime.now() - job_start_time
                        except ValueError:
                            return None
            
            return None
        except Exception as e:
            print(f"WARNING: Could not get job age for '{job_name}': {e}")
            return None
    
    def get_tracked_jobs_with_details(self) -> List[Dict[str, any]]:
        """Get detailed information about all tracked jobs"""
        jobs = []
        try:
            if not os.path.exists(self.running_jobs_file):
                return jobs
            
            with open(self.running_jobs_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if ':' in line:
                        job_name, timestamp_str = line.split(':', 1)
                        
                        try:
                            job_start_time = datetime.fromisoformat(timestamp_str)
                            age = datetime.now() - job_start_time
                            is_running = self.is_job_process_running(job_name)
                            
                            jobs.append({
                                'name': job_name,
                                'start_time': job_start_time,
                                'age': age,
                                'is_process_running': is_running,
                                'is_stale': age > timedelta(hours=self.max_job_age_hours) and not is_running
                            })
                        except ValueError:
                            jobs.append({
                                'name': job_name,
                                'start_time': None,
                                'age': None,
                                'is_process_running': False,
                                'is_stale': True,
                                'error': 'Invalid timestamp'
                            })
        
        except Exception as e:
            print(f"WARNING: Could not get job details: {e}")
        
        return jobs
    
    def cleanup_all_stale_jobs(self) -> int:
        """Manually clean up all stale job entries and return count cleaned"""
        stale_jobs = []
        
        try:
            if not os.path.exists(self.running_jobs_file):
                return 0
            
            with open(self.running_jobs_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if ':' in line:
                        job_name, timestamp_str = line.split(':', 1)
                        
                        try:
                            job_start_time = datetime.fromisoformat(timestamp_str)
                            age = datetime.now() - job_start_time
                            
                            # Check if stale (old and not running)
                            if age > timedelta(hours=self.max_job_age_hours):
                                if not self.is_job_process_running(job_name):
                                    stale_jobs.append(job_name)
                        except ValueError:
                            # Invalid timestamp
                            stale_jobs.append(job_name)
            
            # Clean up all stale jobs
            for job_name in stale_jobs:
                self._cleanup_stale_job(job_name)
                print(f"INFO: Cleaned up stale job: '{job_name}'")
            
            return len(stale_jobs)
            
        except Exception as e:
            print(f"WARNING: Could not cleanup stale jobs: {e}")
            return 0
    
    def _extend_job_tracking(self, job_name: str):
        """Extend tracking for a legitimate long-running job by updating its timestamp"""
        try:
            if not os.path.exists(self.running_jobs_file):
                return
            
            # Read all lines
            with open(self.running_jobs_file, 'r') as f:
                lines = f.readlines()
            
            # Update the timestamp for this job
            updated_lines = []
            for line in lines:
                if line.startswith(f"{job_name}:"):
                    # Update with current timestamp
                    updated_lines.append(f"{job_name}:{datetime.now().isoformat()}\n")
                else:
                    updated_lines.append(line)
            
            # Write back updated list
            with open(self.running_jobs_file, 'w') as f:
                f.writelines(updated_lines)
                
        except Exception as e:
            print(f"WARNING: Could not extend tracking for job '{job_name}': {e}")
    
    def _cleanup_stale_job(self, job_name: str):
        """Remove stale job entry from tracking file"""
        try:
            if not os.path.exists(self.running_jobs_file):
                return
            
            # Read all lines except the stale one
            with open(self.running_jobs_file, 'r') as f:
                lines = f.readlines()
            
            # Filter out the stale job
            filtered_lines = [line for line in lines if not line.startswith(f"{job_name}:")]
            
            # Write back the filtered list
            with open(self.running_jobs_file, 'w') as f:
                f.writelines(filtered_lines)
                
        except Exception as e:
            print(f"WARNING: Could not cleanup stale job '{job_name}': {e}")