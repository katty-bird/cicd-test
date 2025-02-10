import os
import requests
import datetime
import statistics
from dotenv import load_dotenv

# Load the environment variables
load_dotenv()

# Set up the variables
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")  # My GitHub Token
REPO_OWNER = "katty-bird"
REPO_NAME = "cicd-test"
START_DATE = "2025-02-08T00:00:00Z"
END_DATE = "2025-02-09T23:59:59Z"

# Headers for API-requests
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"}

# Function to format time in minutes and seconds
def format_time(seconds):
    if seconds is None:
        return "N/A"
    minutes = int(seconds // 60)
    sec = int(seconds % 60)
    if minutes > 0:
        return f"{minutes} min {sec} sec"
    else:
        return f"{sec} sec"

# Function to get all workflow runs for the specified period
def get_workflow_runs():
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/actions/runs"
    params = {"per_page": 100}
    runs = []

    while url:
        response = requests.get(url, headers=HEADERS, params=params).json()
        if "workflow_runs" not in response:
            break

        for run in response["workflow_runs"]:
            created_at = run["created_at"]
            if START_DATE <= created_at <= END_DATE:
                runs.append(run)

        url = response.get("next", None)

    return runs

# Function to get the time of execution of steps inside the pipeline run
def get_job_times(run_id):
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/actions/runs/{run_id}/jobs"
    response = requests.get(url, headers=HEADERS).json()
    
    build_time = None
    push_time = None
    total_time = 0

    if "jobs" not in response:
        return None

    for job in response["jobs"]:
        for step in job["steps"]: 
            step_name = step["name"]
            start_time = datetime.datetime.fromisoformat(step["started_at"].replace("Z", "+00:00"))
            end_time = datetime.datetime.fromisoformat(step["completed_at"].replace("Z", "+00:00"))
            duration = (end_time - start_time).total_seconds()

            print(f"DEBUG: Step found -> {step_name} | Duration: {format_time(duration)}") 

            if step_name == "Build Docker image": 
                build_time = duration  
            if step_name == "Push Docker image":
                push_time = duration

            total_time += duration 

    return build_time, push_time, total_time

# Analysis of all pipelines
def analyze_pipelines():
    runs = get_workflow_runs()
    build_times = []
    push_times = []
    total_times = []

    for run in runs:
        build_time, push_time, total_time = get_job_times(run["id"])
        if build_time:
            build_times.append(build_time)
        if push_time:
            push_times.append(push_time)
        if total_time:
            total_times.append(total_time)

    avg_build_time = statistics.mean(build_times) if build_times else 0
    avg_push_time = statistics.mean(push_times) if push_times else 0
    avg_total_time = statistics.mean(total_times) if total_times else 0
    avg_without_push = avg_total_time - avg_push_time if avg_total_time and avg_push_time else 0

    print(f"Average runtime: {format_time(avg_total_time)}")
    print(f"Average build time: {format_time(avg_build_time)}")
    print(f"Average push time: {format_time(avg_push_time)}")
    print(f"Average runtime without push: {format_time(avg_without_push)}")

# Start the Metrics analysis
analyze_pipelines()