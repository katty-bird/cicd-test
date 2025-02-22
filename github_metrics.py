import os
import requests
import datetime
import statistics
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# GitHub credentials
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_OWNER = "katty-bird"
REPO_NAME = "cicd-test"
START_DATE = "2025-02-16T00:00:00Z"
END_DATE = "2025-02-19T23:59:59Z"

# API headers
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"}

# Function to parse ISO datetime string
def parse_iso_datetime(date_str):
    return datetime.datetime.fromisoformat(date_str.replace("Z", "+00:00"))

def format_time_human(seconds):
    if seconds < 60:
        return f"{int(seconds)} sec"
    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)
    return f"{minutes} min {remaining_seconds} sec"

# Function to format time in seconds
def format_time(seconds):
    return round(seconds) if seconds is not None else 0

# Function to get all workflow runs
def get_workflow_runs():
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/actions/runs"
    params = {"per_page": 100}
    response = requests.get(url, headers=HEADERS, params=params).json()
    
    runs = []
    for run in response.get("workflow_runs", []):
        created_at = run["created_at"]
        if (
            START_DATE <= created_at <= END_DATE and
            run["status"] == "completed" and
            run["event"] == "schedule"
        ):
            run_started_at = run["updated_at"]
            queue_time = (parse_iso_datetime(run_started_at) - parse_iso_datetime(created_at)).total_seconds()
            
            runs.append({
                "id": run["id"],
                "created_at": created_at,
                "run_started_at": run_started_at,
                "queue_time": format_time(queue_time)
            })
    return runs

# Function to get job execution times
def get_job_times(run):
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/actions/runs/{run['id']}/jobs"
    response = requests.get(url, headers=HEADERS).json()
    
    build_time, push_time, total_time = 0, 0, 0

    for job in response["jobs"]:
        for step in job["steps"]: 
            step_name = step["name"]
            start_time = parse_iso_datetime(step["started_at"])
            end_time = parse_iso_datetime(step["completed_at"])
            duration = (end_time - start_time).total_seconds()
            
            if "Build Docker image" in step_name and "Post" not in step_name:
                print(f"DEBUG: Build step found -> {step_name}, Duration: {duration} sec")
                build_time = duration  
            if "Push Docker image" in step_name:
                push_time = duration

            total_time += duration 

    return format_time(build_time), format_time(push_time), format_time(total_time)

# Analysis of all pipelines
def analyze_pipelines():
    runs = get_workflow_runs()
    build_times, push_times, total_times, queue_times = [], [], [], []

    for run in runs:
        result = get_job_times(run)
        if result:
            build_time, push_time, total_time = result
            queue_time = run["queue_time"]
            build_times.append(build_time)
            push_times.append(push_time)
            total_times.append(total_time)
            queue_times.append(queue_time)

    # Calculate total runtime in minutes
    all_run_minutes = sum(total_times) / 60

    avg_build_time = format_time(statistics.mean(build_times) if build_times else 0)
    avg_push_time = format_time(statistics.mean(push_times) if push_times else 0)
    avg_total_time = format_time(statistics.mean(total_times) if total_times else 0)
    avg_without_push = format_time(avg_total_time - avg_push_time if avg_total_time and avg_push_time else 0)
    avg_queue_time = format_time(statistics.mean(queue_times) if queue_times else 0)

    print(f"Runs analyzed: {len(runs)}")
    print(f"Total time of {len(runs)} runs: {format_time_human(all_run_minutes * 60)}")
    print(f"Average runtime: {format_time_human(avg_total_time)}")
    print(f"Average build time: {format_time_human(avg_build_time)}")
    print(f"Average push time: {format_time_human(avg_push_time)}")
    print(f"Average runtime without push: {format_time_human(avg_without_push)}")
    print(f"Average queue time: {format_time_human(avg_queue_time)}")

    # For numerical analysis and graphs
    with open("git_raw_data/github_pipeline_data_sec.csv", "w") as f:
        f.write("Index,Build Time,Push Time,Total Time,Queue Time\n")
        for i, run in enumerate(runs):
            f.write(f"{i+1},{build_times[i]},{push_times[i]},{total_times[i]},{queue_times[i]}\n")

    # Export readable format
    with open("git_raw_data/github_pipeline_data_min.csv", "w") as f:
        f.write("Index,Build Time,Push Time,Total Time,Queue Time\n")
        for i, run in enumerate(runs):
            f.write(f"{i+1},{format_time_human(build_times[i])},{format_time_human(push_times[i])},{format_time_human(total_times[i])},{format_time_human(queue_times[i])}\n")

    # Export Average times in readable format
    with open("git_raw_data/github_average_time_sec.csv", "w") as f:
        f.write("Runs Analyzed,Average Runtime,Average Build Time,Average Push Time,Average Runtime Without Push,Average Queue Time,Total Runtime\n")
        f.write(f"{len(runs)},{format_time_human(avg_total_time)},{format_time_human(avg_build_time)},{format_time_human(avg_push_time)},{format_time_human(avg_without_push)},{format_time_human(avg_queue_time)},{format_time_human(all_run_minutes * 60)}\n")

# Start the Metrics analysis
analyze_pipelines()
