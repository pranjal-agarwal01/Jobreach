"""
Keep asking Oracle Cloud for the free ARM server until it has room, then print its public IP.

Oracle's free ARM servers are often "Out of host capacity" in busy regions. Every few minutes this
makes ONE request: "create this server" (Compute LaunchInstance), with the settings saved in your
Resource Manager stack (image, shape, size, network, SSH key). When Oracle has no room the request
simply fails and nothing is created; when it has room, the server is created and the script
stops. Any other error stops it too, so a wrong setting isn't retried forever.

(--via-stack instead presses the stack's Apply each time, as the console button does. That runs a
whole job per attempt and needs status checks while it runs, which Oracle throttles more.)

Uses Oracle's official Python library and your API key (~/.oci/config). Nothing is sent anywhere
but Oracle. While it runs, Windows is asked not to sleep (only for as long as this script runs; no
settings are changed).

    python deploy/oracle_retry.py --stack instance-20261003-1834 [--every 600]
"""
from __future__ import annotations

import argparse
import io
import random
import re
import sys
import time
import zipfile
from datetime import datetime

import oci
from oci.core.models import (CreateVnicDetails, InstanceSourceViaImageDetails, LaunchInstanceDetails,
                             LaunchInstanceShapeConfigDetails)
from oci.resource_manager.models import CreateApplyJobOperationDetails, CreateJobDetails

CAPACITY_WORDS = ("out of host capacity", "out of capacity", "insufficient capacity")
DONE = {"SUCCEEDED", "FAILED", "CANCELED"}
LIVE = ("PROVISIONING", "STARTING", "RUNNING")


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
    for wait in (60, 120, 240, 480, 900):
        try:
            return fn(*a, **kw)
        except oci.exceptions.ServiceError as e:
            if e.status != 429:
                raise
            log("Oracle says slow down ({}); waiting {}s".format(getattr(fn, "__name__", "call"), wait))
            time.sleep(wait)
    return fn(*a, **kw)


def is_capacity(text: str) -> bool:
    return any(w in (text or "").lower() for w in CAPACITY_WORDS)


def find_stack(rm, compartment: str, name: str):
    stacks = call(rm.list_stacks, compartment_id=compartment).data
    for s in stacks:
        if s.display_name == name or s.id == name:
            return s
    sys.exit("No stack called {!r}. Stacks here: {}".format(name, ", ".join(s.display_name for s in stacks) or "none"))


def grab(tf: str, pattern: str, what: str) -> str:
    m = re.search(pattern, tf)
    if not m:
        sys.exit("The stack has no {} setting".format(what))
    return m.group(1)


def launch_details(rm, net, stack, compartment: str) -> LaunchInstanceDetails:
    """The server described in the stack's Terraform, in the subnet the stack already created."""
    tf = zipfile.ZipFile(io.BytesIO(call(rm.get_stack_tf_config, stack.id).data.content)).read("main.tf").decode()
    subnet_name = grab(tf, r'resource "oci_core_subnet"(?s:.*?)display_name = "([^"]+)"', "subnet")
    subnets = [s for s in call(net.list_subnets, compartment_id=compartment, display_name=subnet_name).data
               if s.lifecycle_state == "AVAILABLE" and not s.prohibit_public_ip_on_vnic]
    if not subnets:
        sys.exit("The stack's subnet {!r} doesn't exist yet: press Apply on the stack once first".format(subnet_name))
    return LaunchInstanceDetails(
        compartment_id=compartment,
        availability_domain=grab(tf, r'availability_domain = "([^"]+)"', "availability domain"),
        # The instance is the first resource; its own display_name is the first one at one tab's depth.
        display_name=grab(tf, r'\n\tdisplay_name = "([^"]+)"', "name"),
        shape=grab(tf, r'shape = "([^"]+)"', "shape"),
        shape_config=LaunchInstanceShapeConfigDetails(ocpus=float(grab(tf, r'ocpus = "([\d.]+)"', "OCPUs")),
                                                      memory_in_gbs=float(grab(tf, r'memory_in_gbs = "([\d.]+)"', "memory"))),
        source_details=InstanceSourceViaImageDetails(image_id=grab(tf, r'source_id = "([^"]+)"', "image")),
        create_vnic_details=CreateVnicDetails(subnet_id=subnets[0].id, assign_public_ip=True, display_name="Jobreach"),
        metadata={"ssh_authorized_keys": grab(tf, r'"?ssh_authorized_keys"? = "([^"]+)"', "SSH key")},
    )


