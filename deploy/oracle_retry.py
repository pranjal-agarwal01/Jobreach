"""
Keep pressing "Apply" on an Oracle Cloud Resource Manager stack until the server gets created.

Oracle's free ARM servers are often "Out of host capacity" in busy regions. This asks again
every few minutes, the same as pressing Actions > Apply on the stack, and stops when the server
exists, printing its public IP. Any other error stops it, so a wrong setting isn't retried
forever.

Uses Oracle's official Python library and your API key (~/.oci/config). Nothing is sent
anywhere but Oracle. While it runs, Windows is asked not to sleep (only for as long as this
script runs; no settings are changed).

    python deploy/oracle_retry.py --stack instance-20261003-1834 [--every 300]
"""
from __future__ import annotations

import argparse
import random
import sys
import time
from datetime import datetime

import oci
from oci.resource_manager.models import CreateApplyJobOperationDetails, CreateJobDetails

CAPACITY_WORDS = ("out of host capacity", "out of capacity", "insufficient capacity")
DONE = {"SUCCEEDED", "FAILED", "CANCELED"}


def log(msg: str) -> None:
    print("{} {}".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg), flush=True)


def keep_awake() -> None:
    if sys.platform == "win32":
        import ctypes
        ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)


def done_sound() -> None:
    if sys.platform == "win32":
        import winsound
        for _ in range(3):
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
            time.sleep(0.6)


def call(fn, *a, **kw):
    """One Oracle call, waiting out its rate limit (429) instead of failing."""
    for wait in (30, 60, 120, 240, 480):
        try:
            return fn(*a, **kw)
        except oci.exceptions.ServiceError as e:
            if e.status != 429:
                raise
            log("Oracle says slow down; waiting {}s".format(wait))
            time.sleep(wait)
    return fn(*a, **kw)


def find_stack(rm, compartment: str, name: str):
    stacks = call(rm.list_stacks, compartment_id=compartment).data
    for s in stacks:
        if s.display_name == name or s.id == name:
            return s
    sys.exit("No stack called {!r}. Stacks here: {}".format(name, ", ".join(s.display_name for s in stacks) or "none"))


def wait_for(rm, job_id: str, every: int = 30):
    while True:
        job = call(rm.get_job, job_id).data
        if job.lifecycle_state in DONE:
            return job
        time.sleep(every)


def public_ip(compute, network, compartment: str):
    """The newest running instance's public IP (and its name), once it has one."""
    instances = [i for i in call(compute.list_instances, compartment_id=compartment).data
                 if i.lifecycle_state in ("PROVISIONING", "STARTING", "RUNNING")]
    if not instances:
        return None, None
    inst = max(instances, key=lambda i: i.time_created)
    for att in call(compute.list_vnic_attachments, compartment_id=compartment, instance_id=inst.id).data:
        vnic = call(network.get_vnic, att.vnic_id).data
        if vnic.public_ip:
            return vnic.public_ip, inst
    return None, inst


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stack", required=True, help="the stack's name (or its OCID)")
    ap.add_argument("--every", type=int, default=600, help="seconds between attempts (default 600)")
    ap.add_argument("--profile", default="DEFAULT")
    args = ap.parse_args()

    config = oci.config.from_file(profile_name=args.profile)
    oci.config.validate_config(config)
    compartment = config["tenancy"]                    # the stack lives in the root compartment
    rm = oci.resource_manager.ResourceManagerClient(config)
    compute = oci.core.ComputeClient(config)
    network = oci.core.VirtualNetworkClient(config)

    stack = find_stack(rm, compartment, args.stack)
    log("Stack {} in {}".format(stack.display_name, config["region"]))
    keep_awake()

    attempt = 0
    while True:
        running = [j for j in call(rm.list_jobs, stack_id=stack.id).data if j.lifecycle_state not in DONE]
        if running:
            log("A job is already running ({}); waiting for it".format(running[0].display_name))
            job = wait_for(rm, running[0].id)
        else:
            attempt += 1
            log("Attempt {}: Apply".format(attempt))
            job = call(rm.create_job, CreateJobDetails(
                stack_id=stack.id, display_name="retry-apply-{}".format(attempt),
                job_operation_details=CreateApplyJobOperationDetails(execution_plan_strategy="AUTO_APPROVED"))).data
            job = wait_for(rm, job.id)

        if job.lifecycle_state == "SUCCEEDED":
            log("Applied. Waiting for the server's public IP...")
            for _ in range(40):
                ip, inst = public_ip(compute, network, compartment)
                if ip:
                    log("SERVER READY: {} ({}), public IP {}".format(inst.display_name, inst.shape, ip))
                    done_sound()
                    return
                time.sleep(15)
            log("SERVER CREATED but it has no public IP yet: add an ephemeral public IP to its VNIC in the console.")
            done_sound()
            return

        text = (job.failure_details.message if job.failure_details else "") or ""
        try:
            text += "\n" + (call(rm.get_job_logs_content, job.id).data or "")
        except oci.exceptions.ServiceError:
            pass
        if any(w in text.lower() for w in CAPACITY_WORDS):
            wait = args.every + random.randint(-30, 30)
            log("Out of host capacity. Trying again in {} min.".format(round(wait / 60, 1)))
            time.sleep(wait)
            continue
        last = [line for line in text.splitlines() if line.strip()][-8:]
        log("FAILED for another reason; stopping so it can be fixed:\n  " + "\n  ".join(last))
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Stopped.")
