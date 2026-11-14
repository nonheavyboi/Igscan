import os, random, re, time, threading, queue, requests
from pathlib import Path

TOTAL   = int(os.getenv("TOTAL", "20000"))
SHARDS  = int(os.getenv("SHARDS", "8"))
SHARD   = int(os.getenv("SHARD", "0"))
WORKERS = int(os.getenv("WORKERS", "3"))
SEED    = int(os.getenv("SEED", "1337"))

OUT = Path("results"); OUT.mkdir(exist_ok=True)
FREE = OUT / f"free_{SHARD}.txt"
DONE = OUT / f"done_{SHARD}.txt"

HEAD = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9"}

ON = "b c d f g h j k l m n p r s t v w z br ch cl cr dr fl fr gl gr pl pr sh sk sl sn sp st th tr".split()
VO = "a e i o u".split()
CO = "b d f g k l m n p r s t v x z ck ld lt mp nd ng nk nt rk rt sk st th".split()
WORDS = """ash oak salt iron wolf hive dusk fern moss tide glow echo mist thorn river
stone cloud spark drift bloom ember frost grain hollow ivory juniper kiln lantern meadow
nectar orbit pine quartz reed ridge smoke steel timber umber vale willow yarn zenith
era club files daily studio note frame line press room shift trail verse""".split()

def mk(rng):
    r = rng.random()
    if r < 0.30:
        return rng.choice(WORDS)
    n = rng.choice([2, 2, 3, 3, 4])
    s = ""
    while len(s) < n:
        s += rng.choice(ON) if (not s or s[-1] in "aeiou") else rng.choice(CO)
    return s[:n]

def build(rng, count):
    seen = set(); guard = 0
    while len(seen) < count and guard < count * 40:
        guard += 1
        parts = [mk(rng) for _ in range(rng.choice([2, 2, 2, 3]))]
        name = parts[0]
        for p in parts[1:]:
            name += rng.choice("....._") + p
        if not (4 <= len(name) <= 28): continue
        if re.search(r"[._]{2}", name): continue
        if re.search(r"([a-z])\1{2}", name): continue
        if not re.search(r"[aeiou]", name): continue
        seen.add(name)
    return list(seen)

rng = random.Random(SEED)
mine = build(rng, TOTAL)[SHARD::SHARDS]

done = set()
if DONE.exists():
    done = set(DONE.read_text().split())
mine = [n for n in mine if n not in done]
print(f"shard {SHARD}: {len(mine)} to check", flush=True)

lock = threading.Lock()
q = queue.Queue()
for n in mine: q.put(n)

stats = {"free": 0, "taken": 0, "rate": 0, "err": 0}
stop = threading.Event()

def classify(name):
    s = requests.Session(); s.headers.update(HEAD)
    try:
        r = s.get(f"https://www.instagram.com/{name}/", timeout=20)
        b = r.text.lower()
        if r.status_code == 429: return "RATE"
        if r.status_code == 404: return "FREE"
        if "page not found" in b or "isn't available" in b: return "FREE"
        if "please wait a few minutes" in b or "challenge" in b: return "RATE"
        return "TAKEN"
    except Exception:
        return "ERR"

def worker():
    streak = 0
    while not stop.is_set():
        try: name = q.get_nowait()
        except queue.Empty: return
        v = classify(name)
        with lock:
            if v == "FREE":
                stats["free"] += 1
                with FREE.open("a") as f: f.write(name + "\n")
                print("FREE " + name, flush=True)
            elif v == "TAKEN": stats["taken"] += 1
            elif v == "RATE": stats["rate"] += 1
            else: stats["err"] += 1
            with DONE.open("a") as f: f.write(name + "\n")
        streak = streak + 1 if v in ("RATE", "ERR") else 0
        if streak >= 12:
            print("too many blocks, stopping", flush=True)
            stop.set(); return
        time.sleep(90 if v == "RATE" else 1.2)

ts = [threading.Thread(target=worker, daemon=True) for _ in range(WORKERS)]
[t.start() for t in ts]
[t.join() for t in ts]
print(stats, flush=True)
