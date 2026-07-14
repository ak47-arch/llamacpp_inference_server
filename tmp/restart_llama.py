import os, signal, time, sys

def find_llama_pid():
    for pid in os.listdir("/proc"):
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                cmd = f.read().decode().replace("\x00", " ")
                if "llama-server" in cmd:
                    return int(pid)
        except:
            pass
    return None

pid = find_llama_pid()
if pid:
    print(f"Found llama-server PID: {pid}")
    os.kill(pid, signal.SIGTERM)
    print("Sent SIGTERM")
else:
    print("No llama-server found running")
    sys.exit(1)

# Wait for restart
for i in range(30):
    time.sleep(2)
    new_pid = find_llama_pid()
    if new_pid and new_pid != pid:
        with open(f"/proc/{new_pid}/cmdline", "rb") as f:
            cmd = f.read().decode().replace("\x00", " ")
        print(f"New server started! PID: {new_pid}")
        print(f"Command: {cmd}")
        sys.exit(0)
    print(f"Waiting... ({i+1}/30)")

print("Timed out waiting for restart")
sys.exit(1)