def report(compute, net, compartment: str, instance_id: str) -> None:
    """Wait for the new server to run and have its public address; print it and stop."""
    for _ in range(60):
        inst = call(compute.get_instance, instance_id).data
        if inst.lifecycle_state == "RUNNING":
            for att in call(compute.list_vnic_attachments, compartment_id=compartment, instance_id=inst.id).data:
                vnic = call(net.get_vnic, att.vnic_id).data
                if vnic.public_ip:
                    log("SERVER READY: {} ({}), public IP {}".format(inst.display_name, inst.shape, vnic.public_ip))
                    done_sound()
                    return
        time.sleep(30)
    log("SERVER CREATED but it isn't running with a public IP yet: check it in the console.")
    done_sound()


def existing(compute, compartment: str):
    live = [i for i in call(compute.list_instances, compartment_id=compartment).data if i.lifecycle_state in LIVE]
    return max(live, key=lambda i: i.time_created) if live else None


def run_direct(args, compartment, rm, compute, net, stack) -> None:
    details = launch_details(rm, net, stack, compartment)
    log("Asking for {} ({:g} OCPU, {:g} GB) in {}, one request every ~{} min".format(
        details.shape, details.shape_config.ocpus, details.shape_config.memory_in_gbs,
        details.availability_domain, round(args.every / 60)))
    attempt = 0
    while True:
        inst = existing(compute, compartment)
        if inst:
            log("A server already exists ({}); waiting for its address".format(inst.display_name))
            return report(compute, net, compartment, inst.id)
        attempt += 1
        try:
            inst = call(compute.launch_instance, details).data
        except oci.exceptions.ServiceError as e:
            if is_capacity(e.message):
                wait = args.every + random.randint(-45, 45)
                log("Attempt {}: out of host capacity. Next try in {} min.".format(attempt, round(wait / 60, 1)))
                time.sleep(wait)
                continue
            log("FAILED for another reason; stopping so it can be fixed: {} {}".format(e.status, e.message))
            sys.exit(1)
        log("Attempt {}: Oracle accepted it. The server is being created.".format(attempt))
        return report(compute, net, compartment, inst.id)


def run_via_stack(args, rm, compute, net, compartment, stack) -> None:
    attempt = 0
    while True:
        running = [j for j in call(rm.list_jobs, stack_id=stack.id).data if j.lifecycle_state not in DONE]
        if running:
            job_id = running[0].id
        else:
            attempt += 1
            log("Attempt {}: Apply".format(attempt))
            job_id = call(rm.create_job, CreateJobDetails(
                stack_id=stack.id, display_name="retry-apply-{}".format(attempt),
                job_operation_details=CreateApplyJobOperationDetails(execution_plan_strategy="AUTO_APPROVED"))).data.id
        job = call(rm.get_job, job_id).data
        while job.lifecycle_state not in DONE:
            time.sleep(60)
            job = call(rm.get_job, job_id).data
        if job.lifecycle_state == "SUCCEEDED":
            inst = existing(compute, compartment)
            if inst:
                return report(compute, net, compartment, inst.id)
            return log("Applied, but no server found.")
        text = (job.failure_details.message if job.failure_details else "") or ""
        try:
            text += "\n" + (call(rm.get_job_logs_content, job.id).data or "")
        except oci.exceptions.ServiceError:
            pass
        if is_capacity(text):
            wait = args.every + random.randint(-45, 45)
            log("Out of host capacity. Next try in {} min.".format(round(wait / 60, 1)))
            time.sleep(wait)
            continue
        log("FAILED for another reason; stopping so it can be fixed:\n  " +
            "\n  ".join([line for line in text.splitlines() if line.strip()][-8:]))
        sys.exit(1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stack", required=True, help="the stack's name (or its OCID)")
    ap.add_argument("--every", type=int, default=600, help="seconds between attempts (default 600)")
    ap.add_argument("--via-stack", action="store_true", help="press the stack's Apply instead of one direct request")
    ap.add_argument("--profile", default="DEFAULT")
    args = ap.parse_args()

    config = oci.config.from_file(profile_name=args.profile)
    oci.config.validate_config(config)
    compartment = config["tenancy"]                    # the stack lives in the root compartment
    rm = oci.resource_manager.ResourceManagerClient(config)
    compute = oci.core.ComputeClient(config)
    net = oci.core.VirtualNetworkClient(config)
    stack = find_stack(rm, compartment, args.stack)
    log("Stack {} in {}".format(stack.display_name, config["region"]))
    keep_awake()
    if args.via_stack:
        run_via_stack(args, rm, compute, net, compartment, stack)
    else:
        run_direct(args, compartment, rm, compute, net, stack)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Stopped.")
