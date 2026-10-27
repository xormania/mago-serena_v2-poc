import os,sys
from pathlib import Path
with Path(os.environ["POC_WORKER_LAUNCH"]).open("a") as f: f.write("worker-started\n")
os.execvpe(sys.argv[1],sys.argv[1:],os.environ)
