import os
import requests
import statistics
import re
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Bitbucket credentials
BITBUCKET_WORKSPACE = "markdown-project"
BITBUCKET_REPO = "cicd-test"
BITBUCKET_USERNAME = "kattebird"
BITBUCKET_APP_PASSWORD = os.getenv("BITBUCKET_APP_PASSWORD")

# API headers
HEADERS = {"Accept": "application/json"}

# Function to parse ISO datetime string
def parse_iso_datetime(date_str):
    date_str = date_str.rstrip("Z")  # Remove 'Z' if present
    date_str = date_str.split(".")[0]  # Keep only seconds, remove microseconds
    return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")

def format_time_human(seconds):
    if seconds < 60:
        return f"{int(seconds)} sec"
    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)
    return f"{minutes} min {remaining_seconds} sec"

# Function to get all pipeline runs
def get_pipelines():
    url = f"https://api.bitbucket.org/2.0/repositories/{BITBUCKET_WORKSPACE}/{BITBUCKET_REPO}/pipelines?status=PASSED&sort=-created_on&pagelen=80"
    response = requests.get(url, headers=HEADERS, auth=(BITBUCKET_USERNAME, BITBUCKET_APP_PASSWORD))
    data = response.json()
    
    pipelines = []
    for pipeline in data.get("values", []):
        if pipeline["state"]["name"] == "COMPLETED":
            created_at = pipeline["created_on"]
            completed_at = pipeline["completed_on"]
            duration = pipeline["duration_in_seconds"]
            queue_time = (parse_iso_datetime(completed_at) - parse_iso_datetime(created_at)).total_seconds() - duration
            
            pipelines.append({
                "uuid": pipeline["uuid"],
                "created_at": created_at,
                "completed_at": completed_at,
                "duration_seconds": duration,
                "queue_time": round(max(queue_time, 0))
            })
    return pipelines

# Function to get steps for a specific pipeline
def get_pipeline_steps(pipeline_uuid):
    url = f"https://api.bitbucket.org/2.0/repositories/{BITBUCKET_WORKSPACE}/{BITBUCKET_REPO}/pipelines/{pipeline_uuid}/steps"
    response = requests.get(url, headers=HEADERS, auth=(BITBUCKET_USERNAME, BITBUCKET_APP_PASSWORD))
    
    if response.status_code == 200:
        data = response.json()
        steps = [
            {"uuid": step["uuid"], "name": step["name"], "log_available": step.get("log_available", False)}
            for step in data.get("values", [])
        ]
        return steps
    else:
        print(f"ERROR: Failed to get steps for pipeline {pipeline_uuid}")
        return []

# Function to get logs for a specific step of a pipeline
def get_pipeline_log(pipeline_uuid, step_uuid):
    url = f"https://api.bitbucket.org/2.0/repositories/{BITBUCKET_WORKSPACE}/{BITBUCKET_REPO}/pipelines/{pipeline_uuid}/steps/{step_uuid}/log"
    response = requests.get(url, auth=(BITBUCKET_USERNAME, BITBUCKET_APP_PASSWORD))

    if response.status_code == 200:
        return response.text
    else:
        print(f"ERROR: Failed to get log for pipeline {pipeline_uuid}, step {step_uuid}, {response.status_code}")
        return None

# Function to extract step times from logs
def extract_step_times(log_text):
    build_time = 0
    push_time = 0

    for line in log_text.split("\n"):
        match = re.search(r"(.+)\s* took (\d+) seconds", line.strip())
        
        if match:
            step_name = match.group(1).strip()
            duration = int(match.group(2))

            if "docker build" in step_name:
                build_time = duration
            
            if "docker login" in step_name or "docker tag" in step_name or "docker push" in step_name:
                push_time += duration 

    return build_time, push_time

# Function to analyze pipelines
def analyze_pipelines():
    pipelines = get_pipelines()
    build_times, push_times, total_times, queue_times = [], [], [], []
        
    print("DEBUG: Pipelines:", pipelines)
    for pipeline in pipelines:
        steps = get_pipeline_steps(pipeline["uuid"])
        print(f"DEBUG: Pipeline {pipeline['uuid']} has steps: {steps}")

        for step in steps:
            print(f"DEBUG: Step found -> {step['name']} (UUID: {step['uuid']})")
            if "Build and Push Docker" in step["name"]: 
                log_text = get_pipeline_log(pipeline["uuid"], step["uuid"])
                
                if log_text:
                    build_time, push_time = extract_step_times(log_text)
                    if build_time == 0 or push_time == 0:
                        print(f"ERROR: Build time or push time is 0 for pipeline {pipeline['uuid']}")
                        continue
                    total_time = pipeline["duration_seconds"]
                    total_without_push = total_time - push_time

                    build_times.append(build_time)
                    push_times.append(push_time)
                    total_times.append(total_time)
                    queue_times.append(pipeline["queue_time"])

    avg_build_time = round(statistics.mean(build_times) if build_times else 0)
    avg_push_time = round(statistics.mean(push_times) if push_times else 0)
    avg_total_time = round(statistics.mean(total_times) if total_times else 0)
    avg_without_push = round(avg_total_time - avg_push_time if avg_total_time and avg_push_time else 0)
    avg_queue_time = round(statistics.mean(queue_times) if queue_times else 0)

    # Calculate total runtime in minutes
    all_run_minutes = sum(total_times) / 60

    print(f"Runs analyzed: {len(build_times)}")
    print(f"Total time of {len(build_times)} runs: {format_time_human(all_run_minutes * 60)}")
    print(f"Average runtime: {format_time_human(avg_total_time)}")
    print(f"Average build time: {format_time_human(avg_build_time)}")
    print(f"Average push time: {format_time_human(avg_push_time)}")
    print(f"Average runtime without push: {format_time_human(avg_without_push)}")
    print(f"Average queue time: {format_time_human(avg_queue_time)}")

    # Export numerical data for analysis
    with open("bitbucket_pipeline_data_sec.csv", "w") as f:
        f.write("Index,Build Time,Push Time,Total Time,Queue Time\n")  
        for i in range(len(build_times)):
            f.write(f"{i+1},{build_times[i]},{push_times[i]},{total_times[i]},{queue_times[i]}\n")

    # Export readable format
    with open("bitbucket_pipeline_data_min.csv", "w") as f:
        f.write("Index,Build Time,Push Time,Total Time,Queue Time\n")
        for i in range(len(build_times)):
            f.write(f"{i+1},{format_time_human(build_times[i])},{format_time_human(push_times[i])},{format_time_human(total_times[i])},{format_time_human(queue_times[i])}\n")

    # Export Average times in readable format
    with open("bitbucket_average_time_min.csv", "w") as f:
        f.write("Runs Analyzed,Average Runtime,Average Build Time,Average Push Time,Average Runtime Without Push,Average Queue Time, Total Runtime\n")
        f.write(f"{len(build_times)},{format_time_human(avg_total_time)},{format_time_human(avg_build_time)},{format_time_human(avg_push_time)},{format_time_human(avg_without_push)},{format_time_human(avg_queue_time)},{format_time_human(all_run_minutes * 60)}\n")

# Run analysis
analyze_pipelines()
