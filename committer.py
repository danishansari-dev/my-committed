import subprocess
import time
import os
import sys

# --- CONFIGURATION ---
AUTHOR_NAME = "danishansari-dev"
AUTHOR_EMAIL = "danishansari.dev@gmail.com"
BRANCH = "master"
BATCH_SIZE = 1000
TOTAL_EXECUTIONS = 3

PROGRESS_FILE = ".committer_progress"

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, "r") as f:
                lines = f.read().splitlines()
                if len(lines) >= 2:
                    return int(lines[0]), int(lines[1])
        except Exception as e:
            print(f"Error reading progress file: {e}")
            pass
    return 0, 0

def save_progress(total_commits, executions):
    with open(PROGRESS_FILE, "w") as f:
        f.write(f"{total_commits}\n{executions}\n")

def get_head_hash():
    try:
         result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
         return result.stdout.strip()
    except subprocess.CalledProcessError:
         return None

def get_tree_hash(commit_hash):
    try:
        result = subprocess.run(["git", "cat-file", "-p", commit_hash], capture_output=True, text=True, check=True)
        for line in result.stdout.splitlines():
            if line.startswith("tree "):
                return line.split(" ")[1].strip()
        return None
    except subprocess.CalledProcessError:
        return None

def push_with_retry():
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"Pushing to origin (Attempt {attempt + 1}/{max_retries})...")
            subprocess.run(["git", "push", "origin", BRANCH], check=True)
            print("Push successful.")
            return True
        except subprocess.CalledProcessError:
            print(f"Push failed.")
            if attempt < max_retries - 1:
                print("Retrying in 5 seconds...")
                time.sleep(5)
    print("All push attempts failed.")
    return False

def generate_commits(executions_done, initial_commits_done, target_executions):
    
    total_commits = initial_commits_done
    
    # We will spread timestamps backwards from current time
    # This prevents git from complaining about duplicate duplicate timestamps/commits
    # We'll use 1 second intervals for simplicity
    current_time = int(time.time())
    
    try:
        for i in range(executions_done, target_executions):
            start_time = time.time()
            
            head_hash = get_head_hash()
            if not head_hash:
                print("Could not find HEAD. Is the repository initialized with at least one commit?")
                return
            
            tree_hash = get_tree_hash(head_hash)
            if not tree_hash:
                print(f"Could not find tree hash for commit {head_hash}")
                return

            # Build fast-import stream
            stream = []
            
            parent = head_hash
            for j in range(BATCH_SIZE):
                 commit_time = current_time - (total_commits + j)
                 
                 stream.append(f"commit refs/heads/{BRANCH}")
                 stream.append(f"mark :{j+1}")
                 stream.append(f"committer {AUTHOR_NAME} <{AUTHOR_EMAIL}> {commit_time} +0000")
                 stream.append(f"data 12")
                 stream.append("Empty commit")
                 stream.append(f"from {parent}")
                 stream.append(f"M 040000 {tree_hash} \"\"")
                 stream.append("")
                 
                 parent = f":{j+1}"

            stream_data = "\n".join(stream) + "\n"

            # Pipe to fast-import
            process = subprocess.Popen(["git", "fast-import", "--quiet", "--done"], stdin=subprocess.PIPE, text=True)
            process.communicate(input=stream_data)
            
            if process.returncode != 0:
                print(f"git fast-import failed with return code {process.returncode}")
                return
                
            total_commits += BATCH_SIZE
            current_exec = i + 1
            
            if not push_with_retry():
                 print("Stopping due to push failure.")
                 return
                 
            save_progress(total_commits, current_exec)
            
            elapsed = time.time() - start_time
            speed = BATCH_SIZE / elapsed if elapsed > 0 else 0
            
            print(f"Execution {current_exec}/{target_executions} | Total commits: {total_commits:,} | Speed: {speed:,.0f} commits/s")
            
    except KeyboardInterrupt:
        print("\nInterrupted by user. Exiting gracefully.")
        sys.exit(0)

def main():
    total_commits_done, executions_done = load_progress()
    print(f"Starting/Resuming commit generation...")
    print(f"Previous progress: {executions_done} executions, {total_commits_done} commits")
    
    if executions_done >= TOTAL_EXECUTIONS:
        print("Target executions already reached!")
        return

    generate_commits(executions_done, total_commits_done, TOTAL_EXECUTIONS)

if __name__ == "__main__":
    main()
