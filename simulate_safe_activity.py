# simulate_safe_activity.py
import os, time, random, string, argparse

def rand_name(n=10):
    letters = string.ascii_lowercase
    return "".join(random.choice(letters) for _ in range(n))

def safe_simulate(target_dir, bursts=3, files_per_burst=80, do_delete=False):
    os.makedirs(target_dir, exist_ok=True)
    created = []

    # create files
    for i in range(files_per_burst):
        p = os.path.join(target_dir, f"{rand_name()}.txt")
        with open(p, "w") as f:
            f.write("dummy\n"*5)
        created.append(p)
    print(f"Created {len(created)} files.")
    time.sleep(1)

    # bursts of rename/modify
    for b in range(bursts):
        for i, p in enumerate(list(created)):
            if not os.path.exists(p):
                continue
            new_p = os.path.join(target_dir, f"{rand_name()}_{i}.txt")
            os.replace(p, new_p)
            with open(new_p, "a") as f:
                f.write("update\n")
            created[created.index(p)] = new_p
        print(f"Burst {b+1}/{bursts} done.")
        time.sleep(0.5)

    if do_delete:
        for p in created:
            try:
                os.remove(p)
            except FileNotFoundError:
                pass
        print("Deleted simulated files.")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("path", help="Sandbox directory (will be created if missing)")
    ap.add_argument("--bursts", type=int, default=3)
    ap.add_argument("--files-per-burst", type=int, default=80)
    ap.add_argument("--delete", action="store_true")
    args = ap.parse_args()
    safe_simulate(args.path, args.bursts, args.files_per_burst, args.delete)